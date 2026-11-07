"""Reversible, whole-region outer End reset. No world file contents are exported."""
import re

KINDS = ('region', 'entities', 'poi')


def outer_file(name):
    match = re.fullmatch(r'r\.(-?\d+)\.(-?\d+)\.mca', name)
    divisor = 1
    if not match:
        match = re.fullmatch(r'c\.(-?\d+)\.(-?\d+)\.mcc', name)
        divisor = 32
    if not match:
        raise RuntimeError('Unrecognized End region file; refusing reset: ' + name)
    x, z = (int(v) // divisor for v in match.groups())
    # Four regions cover blocks [-512,511] in both axes, including the entire
    # main island, pillars, exit portal, gateway ring and surrounding void.
    return x not in (-1, 0) or z not in (-1, 0)


def entries(ftp, path):
    result = {}
    for name, facts in ftp.mlsd(path, facts=['type', 'size', 'modify']):
        if name in ('.', '..') or facts.get('type') in ('cdir', 'pdir'):
            continue
        if '/' in name or '\\' in name:
            raise RuntimeError('Unexpected listing entry')
        result[name] = dict(facts)
    return result


def file_identity(facts):
    if facts.get('type') != 'file' or not facts.get('modify') or 'size' not in facts:
        raise RuntimeError('Incomplete file metadata; refusing reset')
    return {'size': int(facts['size']), 'modify': facts['modify']}


def inventory(ftp, world):
    world_entries = entries(ftp, world)
    if 'DIM1' in world_entries:
        raise RuntimeError('Legacy End folder also exists; inspect before resetting')
    root = world + '/dimensions/minecraft/the_end'
    top = entries(ftp, root)
    if top.get('region', {}).get('type') != 'dir':
        raise RuntimeError('Expected current End region directory is missing')
    files, move, keep = {}, {}, {}
    for kind in KINDS:
        if kind not in top:
            continue
        if top[kind].get('type') != 'dir':
            raise RuntimeError('Expected End storage directory')
        for name, facts in entries(ftp, root + '/' + kind).items():
            rel = kind + '/' + name
            identity = file_identity(facts)
            files[rel] = identity
            (move if outer_file(name) else keep)[rel] = identity
    if not any(p.startswith('region/') for p in keep):
        raise RuntimeError('No main-island region files found; refusing reset')
    return {'root': root, 'files': files, 'move': move, 'keep': keep}


def summary(plan):
    return {'preservedBlockBounds': [-512, 511],
            'preservedFiles': len(plan['keep']),
            'outerFilesToArchive': len(plan['move']),
            'outerBytesToArchive': sum(v['size'] for v in plan['move'].values()),
            'outerFilesByKind': {k: sum(p.startswith(k + '/') for p in plan['move']) for k in KINDS}}


def archive(ftp, world, plan, directory, journal, check_stopped):
    """Caller rolls journal back on ANY failure, together with generator change."""
    if inventory(ftp, world) != plan:
        raise RuntimeError('End files changed after inspection')
    check_stopped()
    ftp.mkd(directory)
    for kind in KINDS:
        if any(p.startswith(kind + '/') for p in plan['move']):
            ftp.mkd(directory + '/' + kind)
    for i, (rel, identity) in enumerate(sorted(plan['move'].items())):
        if i % 20 == 0:
            check_stopped()
        source = plan['root'] + '/' + rel
        destination = directory + '/' + rel
        ftp.rename(source, destination)
        journal.append((source, destination, identity))
    after = inventory(ftp, world)
    if after['files'] != plan['keep']:
        raise RuntimeError('Protected regions differ or outer files remain')
    archived = {}
    for kind in KINDS:
        if any(p.startswith(kind + '/') for p in plan['move']):
            for name, facts in entries(ftp, directory + '/' + kind).items():
                archived[kind + '/' + name] = file_identity(facts)
    if archived != plan['move']:
        raise RuntimeError('Archived End files do not match original inventory')
    check_stopped()


def rollback(ftp, journal):
    for source, destination, _ in reversed(journal):
        ftp.rename(destination, source)
