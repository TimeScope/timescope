#!/usr/bin/env python3
"""Offline provenance and graph guards; runtime coverage lives in the Rust harness."""
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib
import unittest

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / 'vendor/rstar'


class RstarBackport(unittest.TestCase):
    def test_reviewed_archive_and_exact_file_ledger(self):
        ledger = json.loads((VENDOR / 'BACKPORT-FILES.json').read_text())
        canonical = json.dumps(ledger, sort_keys=True, separators=(',', ':')).encode()
        self.assertEqual(hashlib.sha256(canonical).hexdigest(),
                         '7475ed4e86f6dfd98581777c875399ed0e8262871ab75d3717a7e4278929b6ee')
        expected = {'BACKPORT.md', 'BACKPORT-FILES.json'}
        changed = []
        for row in ledger['files']:
            expected.add(row['path'])
            data = (VENDOR / row['path']).read_bytes()
            self.assertEqual(len(data), row['local_bytes'], row['path'])
            self.assertEqual(hashlib.sha256(data).hexdigest(), row['local_sha256'], row['path'])
            if row['local_sha256'] != row['upstream_sha256']:
                changed.append(row['path'])
        self.assertEqual(changed, ['Cargo.toml', 'Cargo.toml.orig', 'src/algorithm/nearest_neighbor.rs'])
        for row in ledger['additional_upstream_files']:
            expected.add(row['path'])
            self.assertEqual(hashlib.sha256((VENDOR / row['path']).read_bytes()).hexdigest(), row['sha256'])
        self.assertEqual({p.relative_to(VENDOR).as_posix() for p in VENDOR.rglob('*') if p.is_file()}, expected)

    def test_locked_workspace_uses_backport_without_affected_packages(self):
        manifest = tomllib.loads((ROOT / 'Cargo.toml').read_text())
        self.assertEqual(manifest['patch']['crates-io']['rstar']['path'], 'vendor/rstar')
        lock = tomllib.loads((ROOT / 'Cargo.lock').read_text())['package']
        self.assertFalse(any(p['name'] in {'heapless', 'hash32'} for p in lock))
        rstar = [p for p in lock if p['name'] == 'rstar']
        self.assertEqual(len(rstar), 1)
        self.assertEqual(rstar[0]['version'], '0.12.2')
        self.assertNotIn('source', rstar[0])
        tree = subprocess.check_output(['cargo', 'tree', '--offline', '--locked', '--workspace', '-i', 'rstar'],
                                       cwd=ROOT, text=True)
        self.assertTrue(tree.startswith('rstar v0.12.2 (' + str(VENDOR) + ')'))

    def test_distribution_retains_licenses_and_modification_record(self):
        import package_notices
        javascript = (ROOT / 'scripts/package-notices.mjs').read_text()
        for name in ['vendor/rstar/LICENSE-MIT', 'vendor/rstar/LICENSE-APACHE', 'vendor/rstar/BACKPORT.md']:
            self.assertIn(name, package_notices.REQUIRED_FILES)
            self.assertIn('"' + name + '"', javascript)


if __name__ == '__main__':
    unittest.main()
