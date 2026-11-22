# Installation and preview status

[TimeScope 0.16.17](https://github.com/TimeScope/timescope/releases/tag/v0.16.17) is available for Apple Silicon macOS, Windows x64, and Ubuntu 24.04 amd64. The release assets retain the `chronoscope-` filename prefix, but the installed app is TimeScope.

## Current downloads

| Platform | Download | Installation and trust status |
| --- | --- | --- |
| Apple Silicon macOS (arm64) | [App archive](https://github.com/TimeScope/timescope/releases/download/v0.16.17/chronoscope-macos-arm64.tar.xz) | Extract the archive and copy `TimeScope.app` from the extracted `TimeScope` directory to Applications. Ad hoc signed, not Developer ID signed or notarized; Gatekeeper may block the download. No Intel Mac binary is included. |
| Windows x64 | [Installer ZIP](https://github.com/TimeScope/timescope/releases/download/v0.16.17/chronoscope-windows-x86_64.zip) | Extract the ZIP and run `TimeScope_0.16.17_x64-setup.exe` from the extracted `TimeScope` directory. The installer is unsigned. Microsoft Edge WebView2 Evergreen Runtime must already be installed; it is not bundled. |
| Ubuntu 24.04 amd64 (x86-64) | [Debian package ZIP](https://github.com/TimeScope/timescope/releases/download/v0.16.17/chronoscope-linux-ubuntu24.04-x86_64-deb.zip) | Extract the ZIP, open the extracted `TimeScope` directory in a terminal, and run `sudo apt install ./timescope_0.16.17_amd64.deb`. This is not an AppImage and uses Ubuntu's system GTK and WebKitGTK. Other distributions and architectures are not covered by this build's validation. |

The exact downloads passed GitHub-hosted desktop CLI, GUI engine startup, and attached MCP checks ([macOS](https://github.com/TimeScope/timescope/releases/download/v0.16.17/HOSTED-VALIDATION-macos-arm64.json) · [Windows](https://github.com/TimeScope/timescope/releases/download/v0.16.17/HOSTED-VALIDATION-windows-x86_64.json) · [Ubuntu](https://github.com/TimeScope/timescope/releases/download/v0.16.17/HOSTED-VALIDATION-linux-ubuntu24.04-x86_64-deb.json)). Ubuntu also passed APT dependency simulation. These checks do not establish clean installation or removal on real devices, macOS Gatekeeper acceptance, visible rendering, or physical GPU compatibility.

Use [SHA256SUMS.txt](https://github.com/TimeScope/timescope/releases/download/v0.16.17/SHA256SUMS.txt) to verify downloads and [RELEASE-MANIFEST.json](https://github.com/TimeScope/timescope/releases/download/v0.16.17/RELEASE-MANIFEST.json) for per-platform build provenance. Keep the accompanying notices and source-access instructions. The exact application source differs by platform: use [the Ubuntu and release-tag source](https://github.com/TimeScope/timescope/releases/download/v0.16.17/chronoscope-source.zip) for Ubuntu, and [the macOS and Windows source](https://github.com/TimeScope/timescope/releases/download/v0.16.17/chronoscope-source-a6d165e.zip) for those builds, even though their bundled instructions name the generic ZIP. See the [release notes](https://github.com/TimeScope/timescope/releases/tag/v0.16.17) for dependency sources, notices, and the limits of the Ubuntu WASM provenance.

The Apple model diagnostic requires macOS 26+; Apple Intelligence is not an SI Chat provider.

## Historical previews and disclosures

The [0.16.16 Windows release](https://github.com/TimeScope/timescope/releases/tag/v0.16.16) and [0.16.15 preview](https://github.com/TimeScope/timescope/releases/tag/v0.16.15) remain available. 0.16.16 re-enabled Charts and added editable chart axes, compact pane navigation, notification dismissal, and persistent background visibility controls. Its [hosted validation receipt](https://github.com/TimeScope/timescope/releases/download/v0.16.16/HOSTED-VALIDATION-windows-x86_64.json) covers only the tested package and environment. For 0.16.15, bounded source/native-string/hosted-web scans and file inventories found no user-specific credentials; the payload review records Cesium’s original evaluation default token.

The [0.16.14 experimental preview](https://github.com/TimeScope/timescope/releases/tag/v0.16.14) had Charts and Patterns disabled on Mac and Linux. Its Linux AppImage was tested on Ubuntu 26.04.1 with glibc 2.43; older distributions were not verified. Its GnuTLS dependency had two upstream-disputed certificate-validation reports with deferred Ubuntu fixes. The online update check passed; no malicious-server acceptance in Chronoscope was demonstrated. The 0.16.14 Windows diagnostic strings retain a disclosed generic public dependency-cache path. See that release's security disclosure and native security receipt, [source mapping](https://github.com/TimeScope/timescope/releases/download/v0.16.14/SOURCE-PARITY.json), and [local acceptance scope](validation/release-0.16.14-publication/README.md), which includes offline views, queries, and save/reopen on Mac and Linux. Back up projects before preview testing.

See the [release checklist](RELEASE-CHECKLIST.md), [distribution obligations](DISTRIBUTION.md), [local build procedure](LOCAL-RELEASES.md) and [local security checks](SECURITY-CHECKS.md).

## Build from source

Desktop: **Rust 1.96+**, **Node 22+**, and [Tauri v2 platform prerequisites](https://v2.tauri.app/start/prerequisites/). CLI-only core declares Rust **1.96+** and needs neither Node nor a window system. Locked dependencies can impose newer compiler requirements; the local verification compiler is recorded separately, not a minimum-version test.

- macOS: Xcode 27.2 / macOS SDK 27.2 for the recorded local preview build (native compilation remains the gate); see [Mac handoff](MAC_HANDOFF.md).
- Windows: MSVC C++ build tools/Windows SDK and WebView2, as described by Tauri.
- Linux: WebKitGTK 4.1/GTK3 development prerequisites and platform linker tools; consult Tauri and the manual workflow package list. Do not install packages merely to run the CLI.

Use [README commands](../README.md). For distributable builds use `python3 scripts/build_portable.py build --locked --release -p chronoscope --bin timescope` or `python3 scripts/build_portable.py -- npm run bundle` to remap repository/Cargo/home compiler paths. Existing effective environment flags are preserved and remaps appended. `RUSTFLAGS` follows Cargo’s whitespace splitting: quotes are literal and backslashes (including Windows paths) are not shell-unescaped. If an individual argument contains spaces, use `CARGO_ENCODED_RUSTFLAGS` with a literal unit separator (U+001F) between arguments; it takes precedence over `RUSTFLAGS`. For example in Python: `env["CARGO_ENCODED_RUSTFLAGS"] = "\x1f".join(["-C", r"link-arg=C:\SDK Folder\foo.lib"])`. If using target-specific Cargo configuration, pass its effective rustflags via `CARGO_ENCODED_RUSTFLAGS` (or `RUSTFLAGS`) first: Cargo environment flags override configured flags. The wrapper does not edit configuration and refuses implicit configured flags rather than dropping them. Verify final binary strings and notices; Rust remapping alone does not cover Swift/linker/generated resources or old published binaries.

## Appearance and existing installations

The running Mac Dock and Windows window icons follow the selected appearance; Finder/Explorer/pinned shortcuts can retain the packaged pearl icon. Linux uses the pearl fallback.

Default settings and automatic document copies migrate once from former Chronoscope Cesium folders. Close the earlier app first; see [profile migration](MAC_HANDOFF.md#settings-and-automatic-document-copies). Explicit `--data-dir` profiles are not migrated. Regenerate external client setup from Preferences → MCP setup at the final installed location.
