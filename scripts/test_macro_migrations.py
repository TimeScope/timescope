import hashlib, json, unittest, tomllib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
LEDGERS = {'argmin': '915114bab25f27d5936b67f1deb85b2594d97c48351f7cbe3008f7b1d65b2418'}
class MacroMigrations(unittest.TestCase):
    def test_exact_reviewed_source_ledgers(self):
        for name, expected in LEDGERS.items():
            folder=ROOT/'vendor'/name
            ledger=json.loads((folder/'BACKPORT-FILES.json').read_text())
            self.assertEqual(hashlib.sha256(json.dumps(ledger,sort_keys=True,separators=(',',':')).encode()).hexdigest(),expected)
            changed=[]
            for row in ledger['files']:
                self.assertEqual(hashlib.sha256((folder/row['path']).read_bytes()).hexdigest(),row['local_sha256'])
                if row['local_sha256'] != row['upstream_sha256']: changed.append(row['path'])
            self.assertEqual(changed,['Cargo.toml','Cargo.toml.orig'])
            expected_files = {r['path'] for r in ledger['files']} | {r['path'] for r in ledger.get('additional_upstream_files', [])} | {'BACKPORT.md', 'BACKPORT-FILES.json'}
            self.assertEqual({p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}, expected_files)
            for row in ledger.get('additional_upstream_files',[]):
                self.assertEqual(hashlib.sha256((folder/row['path']).read_bytes()).hexdigest(),row['sha256'])
    def test_lock_excludes_retired_macro_and_rejected_fork(self):
        packages=tomllib.loads((ROOT/'Cargo.lock').read_text())['package']
        self.assertFalse(any(p['name'] in ['paste','proc-macro-error2'] for p in packages))
        versions={p['name']:p['version'] for p in packages}
        self.assertEqual(versions['async-executor'],'1.14.1')
        self.assertEqual(versions['clipboard-win'],'5.4.3')
        self.assertEqual(versions['pastey'],'0.2.3')
if __name__ == '__main__': unittest.main()
