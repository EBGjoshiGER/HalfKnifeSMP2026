import unittest
from scripts.sync_projects import snapshot, END_STAGES

class EndStageExportTest(unittest.TestCase):
    def test_only_active_stage_is_published(self):
        targets = {item: 2 for group in END_STAGES for item in group}
        config = {'requirements': targets}
        state = {'active': False, 'paused': False, 'completed': False, 'donated': dict.fromkeys(targets, 0)}
        self.assertEqual(snapshot(config, state, staged=True)['resources'], [])
        state['active'] = True
        for n, group in enumerate(END_STAGES):
            result = snapshot(config, state, staged=True)
            self.assertEqual(result['currentStage'], n + 1)
            self.assertEqual([r['id'] for r in result['resources']], group)
            for item in group: state['donated'][item] = 2
        state['completed'] = True
        self.assertEqual(snapshot(config, state, staged=True)['resources'], [])

    def test_future_legacy_counts_and_custom_goals(self):
        config = {'requirements': {'minecraft:netherrack': 2, 'minecraft:ancient_debris': 2, 'minecraft:diamond': 2}}
        state = {'active': True, 'paused': False, 'completed': False,
                 'donated': {'minecraft:netherrack': 0, 'minecraft:ancient_debris': 2, 'minecraft:diamond': 0}}
        self.assertEqual([r['id'] for r in snapshot(config, state, staged=True)['resources']], ['minecraft:netherrack'])
        state['donated']['minecraft:netherrack'] = 2
        self.assertEqual([r['id'] for r in snapshot(config, state, staged=True)['resources']], ['minecraft:diamond'])
