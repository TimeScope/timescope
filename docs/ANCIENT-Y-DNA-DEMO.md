# Ancient Y-DNA · Eurasian subclades

Open **Help → Demo datasets → Ancient Y-DNA · Eurasian subclades**. The bundled
workspace is `samples/ancient-y-eurasian-subclades.chronoscope`; opening it creates
an editable copy with all data available offline.

The demo contains **1,708 dated records**, 78 branch/confidence labels, and 1,031
conservative matches to AADR v66.p1 metadata. It starts on a Eurasian globe in
the 12,000–2,000 years BP window. Saved views include Europe, the steppe and
Siberia, East Asia, and the Caucasus/West Asia in Time, historical periods, all
dated records, a consistent-AADR-nomenclature subset, and resolved branches.

## Sources and credit

- Freeman, Brimacombe & Elhaik (2020), [aYChr-DB](https://doi.org/10.1093/nargab/lqaa081),
  version 5: 1,797 published ancient Eurasian Y records; **CC BY 4.0**. Original
  specimen IDs, coordinates, calendar dates, haplogroups and study references
  remain attached. Of these, 74 lack calendar ages and 15 have only open-ended
  dates; these 89 records are excluded from the timeline.
- Mallick & Reich, [Allen Ancient DNA Resource](https://doi.org/10.7910/DVN/FFIDCW),
  **v66.p1, 1240K metadata; CC0 1.0**, accessed through the pinned
  [Poseidon metadata package](https://github.com/poseidon-framework/aadr-archive/tree/7406a4162bbde48dbae41dc8e68381a30ce0116e/AADR_v66_p1_1240K).
  The v62 annotation table is used only to bridge retired identifiers.
- Mallick et al. (2024), [The Allen Ancient DNA Resource (AADR) a curated compendium
  of ancient human genomes](https://doi.org/10.1038/s41597-024-03031-7), *Scientific
  Data* 11:182, provides the accompanying methodological citation.

Source and transformation credits are embedded in the workspace and its
attribution sidecar. Underlying study references and AADR publication DOIs remain
available on individual records.

## What the map means

Colors distinguish reported paternal branches. Full subclades and terminal SNP
labels are available in attributes such as `y_assignment_selected`,
`y_aadr_terminal_mutation` and `y_full_label`. Point height in Time and Globe Time
Height represents date, not physical altitude.

These are sampled individuals, not population frequencies or directly observed
migration journeys. Historical-period views are chronological slices, not
assignments of every person to a culture, language, ethnicity or migration.
Uneven excavation, preservation and sequencing affect the distribution. Shared
site coordinates overlap; the number of visible map marks need not equal the
number of records. The basemap uses modern geography, not reconstructed shores.

Calendar BC/AD ranges use a midpoint solely as a display anchor. Original date
strings and interval endpoints are retained. The workbook's raw radiocarbon BP
field is not treated as a calibrated calendar age. BP is relative to **1950**.
TimeScope currently displays signed calendar years on its deep-time rail.

### Assignment and matching policy

Match normalized exact specimen identifiers, with a unique v62 identifier bridge
where needed. Require a genetic male and AADR assessment **Pass**, coordinates
within 50 km, and a compatible calendar age within a tolerance of the larger of
500 years or twice the AADR date standard deviation. Require one individual and
compatible nested calls across accepted representations; retain original calls
for four records with conflicting representation calls. Numeric-only IDs are
not enough to establish a match.

Prefer usable curated manual ISOGG assignments, otherwise AADR automatic ISOGG
v15.73 calls. Select the highest 1240k SNP-count representation among consistent
candidates; that count is not Y-chromosome coverage. This workflow does not
reanalyse sequence reads. Original and AADR labels, identifiers, QC and source
DOIs remain distinguishable. Broad calls remain **Unresolved**. Tildes and question
marks remain **tentative**. Legacy C3/C6, N3 and O3 labels are flagged rather than
silently mapped across historical trees. The AADR-only saved view uses one
annotation system for its 1,031 matched records.

## Reproduction

```sh
python3 scripts/fetch_data_assets.py --ancient-y-sources
python3 scripts/prepare_ancient_y_demo.py
```

The three source tables are pinned by revision, size and SHA-256 in
`assets/data-assets.json` and stay under ignored
`samples/public/source-snapshots/ancient-y/`. The generator uses only Python's
standard library and does not access the network. It emits the compact bundled
workspace, attribution, aggregate provenance. Large raw
tables and routine validation captures are not bundled or committed.
