"""Build a narrowly patched RAS 5.0.0, test the actual config copy, install with backup."""
import base64
import ftplib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import urllib.request
import zipfile

ROOT = Path('temp/ras-upgrade')
SHA512 = '600bef27fcea3c50dc6caaaffbb09e6f34525afe74625553443dff0249c36a792b4ea7ec88b31e33f7e07940dbc12564ecf2bf7a03add9d9ece0f839769bf801'
OLD_SHA256 = '023c1040c123e65aa88006a8f942c1d2c68fc55094801f68844ea522022c7ab5'
URL = 'https://cdn.modrinth.com/data/d85UTOuq/versions/b4kQHIIw/rpg_attribute_system-fabric-26.2-5.0.0.jar'
OUTPUT = ROOT / 'rpg_attribute_system-fabric-26.2-5.0.0-halfknife.jar'
TARGET = 'mods/rpg_attribute_reworked.jar'


def connect():
    ftp = ftplib.FTP(timeout=45)
    ftp.connect(os.environ['FTP_HOST'], int(os.environ.get('FTP_PORT') or '21'))
    ftp.login(os.environ['FTP_USER'], os.environ['FTP_PASSWORD'])
    return ftp


def read(ftp, path):
    data = io.BytesIO(); ftp.retrbinary('RETR ' + path, data.write); return data.getvalue()


def configs(ftp, remote='config/ras'):
    result = {}
    def walk(folder):
        for name, facts in list(ftp.mlsd(folder)):
            if name in {'.', '..'} or '/' in name or '\\' in name: continue
            path = folder + '/' + name
            if facts.get('type') == 'dir': walk(path)
            elif facts.get('type') == 'file': result[path] = read(ftp, path)
    walk(remote)
    return result


def prepare():
    ROOT.mkdir(parents=True, exist_ok=True)
    original = urllib.request.urlopen(URL, timeout=90).read()
    assert hashlib.sha512(original).hexdigest() == SHA512, 'Not the exact uploaded client JAR'
    (ROOT / 'original-5.0.0.jar').write_bytes(original)
    ftp = connect()
    try:
        old = read(ftp, TARGET)
        if hashlib.sha256(old).hexdigest() != OLD_SHA256:
            # A repeated validation may run after the first successful installation.
            old = read(ftp, TARGET + '.before-5.0.0-halfknife.bak')
        assert hashlib.sha256(old).hexdigest() == OLD_SHA256, 'Original server RAS backup does not match inspection'
        (ROOT / 'old-4.2.5.jar').write_bytes(old)
        snapshot = configs(ftp)
        assert len(snapshot) >= 10, 'Missing RAS config tree'
        for path, data in snapshot.items():
            dest = ROOT / path; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)
        (ROOT / 'config-hashes.json').write_text(json.dumps({p: hashlib.sha256(b).hexdigest() for p, b in snapshot.items()}, sort_keys=True))
        print('Copied RAS config files for isolated testing:', len(snapshot))
    finally: ftp.close()


def package():
    compiled = Path('mods/ras-upgrade/build/classes/java/main/tn/nightbeam/ras/events')
    changes = {'tn/nightbeam/ras/events/' + p.name: p.read_bytes() for p in compiled.glob('FabricRpgAttributeSystemModEvents*.class')}
    assert 'tn/nightbeam/ras/events/FabricRpgAttributeSystemModEvents.class' in changes
    with zipfile.ZipFile(ROOT / 'original-5.0.0.jar') as original, zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_DEFLATED) as out:
        for entry in original.infolist():
            out.writestr(entry, changes.pop(entry.filename, original.read(entry.filename)))
        for name, data in changes.items(): out.writestr(name, data)
    with zipfile.ZipFile(ROOT / 'original-5.0.0.jar') as a, zipfile.ZipFile(OUTPUT) as b:
        changed = [p for p in a.namelist() if a.read(p) != b.read(p)]
        assert changed and all(p.startswith('tn/nightbeam/ras/events/FabricRpgAttributeSystemModEvents') for p in changed), changed
        assert a.read('tn/nightbeam/ras/network/FabricAttributeAllocationPayload.class') == b.read('tn/nightbeam/ras/network/FabricAttributeAllocationPayload.class')
        for p in changed: print('PATCH_CLASS_BASE64', p, base64.b64encode(b.read(p)).decode())
    print('Packaged exact RAS 5.0.0; changed only server item/equipment event classes:', changed)


def verify():
    import json5
    source = ROOT / 'config/ras'
    tested = Path('temp/active-playtime-smoke/config/ras')
    changes = []
    for old in source.rglob('*.json'):
        new = tested / old.relative_to(source)
        before = json5.loads(old.read_text())
        after = json5.loads(new.read_text())
        for key, value in before.items():
            if after.get(key) != value: changes.append((str(old.relative_to(source)), key, value, after.get(key)))
    assert not changes, 'Existing config values changed in 5.0.0: ' + repr(changes)
    log = Path('temp/active-playtime-smoke/smoke.log').read_text()
    assert 'HALFKNIFE RAS UPGRADE PASSED' in log
    print('All existing RAS config values survived isolated startup; item locks/allocation checks passed.')


def install():
    content = OUTPUT.read_bytes()
    ftp = connect()
    backup = TARGET + '.before-5.0.0-halfknife.bak'
    moved = False
    try:
        installed = read(ftp, TARGET)
        if installed != content:
            assert hashlib.sha256(installed).hexdigest() == OLD_SHA256, 'RAS changed during tests'
        expected = json.loads((ROOT / 'config-hashes.json').read_text())
        current = {p: hashlib.sha256(b).hexdigest() for p, b in configs(ftp).items()}
        assert current == expected, 'Configs changed during tests; test the new values first'
        if installed == content:
            print('Already installed: exact tested RAS 5.0.0 HalfKnife JAR, config values verified again; no server files changed.')
            return
        ftp.storbinary('STOR ' + TARGET + '.upload', io.BytesIO(content))
        assert read(ftp, TARGET + '.upload') == content, 'Upload checksum mismatch'
        config_backup = io.BytesIO()
        with zipfile.ZipFile(config_backup, 'w', zipfile.ZIP_DEFLATED) as z:
            for path in expected: z.write(ROOT / path, path)
        ftp.storbinary('STOR config/halfknife-ras-before-5.0.0.zip', io.BytesIO(config_backup.getvalue()))
        # Refuse to replace an older backup if this workflow is accidentally retried.
        try: ftp.size(backup)
        except ftplib.error_perm: pass
        else: raise RuntimeError('Upgrade backup already exists')
        ftp.rename(TARGET, backup); moved = True
        try: ftp.rename(TARGET + '.upload', TARGET)
        except Exception:
            ftp.rename(backup, TARGET); moved = False; raise
        assert read(ftp, TARGET) == content
        assert {p: hashlib.sha256(b).hexdigest() for p, b in configs(ftp).items()} == expected
        print('RAS 5.0.0 HalfKnife installed. Existing config files unchanged; old JAR/config backup created. Restart server to activate.')
    except Exception:
        if moved:
            try:
                ftp.delete(TARGET); ftp.rename(backup, TARGET)
            except Exception as error: print('Rollback needs attention:', type(error).__name__)
        raise
    finally: ftp.close()


if __name__ == '__main__':
    {'prepare': prepare, 'package': package, 'verify': verify, 'install': install}[sys.argv[1]]()
