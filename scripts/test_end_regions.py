import copy
import unittest
import end_regions as er

WORLD = 'HalfKnifeSMP2026'
END = WORLD + '/dimensions/minecraft/the_end'


class FakeFTP:
    def __init__(self):
        self.dirs = {WORLD, END, *(END+'/'+k for k in er.KINDS), 'backup'}
        self.files = {}
        self.fail_after = None
        self.calls = 0
        for kind in er.KINDS:
            for x in range(-2, 2):
                for z in range(-2, 2):
                    self.files[f'{END}/{kind}/r.{x}.{z}.mca'] = {'type':'file','size':'8192','modify':'20261107080000'}

    def mlsd(self, path, facts=None):
        if path not in self.dirs:
            raise RuntimeError('missing directory')
        prefix = path+'/'
        out = []
        for directory in self.dirs:
            if directory.startswith(prefix) and '/' not in directory[len(prefix):]:
                out.append((directory[len(prefix):], {'type':'dir'}))
        for file, metadata in self.files.items():
            if file.startswith(prefix) and '/' not in file[len(prefix):]:
                out.append((file[len(prefix):],copy.deepcopy(metadata)))
        return out

    def mkd(self, path):
        if path in self.dirs:
            raise RuntimeError('already exists')
        self.dirs.add(path)

    def rename(self, source, target):
        self.calls += 1
        if self.fail_after == self.calls:
            raise RuntimeError('simulated rename failure')
        if source in self.dirs:
            if target in self.dirs or target in self.files:
                raise RuntimeError('unsafe directory rename')
            self.dirs = {target + p[len(source):] if p == source or p.startswith(source+'/') else p for p in self.dirs}
            self.files = {target + p[len(source):] if p.startswith(source+'/') else p: v for p,v in self.files.items()}
            return
        if source not in self.files or target in self.files:
            raise RuntimeError('unsafe rename')
        self.files[target] = self.files.pop(source)


class RegionTests(unittest.TestCase):
    def test_protected_boundaries_and_external_chunks(self):
        for x in (-1, 0):
            for z in (-1, 0):
                self.assertFalse(er.outer_file(f'r.{x}.{z}.mca'))
        for name in ('r.-2.0.mca','r.0.1.mca','c.-33.0.mcc','c.32.0.mcc'):
            self.assertTrue(er.outer_file(name))
        for name in ('c.-32.-32.mcc','c.-1.31.mcc','c.31.0.mcc'):
            self.assertFalse(er.outer_file(name))
        for name in ('level.dat','../r.0.0.mca','r.0.0.mca.tmp'):
            with self.assertRaises(RuntimeError): er.outer_file(name)

    def test_archive_and_full_restore(self):
        ftp = FakeFTP()
        original = copy.deepcopy(ftp.files)
        plan = er.inventory(ftp,WORLD)
        self.assertEqual(len(plan['keep']),12)
        self.assertEqual(len(plan['move']),36)
        journal = []
        er.archive(ftp,WORLD,plan,'backup/outer',journal,lambda:None)
        self.assertEqual(er.inventory(ftp,WORLD)['files'],plan['keep'])
        self.assertEqual(len(journal),18)
        er.rollback(ftp,journal)
        self.assertEqual(ftp.files,original)

    def test_partial_failure_restores_originals(self):
        for failure in range(1,19):
            with self.subTest(failure=failure):
                ftp = FakeFTP()
                original = copy.deepcopy(ftp.files)
                plan = er.inventory(ftp,WORLD)
                journal = []
                ftp.fail_after = failure
                with self.assertRaises(RuntimeError):
                    er.archive(ftp,WORLD,plan,'backup/outer',journal,lambda:None)
                er.rollback(ftp,journal)
                self.assertEqual(ftp.files,original)
                self.assertEqual(er.inventory(ftp,WORLD),plan)

    def test_changed_input_and_legacy_folder_abort(self):
        ftp = FakeFTP()
        plan = er.inventory(ftp,WORLD)
        ftp.files[END+'/region/r.2.2.mca'] = {'type':'file','size':'8192','modify':'20261107080000'}
        with self.assertRaises(RuntimeError):
            er.archive(ftp,WORLD,plan,'backup/outer',[],lambda:None)
        ftp.dirs.add(WORLD+'/DIM1')
        with self.assertRaises(RuntimeError): er.inventory(ftp,WORLD)


if __name__ == '__main__':
    unittest.main()
