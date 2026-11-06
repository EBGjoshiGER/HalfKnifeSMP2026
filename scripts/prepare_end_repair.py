"""Test End generator replacement in isolation; never edit the production world."""
import copy
import ftplib
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
import urllib.request
import nbtlib

ROOT = Path('end-repair-test')
ROOT.mkdir(exist_ok=True)
(ROOT / 'mods').mkdir(exist_ok=True)
FTP = ftplib.FTP(timeout=60)
WORLD = 'HalfKnifeSMP2026'
TARGET = WORLD + '/data/minecraft/world_gen_settings.dat'

def read(path):
    b = io.BytesIO()
    FTP.retrbinary('RETR ' + path, b.write)
    return b.getvalue()

def parse(raw):
    return nbtlib.File.parse(io.BytesIO(gzip.decompress(raw)))

def encode(tree):
    b = io.BytesIO()
    tree.write(b)
    return gzip.compress(b.getvalue(), mtime=0)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def download(url):
    req = urllib.request.Request(url, headers={'User-Agent':'HalfKnife-End-Repair'})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()

def boot(probe=False):
    output = []
    q = queue.Queue()
    process = subprocess.Popen(['java','-Xms512M','-Xmx4G','-jar','server.jar','nogui'], cwd=ROOT,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    def consume():
        for line in process.stdout:
            output.append(line)
            q.put(line)
    thread = threading.Thread(target=consume, daemon=True)
    thread.start()
    def send(command):
        process.stdin.write(command + '\n')
        process.stdin.flush()
    def wait_for(predicate, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('Isolated server exited: ' + ''.join(output[-12:]))
            try:
                line = q.get(timeout=1)
            except queue.Empty:
                continue
            if predicate(line):
                return line
        raise RuntimeError('Isolated server timed out: ' + ''.join(output[-12:]))
    try:
        wait_for(lambda line:'Done (' in line, 300)
        if probe:
            if any('not a BetterEnd End biome source' in line for line in output):
                raise RuntimeError('Vanilla End fallback still active')
            send('execute in minecraft:the_end positioned 10000 80 10000 run locate biome betterend:glowing_grasslands')
            line = wait_for(lambda line:'betterend:glowing_grasslands' in line and ('nearest' in line or 'Could not find' in line), 120)
            match = re.search(r'\[(-?\d+),\s*(-?\d+|~),\s*(-?\d+)\]', line)
            if not match:
                raise RuntimeError('No BetterEnd biome located')
            x, y, z = match.groups()
            y = '80' if y == '~' else y
            send(f'execute in minecraft:the_end positioned {x} {y} {z} if biome ~ ~ ~ betterend:glowing_grasslands run say END_REPAIR_BIOME_PASS')
            wait_for(lambda line:'END_REPAIR_BIOME_PASS' in line, 45)
            send(f'execute in minecraft:the_end run forceload add {x} {z}')
            wait_for(lambda line:'Marked chunk' in line or 'already marked' in line, 45)
            send('save-all flush')
            wait_for(lambda line:'Saved the game' in line, 90)
        print('ISOLATED_BOOT_PASS probe=' + str(probe), flush=True)
    finally:
        if process.poll() is None:
            send('stop')
            try:
                process.wait(timeout=90)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise RuntimeError('Isolated server did not stop cleanly')
        thread.join(timeout=5)
        (ROOT / ('probe.log' if probe else 'template.log')).write_text(''.join(output))

try:
    FTP.connect(os.environ['FTP_HOST'], int(os.environ.get('FTP_PORT') or '21'))
    FTP.login(os.environ['FTP_USER'], os.environ['FTP_PASSWORD'])
    props = {}
    for line in read('server.properties').decode('utf-8-sig').splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=',1)
            props[k] = v
    assert props['level-name'] == WORLD
    original = read(TARGET)
    tree = parse(original)
    dims = tree['data']['dimensions']
    assert dims['minecraft:the_end']['generator']['biome_source']['type'] == 'minecraft:the_end'
    installed = sorted(Path(n).name for n in FTP.nlst('mods') if n.endswith('.jar'))
    for i, name in enumerate(installed):
        (ROOT / 'mods' / name).write_bytes(read('mods/' + name))
        if i % 20 == 0:
            print('DOWNLOADED_MODS',i+1,'of',len(installed),flush=True)
    # Reuse the server's existing EULA acceptance; no new agreement is accepted here.
    eula = read('eula.txt')
    assert re.search(rb'^eula=true\s*$',eula,re.M)
    (ROOT / 'eula.txt').write_bytes(eula)
    for path in ('config/betterend/generator.json','config/bclib/main.json','config/wover/main.json'):
        dest = ROOT / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(read(path))
    installers = json.loads(download('https://meta.fabricmc.net/v2/versions/installer'))
    installer = next(x['version'] for x in installers if x.get('stable'))
    (ROOT/'server.jar').write_bytes(download(f'https://meta.fabricmc.net/v2/versions/loader/26.2/0.19.5/{installer}/server/jar'))
    (ROOT/'server.properties').write_text('server-ip=127.0.0.1\nserver-port=0\nonline-mode=false\nview-distance=2\nsimulation-distance=2\nlevel-name=test-world\nlevel-type=wover:normal\nlevel-seed=7261126\nspawn-protection=0\n')
    boot()
    test_path = ROOT/'test-world/data/minecraft/world_gen_settings.dat'
    template = parse(test_path.read_bytes())['data']['dimensions']['minecraft:the_end']['generator']
    assert str(template['biome_source']['type']).startswith('wover:')
    changed = copy.deepcopy(tree)
    generator = copy.deepcopy(template)
    if 'seed' in generator['biome_source']:
        generator['biome_source']['seed'] = copy.deepcopy(tree['data']['seed'])
    changed['data']['dimensions']['minecraft:the_end']['generator'] = generator
    # Exact recursive comparison proves nothing outside this one generator was changed.
    restored = copy.deepcopy(changed)
    restored['data']['dimensions']['minecraft:the_end']['generator'] = copy.deepcopy(dims['minecraft:the_end']['generator'])
    assert restored == tree
    candidate = encode(changed)
    assert parse(candidate) == changed
    test_path.write_bytes(candidate)
    boot(probe=True)
    saved = parse(test_path.read_bytes())
    assert str(saved['data']['dimensions']['minecraft:the_end']['generator']['biome_source']['type']).startswith('wover:')
    assert saved['data']['dimensions']['minecraft:overworld'] == dims['minecraft:overworld']
    assert saved['data']['dimensions']['minecraft:the_nether'] == dims['minecraft:the_nether']
    assert saved['data']['seed'] == tree['data']['seed']
    print('VERIFIED_ONLY_END_GENERATOR_CHANGED',flush=True)
    print('GENERATOR_TYPES',str(generator['type']),str(generator['biome_source']['type']),flush=True)
    print('ORIGINAL_SHA256',digest(original),flush=True)
    print('CANDIDATE_SHA256',digest(candidate),flush=True)
    print('PREPARATION_PASS_NO_PRODUCTION_WRITES',flush=True)
finally:
    FTP.close()
