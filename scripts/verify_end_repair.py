"""Read-only verification of the repaired live End after server startup."""
import copy
import ftplib
import gzip
import hashlib
import io
import json
import os
import re
import nbtlib
import end_regions

WORLD = 'HalfKnifeSMP2026'
BACKUP = 'maintenance-backups/end-generator-20261107T085831Z'
ftp = ftplib.FTP(timeout=60)


def read(path, limit=16*1024*1024):
    buf = io.BytesIO()
    def recv(chunk):
        if buf.tell()+len(chunk) > limit:
            raise RuntimeError('Verification read exceeded size limit')
        buf.write(chunk)
    ftp.retrbinary('RETR '+path,recv)
    return buf.getvalue()


def parse(raw):
    return nbtlib.File.parse(io.BytesIO(gzip.decompress(raw)))


try:
    ftp.connect(os.environ['FTP_HOST'],int(os.environ.get('FTP_PORT') or '21'))
    ftp.login(os.environ['FTP_USER'],os.environ['FTP_PASSWORD'])
    manifest = json.loads(read(BACKUP+'/manifest.json'))
    recovery = json.loads(read(BACKUP+'/outer-end-recovery.json'))
    original_raw = read(BACKUP+'/world_gen_settings.original.dat')
    assert hashlib.sha256(original_raw).hexdigest() == manifest['originalSha256']
    original = parse(original_raw)
    current_raw = read(WORLD+'/data/minecraft/world_gen_settings.dat')
    current = parse(current_raw)
    generator = current['data']['dimensions']['minecraft:the_end']['generator']
    assert str(generator['type']) == 'wover:betterx'
    assert str(generator['biome_source']['type']) == 'wover:end_biome_source'
    restored = copy.deepcopy(current)
    restored['data']['dimensions']['minecraft:the_end']['generator'] = copy.deepcopy(original['data']['dimensions']['minecraft:the_end']['generator'])
    assert restored == original, 'Unexpected change outside End generator'
    plan = end_regions.inventory(ftp,WORLD)
    assert set(recovery['protected']).issubset(plan['files']), 'Main island storage missing'
    archived = {}
    for kind in end_regions.KINDS:
        if any(p.startswith(kind+'/') for p in recovery['files']):
            for name, facts in end_regions.entries(ftp,BACKUP+'/outer-end/'+kind).items():
                archived[kind+'/'+name] = end_regions.file_identity(facts)
    assert archived == recovery['files'], 'Archive metadata differs from recovery inventory'
    log = read('logs/latest.log').decode('utf-8',errors='replace')
    start = log.rfind('Loading Minecraft ')
    if start >= 0:
        log = log[start:]
    done = log.rfind('Done (')
    assert done >= 0 and done > log.rfind('Stopping server'), 'No completed running startup'
    assert 'not a BetterEnd End biome source' not in log, 'Vanilla fallback is active'
    assert 'BetterEnd island terrain, cave biomes and End structures are DISABLED' not in log
    fatal = ('Failed to load level', 'Failed to start the minecraft server', 'Encountered an unexpected exception',
             'Exception in server tick loop', 'Failed to load worldgen settings')
    assert not any(s in log for s in fatal), 'Startup failure detected'
    lines = log.splitlines()
    evidence = []
    for i,line in enumerate(lines):
        if any(s in line for s in ('World Dimensions','not a BetterEnd','Starting minecraft server','Done (','Loading Minecraft ')):
            candidates = lines[i:i+20] if 'World Dimensions' in line else [line]
            for candidate in candidates:
                if not re.search(r'(?i)seed|password|token|secret|logged in|joined the game|\b(?:\d{1,3}\.){3}\d{1,3}\b',candidate):
                    evidence.append(candidate)
    print('LIVE_END_VERIFICATION',json.dumps({
        'startupComplete':True, 'vanillaFallbackWarning':False,
        'generator':str(generator['type']), 'biomeSource':str(generator['biome_source']['type']),
        'onlyEndGeneratorChanged':True, 'protectedFilesPresent':len(recovery['protected']),
        'archivedFilesVerified':len(archived), 'activeOuterFiles':len(plan['move']),
        'generatorFileMatchesInstalledBytes':hashlib.sha256(current_raw).hexdigest()==manifest['candidateSha256'],
        'startupEvidence':list(dict.fromkeys(evidence))[:90]
    },indent=2),flush=True)
    print('LIVE_END_VERIFICATION_PASS_READ_ONLY',flush=True)
finally:
    ftp.close()
