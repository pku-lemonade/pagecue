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
