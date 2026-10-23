"""Read saved Nether/End project state via FTP; never write to the server."""
import ftplib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path

NAMES = {
    'minecraft:obsidian': 'Obsidian', 'minecraft:iron_ingot': 'Eisenbarren',
    'minecraft:gold_ingot': 'Goldbarren', 'minecraft:diamond': 'Diamanten',
    'minecraft:redstone': 'Redstone', 'minecraft:lapis_lazuli': 'Lapislazuli',
    'minecraft:blaze_rod': 'Lohenruten', 'minecraft:ender_pearl': 'Enderperlen',
    'minecraft:quartz': 'Netherquarz', 'minecraft:nether_quartz': 'Netherquarz', 'minecraft:glowstone_dust': 'Glowstonestaub',
    'minecraft:magma_cream': 'Magmacreme', 'minecraft:ghast_tear': 'Ghasttränen',
    'minecraft:crying_obsidian': 'Weinender Obsidian', 'minecraft:ancient_debris': 'Antiker Schrott',
}

def snapshot(config, progress, now=None):
    if not isinstance(config, dict) or not isinstance(progress, dict):
        raise ValueError('Expected project objects')
    targets, donated = config.get('requirements'), progress.get('donated')
    if not isinstance(targets, dict) or not targets or not isinstance(donated, dict):
        raise ValueError('Missing project resources')
    for key in ('active', 'paused', 'completed'):
        if type(progress.get(key)) is not bool:
            raise ValueError('Missing project status')
    resources = []
    for item, required in targets.items():
        count = donated.get(item)
        if (not isinstance(item, str) or type(required) is not int or
                not 0 < required <= 2**53 - 1 or type(count) is not int or not 0 <= count <= 2**53 - 1):
            raise ValueError('Invalid project resource count')
        resources.append({'id': item, 'name': NAMES.get(item, item), 'required': required, 'donated': count})
    # Same precedence and equal weighting of resource goals as both server mods.
    status = ('completed' if progress['completed'] else 'not_started' if not progress['active']
              else 'paused' if progress['paused'] else 'active')
    return {'schemaVersion': 1, 'syncedAt': (now or datetime.now(timezone.utc)).isoformat(),
            'status': status, 'resources': resources}

def read_json(ftp, path):
    data = io.BytesIO()
    ftp.retrbinary('RETR ' + path, data.write)
    return json.loads(data.getvalue().decode('utf-8-sig'))

def collect(ftp):
    result = {}
    for project in ('nether', 'end'):
        folder = f'config/{project}project'
        result[project] = snapshot(read_json(ftp, folder + '/config.json'),
                                   read_json(ftp, folder + '/progress.json'))
    return result

def main():
    with ftplib.FTP(timeout=30) as ftp:
        ftp.connect(os.environ['FTP_HOST'], int(os.environ.get('FTP_PORT') or '21'))
        ftp.login(os.environ['FTP_USER'], os.environ['FTP_PASSWORD'])
        projects = collect(ftp)
    # Publish only validated public counters, never config commands or player UUIDs.
    Path('data').mkdir(exist_ok=True)
    for project, data in projects.items():
        path = Path(f'data/{project}-project.json')
        temporary = path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(path)
        print(f'{project}: {data["status"]}, {len(data["resources"])} resource goals')

if __name__ == '__main__':
    main()
