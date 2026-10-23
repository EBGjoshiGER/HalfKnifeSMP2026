import importlib.util
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location('sync_projects', Path(__file__).parents[1] / 'scripts/sync_projects.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ProjectsTest(unittest.TestCase):
    def setUp(self):
        self.config = {'requirements': {'minecraft:diamond': 100, 'minecraft:iron_ingot': 1000}, 'completionCommands': ['secret command']}
        self.progress = {'active': False, 'paused': False, 'completed': False, 'donated': {'minecraft:diamond': 25, 'minecraft:iron_ingot': 500}, 'playerNames': {'uuid': 'private'}}
    def test_status_precedence_matches_mods(self):
        for active, paused, completed, expected in [(False, False, False, 'not_started'), (False, True, False, 'not_started'), (True, False, False, 'active'), (True, True, False, 'paused'), (False, True, True, 'completed')]:
            self.progress.update(active=active, paused=paused, completed=completed)
            self.assertEqual(mod.snapshot(self.config, self.progress)['status'], expected)
    def test_public_counts_only(self):
        data = mod.snapshot(self.config, self.progress, datetime(2026,10,24,tzinfo=timezone.utc))
        self.assertEqual(data['resources'][0]['name'], 'Diamanten')
        self.assertEqual(data['resources'][0]['donated'], 25)
        self.assertNotIn('secret', json.dumps(data))
        self.assertNotIn('uuid', json.dumps(data))
    def test_missing_or_invalid_counts_fail_instead_of_showing_zero(self):
        for value in [None, -1, True, '10', 1.5]:
            self.progress['donated']['minecraft:diamond'] = value
            with self.assertRaises(ValueError): mod.snapshot(self.config, self.progress)
    def test_ftp_collect_only_uses_retr_for_both_projects(self):
        config, progress = self.config, self.progress
        class FTP:
            def __init__(self): self.commands = []
            def retrbinary(self, command, callback):
                self.commands.append(command)
                callback(json.dumps(config if command.endswith('/config.json') else progress).encode())
        ftp = FTP()
        self.assertEqual(set(mod.collect(ftp)), {'nether', 'end'})
        self.assertEqual(ftp.commands, ['RETR config/netherproject/config.json', 'RETR config/netherproject/progress.json', 'RETR config/endproject/config.json', 'RETR config/endproject/progress.json'])

if __name__ == '__main__': unittest.main()
