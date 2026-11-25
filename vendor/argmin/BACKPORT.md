# argmin 0.11.0: maintained macro dependency

Retain the complete checksum-verified upstream crate and its API. Replace the paste dependency with maintained pastey 0.2.3 through a dependency alias; optimization algorithms are unchanged.

BACKPORT-FILES.json records the original archive checksum and every original/local file hash. This is a local compatibility patch, not a new upstream version. Keep original licenses and this record in notices and source exports. The replacements were reviewed against official source commits; review evidence is retained locally.

Owner: TimeScope maintainer. Remove this patch after compatible upstream dependencies adopt maintained macros, with statistics tests (Argmin), or native Linux compilation, GLib iterator regressions and GUI tests (GLib/GTK) passing. Compiler diagnostic wording may differ.
