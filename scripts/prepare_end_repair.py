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
import socket
import threading
import time
import urllib.request
import zipfile
import nbtlib
import end_regions

ROOT = Path('end-repair-test')
ROOT.mkdir(exist_ok=True)
(ROOT / 'mods').mkdir(exist_ok=True)
FTP = ftplib.FTP(timeout=60)
WORLD = 'HalfKnifeSMP2026'
TARGET = WORLD + '/data/minecraft/world_gen_settings.dat'
APPLY = os.environ.get('END_REPAIR_APPLY', 'false').lower() == 'true'
RESET_OUTER = os.environ.get('END_REPAIR_RESET_OUTER', 'false').lower() == 'true'

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

def require_stopped(props):
    if os.environ.get('END_REPAIR_BACKUP_CONFIRMED', 'false').lower() != 'true':
        raise RuntimeError('A complete stopped-server backup must be confirmed first')
    log = read('logs/latest.log')
    text = log.decode('utf-8',errors='replace')
    stop = text.rfind('Stopping server')
    saved = text.rfind('All dimensions are saved')
    if stop < 0 or saved < stop or 'Done (' in text[stop:]:
        raise RuntimeError('No clean production shutdown confirmed in latest.log')
    host = 'halfknife2026.serverminer.com'
    port = int(props.get('server-port', '25565'))
    # Resolve first: a DNS error must never be mistaken for an offline server.
    addresses = socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
    for family, kind, proto, _, address in addresses:
        s = socket.socket(family,kind,proto)
        s.settimeout(5)
        try:
            if s.connect_ex(address) == 0:
                raise RuntimeError('Production game port is still accepting connections')
        finally:
            s.close()
    return digest(log)

def boot(probe=False):
    print('STARTING_ISOLATED_SERVER probe=' + str(probe), flush=True)
    output = []
    q = queue.Queue()
    process = subprocess.Popen(['java','-XX:ActiveProcessorCount=4','-Djava.util.concurrent.ForkJoinPool.common.parallelism=4','-Xms512M','-Xmx4G','-jar','server.jar','nogui'], cwd=ROOT,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    def consume():
        for line in process.stdout:
            output.append(line)
            q.put(line)
            if any(x in line for x in ('Downloading ', 'Starting minecraft server', 'Preparing start region', 'Done (', 'Stopping server')) and 'seed' not in line.lower():
                print('TEST_SERVER',line.rstrip(),flush=True)
            if '/ERROR]' in line and 'seed' not in line.lower():
                print('TEST_ERROR',line.rstrip(),flush=True)
            if probe and any(s in line for s in ('END_REPAIR_', 'nearest betterend:', 'not loaded', 'Marked chunk', 'Test failed')):
                print('TEST_PROBE',line.rstrip(),flush=True)
    thread = threading.Thread(target=consume, daemon=True)
    thread.start()
    def send(command):
        process.stdin.write(command + '\n')
        process.stdin.flush()
    def wait_for(predicate, seconds):
        deadline = time.monotonic() + seconds
        diagnostic_at = time.monotonic() + 60
        while time.monotonic() < deadline:
            if time.monotonic() > diagnostic_at:
                diagnostic_at = float('inf')
                try:
                    dump = subprocess.run(['jcmd',str(process.pid),'Thread.print'],capture_output=True,text=True,timeout=15).stdout
                    for name in ('main','Server thread'):
                        match = re.search(r'^"'+re.escape(name)+r'".*?(?=\n\n)',dump,re.M|re.S)
                        if match:
                            print('TEST_THREAD_DIAGNOSTIC',match.group(0)[:6500],flush=True)
                except Exception as error:
                    print('TEST_THREAD_DIAGNOSTIC_UNAVAILABLE',type(error).__name__,flush=True)
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
            send(f'execute in minecraft:the_end run forceload add {x} {z}')
            wait_for(lambda line:'Marked chunk' in line or 'already marked' in line, 45)
            # locate biome samples the generator without loading terrain. The biome
            # command needs a loaded chunk; wait for real chunk generation first.
            loaded = False
            for attempt in range(90):
                send(f'execute in minecraft:the_end if loaded {x} {y} {z} run say END_REPAIR_CHUNK_LOADED')
                deadline = time.monotonic() + 1
                while time.monotonic() < deadline:
                    try:
                        line = q.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if 'END_REPAIR_CHUNK_LOADED' in line:
                        loaded = True
                        break
                if loaded:
                    break
                if process.poll() is not None:
                    raise RuntimeError('Test server exited during chunk generation')
            if not loaded:
                raise RuntimeError('Located BetterEnd chunk did not load')
            send(f'execute in minecraft:the_end positioned {x} {y} {z} if biome ~ ~ ~ betterend:glowing_grasslands run say END_REPAIR_BIOME_PASS')
            wait_for(lambda line:'END_REPAIR_BIOME_PASS' in line, 45)
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
    if APPLY:
        require_stopped(props)
    end_plan = end_regions.inventory(FTP, WORLD)
    print('OUTER_END_PLAN',json.dumps(end_regions.summary(end_plan)),flush=True)
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
    # Read the End template directly from the exact installed nested WoVer JAR.
    templates = []
    def inspect_jar(raw, depth=0):
        if depth > 4:
            raise RuntimeError('Unexpected nested mod depth')
        with zipfile.ZipFile(io.BytesIO(raw)) as jar:
            for name in jar.namelist():
                if '/worldgen/world_preset/' in name and name.endswith('/normal.json'):
                    preset = json.loads(jar.read(name))
                    end = preset.get('dimensions',{}).get('minecraft:the_end',{})
                    g = end.get('generator',{})
                    if str(g.get('biome_source',{}).get('type','')).startswith('wover:'):
                        templates.append(g)
                elif name.endswith('.jar'):
                    inspect_jar(jar.read(name),depth+1)
    inspect_jar((ROOT/'mods/worldweaver-26.201.4.jar').read_bytes())
    unique = {json.dumps(g,sort_keys=True):g for g in templates}
    if len(unique) != 1:
        raise RuntimeError('Cannot uniquely resolve installed WoVer End template')
    template_json = next(iter(unique.values()))
    print('INSTALLED_END_TEMPLATE',json.dumps(template_json),flush=True)
    # Produce initialized metadata using a synthetic vanilla flat test world. Never
    # export production level.dat, datapack contents, terrain, entities or player data.
    flat_settings = {'biome':'minecraft:plains','layers':[{'block':'minecraft:bedrock','height':1},
        {'block':'minecraft:dirt','height':2},{'block':'minecraft:grass_block','height':1}],
        'features':False,'lakes':False,'structure_overrides':[]}
    (ROOT/'server.properties').write_text('server-ip=127.0.0.1\nserver-port=0\nonline-mode=false\nview-distance=2\nsimulation-distance=2\nlevel-name=test-world\nlevel-type=minecraft:flat\nlevel-seed=7261126\nspawn-protection=0\ngenerator-settings='+json.dumps(flat_settings)+'\n')
    (ROOT/'mods').rename(ROOT/'bootstrap-disabled-mods')
    try:
        boot()
    finally:
        # Fabric may create the empty mods directory during vanilla bootstrap.
        if (ROOT/'mods').exists():
            (ROOT/'mods').rmdir()
        (ROOT/'bootstrap-disabled-mods').rename(ROOT/'mods')
    test_path = ROOT/'test-world/data/minecraft/world_gen_settings.dat'
    test_path.parent.mkdir(parents=True,exist_ok=True)
    template = nbtlib.parse_nbt(json.dumps(template_json))
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
    print('NBT_ROUNDTRIP_PASS_ONLY_END_GENERATOR_CHANGED',flush=True)
    test_path.write_bytes(candidate)
    boot(probe=True)
    saved = parse(test_path.read_bytes())
    assert str(saved['data']['dimensions']['minecraft:the_end']['generator']['biome_source']['type']).startswith('wover:')
    assert saved['data']['dimensions']['minecraft:overworld'] == dims['minecraft:overworld']
    assert saved['data']['dimensions']['minecraft:the_nether'] == dims['minecraft:the_nether']
    assert saved['data']['seed'] == tree['data']['seed']
    print('VERIFIED_ONLY_END_GENERATOR_CHANGED',flush=True)
    print('GENERATOR_TYPES',str(generator['type']),str(generator['biome_source']['type']),flush=True)
    public_template = copy.deepcopy(generator).unpack()
    if 'seed' in public_template['biome_source']:
        public_template['biome_source']['seed'] = 0
    print('GENERATOR_TEMPLATE',json.dumps(public_template,default=str),flush=True)
    print('ORIGINAL_SHA256',digest(original),flush=True)
    print('CANDIDATE_SHA256',digest(candidate),flush=True)
    if not APPLY:
        print('PREPARATION_PASS_NO_PRODUCTION_WRITES',flush=True)
    else:
        # Check the live inputs again after the entire isolated test.
        FTP.close()
        FTP.connect(os.environ['FTP_HOST'], int(os.environ.get('FTP_PORT') or '21'))
        FTP.login(os.environ['FTP_USER'], os.environ['FTP_PASSWORD'])
        first_log = require_stopped(props)
        if read(TARGET) != original:
            raise RuntimeError('Original world generation file changed during testing')
        current_mods = sorted(Path(n).name for n in FTP.nlst('mods') if n.endswith('.jar'))
        if current_mods != installed:
            raise RuntimeError('Production mod list changed during testing')
        time.sleep(10)
        if require_stopped(props) != first_log or read(TARGET) != original:
            raise RuntimeError('Production files are not stable; refusing to write')
        if end_regions.inventory(FTP, WORLD) != end_plan:
            raise RuntimeError('End region inventory changed during testing')
        from datetime import datetime, timezone
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        directory = 'maintenance-backups'
        try:
            FTP.mkd(directory)
        except ftplib.error_perm:
            FTP.cwd(directory)
            FTP.cwd('..')
        directory += '/end-generator-' + stamp
        FTP.mkd(directory)
        backup = directory + '/world_gen_settings.original.dat'
        FTP.storbinary('STOR '+backup,io.BytesIO(original))
        if read(backup) != original:
            raise RuntimeError('Backup byte verification failed')
        temporary = TARGET + '.end-repair-' + stamp + '.pending'
        kept_original = TARGET + '.before-end-repair-' + stamp
        FTP.storbinary('STOR '+temporary,io.BytesIO(candidate))
        if read(temporary) != candidate:
            raise RuntimeError('Candidate byte verification failed')
        if read(TARGET) != original or require_stopped(props) != first_log:
            raise RuntimeError('Final offline/input check failed')
        swapped = False
        original_moved = False
        region_journal = []
        try:
            FTP.rename(TARGET,kept_original)
            original_moved = True
            FTP.rename(temporary,TARGET)
            swapped = True
            actual = read(TARGET)
            if actual != candidate or parse(actual) != changed:
                raise RuntimeError('Installed file verification failed')
            if read(kept_original) != original:
                raise RuntimeError('Preserved original verification failed')
            if RESET_OUTER:
                def still_stopped():
                    if require_stopped(props) != first_log:
                        raise RuntimeError('Production server state changed')
                # Write the complete recovery map BEFORE moving any region.
                recovery = {'endRoot':end_plan['root'], 'archiveRoot':directory+'/outer-end',
                    'files':end_plan['move'], 'protected':end_plan['keep']}
                recovery_bytes = json.dumps(recovery,indent=2,sort_keys=True).encode()
                recovery_path = directory+'/outer-end-recovery.json'
                FTP.storbinary('STOR '+recovery_path,io.BytesIO(recovery_bytes))
                if read(recovery_path) != recovery_bytes:
                    raise RuntimeError('Recovery inventory verification failed')
                end_regions.archive(FTP,WORLD,end_plan,directory+'/outer-end',region_journal,still_stopped)
                print('OUTER_END_ARCHIVED_AND_MAIN_ISLAND_PRESERVED',json.dumps(end_regions.summary(end_plan)),flush=True)
        except Exception:
            region_error = None
            try:
                end_regions.rollback(FTP,region_journal)
                if end_regions.inventory(FTP,WORLD) != end_plan:
                    raise RuntimeError('End inventory mismatch after rollback')
            except Exception as error:
                region_error = error
            if swapped:
                FTP.rename(TARGET,TARGET+'.failed-'+stamp)
            if original_moved:
                FTP.rename(kept_original,TARGET)
            if read(TARGET) != original:
                raise RuntimeError('ROLLBACK REQUIRES MANUAL ATTENTION')
            if region_error is not None:
                raise RuntimeError('REGION ROLLBACK REQUIRES MANUAL ATTENTION') from region_error
            raise
        manifest = {'status':'applied-awaiting-server-start','originalSha256':digest(original),
            'candidateSha256':digest(candidate),'target':TARGET,'backup':backup,
            'preservedOriginal':kept_original,'changedPath':'data.dimensions.minecraft:the_end.generator',
            'chunksEdited':False,'outerRegionsArchived':len(region_journal),
            'outerArchive':directory+'/outer-end' if RESET_OUTER else None,
            'playerDataEdited':False,'dragonStateEdited':False}
        FTP.storbinary('STOR '+directory+'/manifest.json',io.BytesIO(json.dumps(manifest,indent=2).encode()))
        print('END_REPAIR_APPLIED_AND_VERIFIED',json.dumps(manifest),flush=True)
finally:
    FTP.close()
