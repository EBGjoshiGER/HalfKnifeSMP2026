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
    root = Path('temp/nether-manual-smoke')
    (root / 'mods').mkdir(parents=True, exist_ok=True)
    for label, predicate in [('Fabric API', lambda n: n.startswith('fabric-api-')),
                             ('DimensionDaddy', lambda n: 'dimension' in n.lower() and 'daddy' in n.lower())]:
        names = [n for n in installed if predicate(n)]
        if len(names) != 1:
            raise RuntimeError('Cannot uniquely resolve ' + label)
        (root / 'mods' / names[0]).write_bytes(read(ftp, 'mods/' + names[0]))
    (root / 'mods/nether-project.jar').write_bytes(new_jar)
    installer = next(x['version'] for x in json.loads(download('https://meta.fabricmc.net/v2/versions/installer')) if x.get('stable'))
    (root / 'server.jar').write_bytes(download(f'https://meta.fabricmc.net/v2/versions/loader/26.2/0.19.5/{installer}/server/jar'))
    (root / 'eula.txt').write_text('eula=true\n')
    (root / 'server.properties').write_text('server-ip=127.0.0.1\nserver-port=0\nonline-mode=false\nview-distance=2\nsimulation-distance=2\nlevel-name=smoke-world\nlevel-type=minecraft:flat\n')
    folder = root / 'config/netherproject'
    folder.mkdir(parents=True, exist_ok=True)
    config = {'configVersion': 3, 'requirements': {'minecraft:diamond': 1}, 'contributionWeights': {'minecraft:diamond': 10},
              'completionDelaySeconds': 1, 'completionCommands': ['DimensionDaddy enable nether', 'scoreboard players add opened manual_release 1']}
    (folder / 'config.json').write_text(json.dumps(config))
    seed = {'donated': {'minecraft:diamond': 1}, 'active': True, 'paused': False, 'completed': True,
            'completionCommandsExecuted': False, 'playerTotals': {'fixture': 1}, 'playerPoints': {'fixture': 10}, 'playerNames': {'fixture': 'Fixture'}}
    (folder / 'progress.json').write_text(json.dumps(seed))

    def state():
        return json.loads((folder / 'progress.json').read_text())

    def boot(name):
        log = (root / name).open('w')
        p = subprocess.Popen(['java', '-Xms512M', '-Xmx2G', '-jar', 'server.jar', 'nogui'], cwd=root,
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

    p, log = boot('first.log')
    try:
        command(p, 'scoreboard objectives add manual_release dummy')
        assert state()['completed'] and not state()['completionCommandsExecuted'], 'Startup auto-opened completed project'
        for key in ('donated', 'playerTotals', 'playerPoints', 'playerNames'):
            assert state()[key] == seed[key], 'Existing contributions changed'
        command(p, 'netherproject reload')
        assert not state()['completionCommandsExecuted'], 'Reload auto-opened'
    finally:
        stop(p, log)
    p, log = boot('second.log')
    try:
        time.sleep(2)
        assert not state()['completionCommandsExecuted'], 'Restart auto-opened'
        command(p, 'netherproject reset')
        command(p, 'netherproject activate')
        assert not state()['completionCommandsExecuted'], 'Incomplete goal opened'
        command(p, 'netherproject start')
        command(p, 'netherproject forcecomplete')
        assert state()['completed'] and not state()['completionCommandsExecuted'], 'Goal auto-opened'
        command(p, 'netherproject activate')
        assert state()['completionCommandsExecuted'], 'Manual activation did not open'
        command(p, 'netherproject activate')
        command(p, 'netherproject forcecomplete')
        command(p, 'scoreboard players get opened manual_release')
        assert 'opened has 1' in (root / 'second.log').read_text(), 'Activation executed more than once'
        command(p, 'netherproject locknether')
        assert not state()['completionCommandsExecuted'], 'Relock state wrong'
        # Failed command must not mark the Nether as opened; retry after fixing config.
        config['completionCommands'] = ['missing_release_command']
        (folder / 'config.json').write_text(json.dumps(config))
        command(p, 'netherproject reload')
        command(p, 'netherproject activate')
        assert not state()['completionCommandsExecuted'], 'Failed command marked as opened'
        config['completionCommands'] = ['DimensionDaddy enable nether']
        config['completionDelaySeconds'] = 10
        (folder / 'config.json').write_text(json.dumps(config))
        command(p, 'netherproject reload')
        command(p, 'netherproject unlocknether', 0.2)
        command(p, 'netherproject reload', 11)
        assert not state()['completionCommandsExecuted'], 'Reload did not cancel countdown'
        config['completionDelaySeconds'] = 0
        (folder / 'config.json').write_text(json.dumps(config))
        command(p, 'netherproject reload')
        command(p, 'netherproject unlocknether')
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
    new_path = Path('mods/nether-project/build/libs/nether-project-2.4.0.jar')
    new_jar = new_path.read_bytes()
    assert metadata(new_jar)['id'] == 'netherproject' and metadata(new_jar)['version'] == '2.4.0'
    with ftplib.FTP(timeout=45) as ftp:
        ftp.connect(os.environ['FTP_HOST'], int(os.environ.get('FTP_PORT') or '21'))
        ftp.login(os.environ['FTP_USER'], os.environ['FTP_PASSWORD'])
        installed = sorted(Path(n).name for n in ftp.nlst('mods') if n.endswith('.jar'))
        candidates = [n for n in installed if n.startswith('nether-project-')]
        if len(candidates) != 1:
            raise RuntimeError('Expected exactly one Nether Project jar')
        old_name = candidates[0]
        old = read(ftp, 'mods/' + old_name)
        if metadata(old)['id'] != 'netherproject' or metadata(old)['version'] != '2.3.0':
            raise RuntimeError('Expected installed Nether Project 2.3.0')
        smoke(ftp, installed, new_jar)
        if read(ftp, 'mods/' + old_name) != old:
            raise RuntimeError('Installed mod changed during testing')
        # Never edit production progress/config or issue any production commands.
        base = 'maintenance-backups'
        try:
            ftp.mkd(base)
        except ftplib.error_perm:
            ftp.cwd(base); ftp.cwd('..')
        backup = base + '/nether-manual-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        ftp.mkd(backup)
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
    print('DEPLOY PASS: Nether Project 2.4.0 staged and verified; backup retained. RESTART REQUIRED. Production config/progress untouched.', flush=True)


if __name__ == '__main__':
    main()
