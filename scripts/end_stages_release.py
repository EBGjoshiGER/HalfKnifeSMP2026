"""Test isolated manual activation, then stage only the new jar for the next restart."""
from datetime import datetime, timezone
import ftplib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
import zipfile


def read(ftp, path):
    data = io.BytesIO()
    ftp.retrbinary('RETR ' + path, data.write)
    return data.getvalue()


def metadata(data):
    with zipfile.ZipFile(io.BytesIO(data)) as jar:
        return json.loads(jar.read('fabric.mod.json'))


def download(url):
    with urllib.request.urlopen(url, timeout=90) as response:
        return response.read()


def smoke(ftp, installed, new_jar):
    root = Path('temp/end-stages-smoke')
    (root / 'mods').mkdir(parents=True, exist_ok=True)
    for label, predicate in [('Fabric API', lambda n: n.startswith('fabric-api-')),
                             ('DimensionDaddy', lambda n: 'dimension' in n.lower() and 'daddy' in n.lower())]:
        names = [n for n in installed if predicate(n)]
        if len(names) != 1:
            raise RuntimeError('Cannot uniquely resolve ' + label)
        (root / 'mods' / names[0]).write_bytes(read(ftp, 'mods/' + names[0]))
    (root / 'mods/end-project.jar').write_bytes(new_jar)
    installer = next(x['version'] for x in json.loads(download('https://meta.fabricmc.net/v2/versions/installer')) if x.get('stable'))
    (root / 'server.jar').write_bytes(download(f'https://meta.fabricmc.net/v2/versions/loader/26.2/0.19.5/{installer}/server/jar'))
    (root / 'eula.txt').write_text('eula=true\n')
    (root / 'server.properties').write_text('server-ip=127.0.0.1\nserver-port=0\nonline-mode=false\nview-distance=2\nsimulation-distance=2\nlevel-name=smoke-world\nlevel-type=minecraft:flat\n')
    folder = root / 'config/endproject'
    folder.mkdir(parents=True, exist_ok=True)
    live_config = json.loads(read(ftp, 'config/endproject/config.json'))
    live_progress = json.loads(read(ftp, 'config/endproject/progress.json'))
    (folder / 'config.json').write_text(json.dumps(live_config))
    (folder / 'progress.json').write_text(json.dumps(live_progress))

    def state():
        return json.loads((folder / 'progress.json').read_text())

    def boot(name):
        log = (root / name).open('w')
        p = subprocess.Popen(['java', '-Xms512M', '-Xmx2G', '-Dhalfknife.endproject.test=true', '-jar', 'server.jar', 'nogui'], cwd=root,
                             stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, text=True)
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline and p.poll() is None:
            if 'Done (' in (root / name).read_text() and 'END STAGES PASS' in (root / name).read_text():
                assert 'END STAGES PASS' in (root / name).read_text(), 'Stage integration checks did not run'
                return p, log
            time.sleep(1)
        p.kill(); p.wait(); log.close()
        raise RuntimeError('Boot failed: ' + (root / name).read_text()[-12000:])

    def command(p, value, delay=2):
        p.stdin.write(value + '\n'); p.stdin.flush(); time.sleep(delay)

    def stop(p, log):
        if p.poll() is None:
            command(p, 'stop', 0)
            try: p.wait(timeout=45)
            except subprocess.TimeoutExpired: p.kill(); p.wait()
        log.close()
        assert p.returncode == 0, 'Test server failed'

    p, log = boot('migration.log')
    stop(p, log)
    migrated = json.loads((folder / 'config.json').read_text())
    assert migrated['configVersion'] == 3
    assert len(migrated['stages']) == 4
    for key, value in live_config.items():
        if key not in ('configVersion', 'stages'):
            assert migrated[key] == value, 'Existing config changed: ' + key
    for key, value in live_progress.items():
        assert state()[key] == value, 'Existing progress changed: ' + key
    # Already-donated items in future stages survive migration and repeated boots.
    fixture = dict(live_progress)
    fixture.update(active=True, paused=False, completed=False, completionCommandsExecuted=False)
    fixture['donated'] = dict(live_progress['donated'])
    for id in migrated['stages'][0]: fixture['donated'][id] = migrated['requirements'][id]
    fixture['donated']['minecraft:ancient_debris'] = 7
    fixture['playerTotals'] = {'fixture': 123}
    fixture['playerPoints'] = {'fixture': 456}
    fixture['playerNames'] = {'fixture': 'Fixture'}
    (folder / 'progress.json').write_text(json.dumps(fixture))
    migrated['completionDelaySeconds'] = 1
    migrated['completionCommands'] = ['DimensionDaddy enable end', 'scoreboard players add opened manual_release 1']
    (folder / 'config.json').write_text(json.dumps(migrated))
    p, log = boot('stages.log')
    try:
        command(p, 'endproject status')
        assert 'Stufe 2 von 4' in (root / 'stages.log').read_text(), 'Restart did not resume next stage'
        for key in ('donated', 'playerTotals', 'playerPoints', 'playerNames'):
            assert state()[key] == fixture[key], 'Contribution history changed'
        command(p, 'scoreboard objectives add manual_release dummy')
        command(p, 'endproject activate')
        assert not state()['completionCommandsExecuted'], 'Incomplete goal opened'
        command(p, 'endproject forcecomplete')
        assert state()['completed'] and not state()['completionCommandsExecuted'], 'Goal auto-opened End'
        command(p, 'endproject reload')
        assert not state()['completionCommandsExecuted'], 'Reload auto-opened End'
    finally:
        stop(p, log)
    p, log = boot('restart.log')
    try:
        assert not state()['completionCommandsExecuted'], 'Restart auto-opened End'
        command(p, 'endproject activate')
        assert state()['completionCommandsExecuted'], 'Manual activation failed'
        command(p, 'endproject activate')
        command(p, 'scoreboard players get opened manual_release')
        assert 'opened has 1' in (root / 'restart.log').read_text(), 'Activation ran more than once'
    finally:
        stop(p, log)
    print('SMOKE PASS: live config/history preserved; stage migration and restart; hidden/locked stages; manual release only.', flush=True)


def main():
    new_path = Path('mods/end-project/build/libs/end-project-1.2.0.jar')
    new_jar = new_path.read_bytes()
    assert metadata(new_jar)['id'] == 'endproject' and metadata(new_jar)['version'] == '1.2.0'
    with ftplib.FTP(timeout=45) as ftp:
        ftp.connect(os.environ['FTP_HOST'], int(os.environ.get('FTP_PORT') or '21'))
        ftp.login(os.environ['FTP_USER'], os.environ['FTP_PASSWORD'])
        installed = sorted(Path(n).name for n in ftp.nlst('mods') if n.endswith('.jar'))
        candidates = [n for n in installed if n.startswith('end-project-')]
        if len(candidates) != 1:
            raise RuntimeError('Expected exactly one End Project jar')
        old_name = candidates[0]
        old = read(ftp, 'mods/' + old_name)
        if metadata(old)['id'] != 'endproject' or metadata(old)['version'] != '1.1.0':
            raise RuntimeError('Expected installed End Project 1.1.0')
        import hashlib
        assert hashlib.sha256(old).hexdigest() == 'b95c03bc60e5ebe92c0477da96414e28429f387b0a2968336755f6d237a083c7', 'Server mod differs from inspected snapshot'
        smoke(ftp, installed, new_jar)
        if read(ftp, 'mods/' + old_name) != old:
            raise RuntimeError('Installed mod changed during testing')
        # Never edit production progress/config or issue any production commands.
        base = 'maintenance-backups'
        try:
            ftp.mkd(base)
        except ftplib.error_perm:
            ftp.cwd(base); ftp.cwd('..')
        backup = base + '/end-stages-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        ftp.mkd(backup)
        for name in ('config.json', 'progress.json'):
            original = read(ftp, 'config/endproject/' + name)
            ftp.storbinary('STOR ' + backup + '/' + name, io.BytesIO(original))
            assert read(ftp, backup + '/' + name) == original, 'State backup failed'
        ftp.storbinary('STOR ' + backup + '/' + old_name, io.BytesIO(old))
        assert read(ftp, backup + '/' + old_name) == old, 'Backup failed'
        destination = 'mods/' + new_path.name
        temporary = destination + '.upload'
        ftp.storbinary('STOR ' + temporary, io.BytesIO(new_jar))
        assert read(ftp, temporary) == new_jar, 'Upload check failed'
        moved = False
        try:
            ftp.rename('mods/' + old_name, backup + '/disabled-' + old_name)
            moved = True
            ftp.rename(temporary, destination)
            assert read(ftp, destination) == new_jar
            assert sorted(Path(n).name for n in ftp.nlst('mods') if n.endswith('.jar')) == sorted(set(installed) - {old_name} | {new_path.name})
        except Exception:
            if moved:
                try:
                    ftp.delete(destination)
                except ftplib.error_perm:
                    pass
                ftp.rename(backup + '/disabled-' + old_name, 'mods/' + old_name)
            raise
    print('DEPLOY PASS: End Project 1.2.0 staged and verified; backup retained. RESTART REQUIRED. Production config/progress untouched.', flush=True)


if __name__ == '__main__':
    main()

