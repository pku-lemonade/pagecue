# Binary distribution and dependency sources

PageCue's original application code is MIT licensed. The application uses
unmodified dynamic libraries with their own licenses; the app license does not
replace those terms. `licenses/dependencies` includes installed package notices
and exact package/version metadata. The GPL text is included as part of the LGPL
terms; its presence does not relicense PageCue's original code.

## Source and replacement

Qt/PySide libraries are dynamically bundled, not statically linked into PageCue.
The source tree, lockfile and build specification allow rebuilding the app against
modified compatible libraries. Replacing native libraries in a Mac app may require
re-signing the resulting local bundle; ad-hoc signing needs no paid account.
No restriction on reverse engineering for debugging modified LGPL components is
imposed by PageCue.

Corresponding upstream source locations for the pinned unmodified libraries:

- Qt 6.12.0: https://download.qt.io/official_releases/qt/6.12/6.12.0/single/
- Qt module sources: https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/
- Qt for Python 6.12.0: https://download.qt.io/official_releases/QtForPython/pyside6/
- PySide/Shiboken source tag: https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.12.0
- FFmpeg sources/licensing: https://ffmpeg.org/download.html and https://ffmpeg.org/legal.html
- Python sources/licensing: https://www.python.org/downloads/source/ and https://docs.python.org/3/license.html

The actual Python, Qt and architecture versions are recorded by the packaged smoke
check. Package metadata lists source repositories for the remaining dependencies.
The exact runtime payload and third-party notices must be audited before a public
binary release; development bundles are not yet a release-compliance sign-off.

The installed WebEngine module reports **6.140.0**, Chromium **140.0.7339.225**,
and security-patch version **152.0.7977.83** through its Qt runtime APIs, while
`qVersion()` reports Qt **6.12.0**. Treat those as distinct version identifiers in
the audit; a Qt 6.12 source pointer alone has not established complete source
coverage for this payload. The Qt wheels contain no discoverable standalone
license/attribution files, and `chrome://credits` did not load in the local build.
The public licensing page redirects to the separate WebEngine documentation;
collect matching third-party notices and verify exact source correspondence before
publishing a binary. These are recorded gaps, not completed release checks.

The [official separation announcement](https://www.qt.io/blog/qt-webengine-will-release-separate)
and [PySide 6.12 announcement](https://www.qt.io/blog/qt-for-python-release-6.12-is-here)
explain this split: WebEngine/PDF use a separate release cycle and the Python wheel
version combines Qt's version with the Chromium major (`6.12.0.140`). On
2026-10-25 the public source index exposed
[6.140.0-rc](https://download.qt.io/development_releases/qtwebengine/6.140.0-rc/)
and the official GitHub mirror's newest tag was `v6.140.0-rc` at
`d505fc23640d2bd6345e6483eb73daf4e19f5829`. No final `v6.140.0` tag was observed.
This identifies an available source candidate; it does **not** prove that the
wheel was built from it. The public WebEngine licensing page also currently
redirects to development snapshots. A fresh direct `chrome://credits` load via
QWebEngineView returned `loadFinished(false)`; it was not rejected by PageCue's URL
filter. Runtime correspondence and third-party notices remain unresolved.

## Build and test

```sh
uv sync --frozen
uv run python scripts/build_app.py
```

Build Windows and Mac packages on their respective OSes. The current Mac wheel
requires macOS 14 or newer. A Mac arm64 build does not imply Intel or Windows support.
The app is ad-hoc signed for local use; downloaded distributions can trigger OS
approval prompts. Do not disable platform protections to install it.

Run the real built executable with a PDF and `--smoke-output DIR`; add
`--smoke-media FILE` and `--smoke-web` to exercise the media and browser resources.
Inspect `DIR/result.json`, not only the process exit status. These checks do not
replace real camera and physical-display validation.

## Per-user installation and updates

`scripts/install_app.py` uses Python's standard library. Install the built Mac app
or Windows directory; the script chooses the per-user location documented in
README.md. It copies into a sibling staging directory and validates the staged
identity/executable (and Mac code signature) before replacing an existing PageCue
installation. Unknown apps and directory symlinks are rejected. A failed final
rename restores the old app; a failed restoration retains an explicit recovery
path. Close running instances before updating, especially on Windows.

`--check` validates the installed app, while `--uninstall` removes only its
identified bundle. Documents, preferences and PDF defaults are retained.
The Windows CLI creates a per-user Start Menu shortcut using Windows' shell-link
Unicode COM interface (`IShellLinkW`/`IPersistFile`) through Python's standard
`ctypes`; it does not launch a shell or change PDF associations. Existing links must match the
expected target and application description. `--no-shortcut` supports portable or
secondary installations. See [Microsoft's shell-link documentation](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nn-shobjidl_core-ishelllinkw).

The development Mac arm64 package has been installed, checked, updated, launched
from a Unicode/space-containing path, and removed. Its frozen executable passed
PDF/navigation/reload, muted media decoding and local WebEngine checks. Neither
physical-device acceptance nor an ordinary Windows/macOS user's first-launch OS
approval flow has been validated yet. The native CI workflow now exercises fresh
Windows Server 2025 and Mac runner environments. Its results/artifacts, rather
than the existence of the workflow, determine which platform checks passed.
