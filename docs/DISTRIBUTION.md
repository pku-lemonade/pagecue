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
metadata discrepancy and test the minimum supported OS before publication.
See [contributor instructions](../CONTRIBUTING.md#releases) for Developer ID
signing and notarization. Windows development installers are currently unsigned.

## Release checks

Before publishing application downloads:

1. Build and run the native tests and packaged checks on each supported target.
2. Include complete dependency notices and corresponding source/replacement
   information for the exact libraries shipped.
3. Package the applications for download and document their signing status.
4. Check installation, launch, updating and removal on ordinary user systems.
5. Publish the applications and concise release notes on GitHub Releases.

The remaining dependency audit concerns exact Qt WebEngine/Chromium source
correspondence and complete third-party attribution. The pinned WebEngine wheel
reports 6.140.0 separately from Qt 6.12.0; use the runtime metadata when checking
its source and notices. Current development builds are not yet public binary
releases.
