# Rstar 0.12.2: remove the affected heapless dependency

The complete crates.io `rstar` 0.12.2 archive is retained here. Its SHA-256,
every original file hash, and the three modified file hashes are recorded in
`BACKPORT-FILES.json`. The upstream version remains 0.12.2.

Change: use `alloc::collections::BinaryHeap` throughout nearest-neighbor search,
extending the implementation's existing allocation-backed fallback. Remove the
32-entry heapless optimization and its dependency from both Cargo manifests.
The crate retains `#![forbid(unsafe_code)]` and `no_std` + alloc support. Tree
construction, geometry, comparison order and public APIs are unchanged. Small
nearest-neighbor searches now allocate; measure their performance when reviewing
this patch. Empty searches do not allocate.

Reason: heapless 0.8.0 has nine RustSec unsoundness advisories,
RUSTSEC-2026-0574 through RUSTSEC-2026-0582. The latest geo 0.33.1 still selects
rstar 0.12, while rstar 0.14 permits heapless 0.9. The 0.8 to 0.9 migration changes
substantial collection internals. This local change eliminates heapless from the
TimeScope graph without changing the geographic library APIs or introducing new
collection code. It does not assert that every advisory was reachable through
rstar's former use of BinaryHeap.

The published crate omitted its referenced license files. LICENSE-MIT and
LICENSE-APACHE are retained from the exact official repository commit recorded
in `.cargo_vcs_info.json`; their source URLs and hashes are in the ledger.
Keep these licenses and this modification record in app notices and source
exports.

Verification: `python3 scripts/test_rstar_backport.py` checks provenance and the
locked graph. `cargo test --locked --manifest-path tests/rstar-backport/Cargo.toml`
checks nearest-neighbor, complete ordered traversal, ties, empty trees and
remove/reinsert behavior against brute-force results. Its `measure` example
provides a reproducible comparison with the unmodified archive.

Owner: TimeScope maintainer. Remove this local patch when a compatible released
geographic stack no longer brings in affected heapless, after the unchanged
spatial tests, representative measurements and native app checks pass. Do not
suppress advisories or widen test tolerances to retire it.
