# Distribution

Presenteriyaki's application code is MIT licensed. Bundled libraries retain their
own licenses. Packages include dependency notices and version metadata under
`licenses/dependencies`.

## Dependencies and source

Qt/PySide libraries are dynamically bundled. The source tree, lockfile and build
specification support rebuilding with modified compatible libraries. Replacing
libraries in a Mac bundle may require re-signing it. Presenteriyaki imposes no
restriction on reverse engineering for debugging modified LGPL components.

- [Qt 6.12.0 source](https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/)
- [PySide/Shiboken source](https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.12.0)
- [Qt WebEngine source](https://code.qt.io/cgit/qt/qtwebengine.git/)
- [FFmpeg source and licensing](https://ffmpeg.org/legal.html)
- [Python source and licensing](https://docs.python.org/3/license.html)

`scripts/collect_notices.py` collects installed package notices, Python's license,
and the actual FFmpeg version, configuration, license texts and attribution.
`native-runtime.json` records notice hashes, which the package check verifies.

The packaged notice index also includes inventories from ten Qt 6.12.0 source
archives, the 125 third-party license pages published for WebEngine 6.140.0,
and cryptography's Cargo.lock dependencies. Source archive and crate checksums,
documentation page hashes, and source URLs are retained in `bundle/notices`.
The native inventory records Python's standalone build recipe, both OpenSSL
versions and Rust standard-library source revisions separately.

For source-based attribution inventories, verify the downloaded archive against
Qt's published checksum, then run:

```sh
uv run python scripts/collect_qt_source_notices.py qtbase-everywhere-src-6.12.0.tar.xz \
  --module qtbase --version 6.12.0 --output build/qtbase-notices.json
```

The output preserves attribution metadata, copyright files and referenced license
texts with the archive hash. Review it against the packaged file inventory before
adding notices to a release.

The packaged file inventory is checked separately. Presenteriyaki uses Qt Widgets;
its build omits the unused QML plugin tree, QML debugging tools and Qt Virtual
Keyboard plugin. The check rejects accidental inclusion of unrelated Qt Charts,
Data Visualization, Graphs and Quick 3D libraries. This keeps unnecessary modules
out of both the download and the dependency audit.

Mac release builds use uv-managed Python. The bundle declares the greater of its
Python and Qt deployment targets, and `payload.json` records every Mach-O target
above that declaration. Qt declares 14.4, but the current PySide/Shiboken wheels
contain bindings targeting 26.0. Packaged tests passed on macOS 15.7.9 despite
that discrepancy; support on macOS 14.4 is not established. Resolve the wheel
metadata discrepancy and test the minimum supported OS before a stable release.
See [contributor instructions](../CONTRIBUTING.md#releases) for Developer ID
signing and notarization. Windows development installers are currently unsigned.

## Native browser

Qt WebView uses the operating system's WebKit on macOS and Microsoft's WebView2
Runtime on Windows. Windows packages include a modified Qt WebView plugin under
LGPL-3.0-only; its complete source, patch and rebuild instructions accompany the
DLL. See [the dependency README](../bundle/native-webview/README.md).
Qt PDF still uses code from the WebEngine source module, so its relevant notices
remain included even though the Chromium browser runtime is omitted.

Windows Setup includes Microsoft's SHA-256-pinned, Authenticode-verified WebView2
bootstrapper. It checks the documented per-user and per-machine registry entries
and installs the shared runtime only when missing. An internet connection is
required for that download. Removing Presenteriyaki leaves this shared runtime
installed. See Microsoft's [deployment documentation](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution).

## Release checks

Before publishing application downloads:

1. Build and run the native tests and packaged checks on each supported target.
2. Include complete dependency notices and corresponding source/replacement
   information for the exact libraries shipped.
3. Package the applications for download and document their signing status.
4. Check installation, launch, updating and removal on ordinary user systems.
5. Publish the applications and concise release notes on GitHub Releases.

WebEngine/PDF have a separate version scheme: wheel version 6.12.0.140 reports
WebEngine 6.140.0 at runtime. Its public source and history are in the upstream
[`6.140.0` release branch](https://code.qt.io/cgit/qt/qtwebengine.git/?h=6.140.0),
including the Chromium submodule. The wheel metadata does not identify an exact
upstream Git build commit; the source references identify the supplier's version
and release branch. Presenteriyaki makes no changes to these library sources.
Refresh the source references and notice snapshots when updating dependencies.
