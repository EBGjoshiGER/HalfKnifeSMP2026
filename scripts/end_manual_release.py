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
    root = Path('temp/end-manual-smoke')
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
    config = {'configVersion': 2, 'requirements': {'minecraft:diamond': 1}, 'contributionWeights': {'minecraft:diamond': 10},
              'completionDelaySeconds': 1, 'completionCommands': ['DimensionDaddy enable end', 'scoreboard players add opened manual_release 1']}
    (folder / 'config.json').write_text(json.dumps(config))
    seed = {'donated': {'minecraft:diamond': 1}, 'active': True, 'paused': False, 'completed': True,
            'completionCommandsExecuted': False, 'playerTotals': {'fixture': 1}, 'playerPoints': {'fixture': 10}, 'playerNames': {'fixture': 'Fixture'}}
    (folder / 'progress.json').write_text(json.dumps(seed))

    def state():
        return json.loads((folder / 'progress.json').read_text())

    def boot(name):
        log = (root / name).open('w')
        p = subprocess.Popen(['java', '-Xms512M', '-Xmx2G', '-Dhalfknife.endproject.test=true', '-jar', 'server.jar', 'nogui'], cwd=root,
                             stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, text=True)
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline and p.poll() is None:
            if 'Done (' in (root / name).read_text():
                return p, log
            time.sleep(1)
        p.kill(); p.wait(); log.close()
        raise RuntimeError('Boot failed: ' + (root / name).read_text()[-12000:])

    def command(p, value, delay=2):
        p.stdin.write(value + '\n'); p.stdin.flush(); time.sleep(delay)

    def stop(p, log):
        if p.poll() is None:
            command(p, 'stop', 0)
            try:
                p.wait(timeout=45)
            except subprocess.TimeoutExpired:
                p.kill(); p.wait()
        log.close()
        assert p.returncode == 0, 'Test server failed'

    # Exercise one-time migration from the actual installed config with fixture progress.
    live_config = json.loads(read(ftp, 'config/endproject/config.json'))
    assert live_config.get('configVersion', 1) < 2, 'Expected pre-migration config'
    approved = json.loads(Path('mods/end-project/approved-requirements.json').read_text())
    legacy = dict(live_config)
    legacy['contributionWeights'] = dict(legacy.get('contributionWeights', {}))
    legacy['contributionWeights']['minecraft:nether_quartz'] = 7
    (folder / 'config.json').write_text(json.dumps(legacy))
    fixture = dict(seed)
    fixture['active'] = False
    fixture['completed'] = False
    fixture['donated'] = {'minecraft:nether_quartz': 7, 'minecraft:blaze_rod': 3}
    (folder / 'progress.json').write_text(json.dumps(fixture))
    p, log = boot('migration.log')
    stop(p, log)
    migrated = json.loads((folder / 'config.json').read_text())
    assert migrated['requirements'] == approved, 'Migration did not apply the twelve approved amounts'
    assert migrated['configVersion'] == 2
    assert migrated['contributionWeights']['minecraft:quartz'] == 7
    for key, value in legacy.items():
        if key not in ('requirements', 'configVersion', 'contributionWeights'):
            assert migrated[key] == value, 'Unrelated config changed: ' + key
    assert not state()['active'] and not state()['completionCommandsExecuted'], 'Migration started project'
    assert state()['donated']['minecraft:quartz'] == 7 and state()['donated']['minecraft:blaze_rod'] == 3
    assert 'minecraft:nether_quartz' not in state()['donated']
    for key in ('playerTotals', 'playerPoints', 'playerNames'):
        assert state()[key] == fixture[key], 'Migration changed contribution history'
    assert 'END ITEM REGISTRY PASS' in (root / 'migration.log').read_text()
    migrated['requirements']['minecraft:quartz'] = 12345
    (folder / 'config.json').write_text(json.dumps(migrated))
    p, log = boot('custom-config.log')
    stop(p, log)
    assert json.loads((folder / 'config.json').read_text())['requirements']['minecraft:quartz'] == 12345
    (folder / 'config.json').write_text(json.dumps(config))
    (folder / 'progress.json').write_text(json.dumps(seed))
    print('MIGRATION PASS: twelve exact approved targets and real item IDs, quartz counts/weights, history, inactive state, commands and future config edits preserved.', flush=True)
    p, log = boot('first.log')
    try:
        command(p, 'scoreboard objectives add manual_release dummy')
        assert state()['completed'] and not state()['completionCommandsExecuted'], 'Startup auto-opened completed project'
        for key in ('donated', 'playerTotals', 'playerPoints', 'playerNames'):
            assert state()[key] == seed[key], 'Existing contributions changed'
        command(p, 'endproject reload')
        assert not state()['completionCommandsExecuted'], 'Reload auto-opened'
    finally:
        stop(p, log)
    p, log = boot('second.log')
    try:
        time.sleep(2)
        assert not state()['completionCommandsExecuted'], 'Restart auto-opened'
        command(p, 'endproject reset')
        command(p, 'endproject activate')
        assert not state()['completionCommandsExecuted'], 'Incomplete goal opened'
        command(p, 'endproject start')
        command(p, 'endproject forcecomplete')
        assert state()['completed'] and not state()['completionCommandsExecuted'], 'Goal auto-opened'
        command(p, 'endproject activate')
        assert state()['completionCommandsExecuted'], 'Manual activation did not open'
        command(p, 'endproject activate')
        command(p, 'endproject forcecomplete')
        command(p, 'scoreboard players get opened manual_release')
        assert 'opened has 1' in (root / 'second.log').read_text(), 'Activation executed more than once'
        command(p, 'endproject lockend')
        assert not state()['completionCommandsExecuted'], 'Relock state wrong'
        # Failed command must not mark the End as opened; retry after fixing config.
        config['completionCommands'] = ['missing_release_command']
        (folder / 'config.json').write_text(json.dumps(config))
        command(p, 'endproject reload')
        command(p, 'endproject activate')
        assert not state()['completionCommandsExecuted'], 'Failed command marked as opened'
        config['completionCommands'] = ['DimensionDaddy enable end']
        config['completionDelaySeconds'] = 10
        (folder / 'config.json').write_text(json.dumps(config))
        command(p, 'endproject reload')
        command(p, 'endproject unlockend', 0.2)
        command(p, 'endproject reload', 11)
        assert not state()['completionCommandsExecuted'], 'Reload did not cancel countdown'
        config['completionDelaySeconds'] = 0
        (folder / 'config.json').write_text(json.dumps(config))
        command(p, 'endproject reload')
        command(p, 'endproject unlockend')
        assert state()['completionCommandsExecuted'], 'Retry/zero-delay/alias failed'
    finally:
        stop(p, log)
    p, log = boot('third.log')
    try:
        time.sleep(2)
        assert state()['completionCommandsExecuted'], 'Opened state lost on restart'
    finally:
        stop(p, log)
    print('SMOKE PASS: existing progress, goal/reload/restarts stay closed; manual countdown, duplicate prevention, failure retry, alias and zero-delay passed.', flush=True)


def main():
    new_path = Path('mods/end-project/build/libs/end-project-1.1.0.jar')
    new_jar = new_path.read_bytes()
    assert metadata(new_jar)['id'] == 'endproject' and metadata(new_jar)['version'] == '1.1.0'
    with ftplib.FTP(timeout=45) as ftp:
        ftp.connect(os.environ['FTP_HOST'], int(os.environ.get('FTP_PORT') or '21'))
        ftp.login(os.environ['FTP_USER'], os.environ['FTP_PASSWORD'])
        installed = sorted(Path(n).name for n in ftp.nlst('mods') if n.endswith('.jar'))
        candidates = [n for n in installed if n.startswith('end-project-')]
        if len(candidates) != 1:
            raise RuntimeError('Expected exactly one End Project jar')
        old_name = candidates[0]
        old = read(ftp, 'mods/' + old_name)
        if metadata(old)['id'] != 'endproject' or metadata(old)['version'] != '1.0.0':
            raise RuntimeError('Expected installed End Project 1.0.0')
        smoke(ftp, installed, new_jar)
        if read(ftp, 'mods/' + old_name) != old:
            raise RuntimeError('Installed mod changed during testing')
        # Never edit production progress/config or issue any production commands.
        base = 'maintenance-backups'
        try:
            ftp.mkd(base)
        except ftplib.error_perm:
            ftp.cwd(base); ftp.cwd('..')
        backup = base + '/end-manual-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
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
    print('DEPLOY PASS: End Project 1.1.0 staged and verified; backup retained. RESTART REQUIRED. Production config/progress untouched.', flush=True)


if __name__ == '__main__':
    main()

