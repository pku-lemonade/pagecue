# Development

Use Python 3.13 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --frozen --python 3.13 --managed-python
uv run presenteriyaki /path/to/slides.pdf
uv run pytest -q
```

The main interface uses Qt Widgets and custom painting. Qt PDF renders slides;
pypdf reads notes and metadata. Qt Multimedia handles media and camera input.
WebEngine is used for web content.

## Build the app

Build on the target operating system:

```sh
uv run python scripts/build_app.py
uv run python scripts/build_installer.py
```

Outputs:

- macOS: `dist/Presenteriyaki.app`
- Windows: `dist/Presenteriyaki/Presenteriyaki.exe`
- Installers: `dist/installers/` (`.dmg` on macOS, `-setup.exe` on Windows)

These include the Python and Qt runtime. macOS arm64, macOS Intel and Windows x64
are built separately.

Use uv-managed Python for release builds, as CI does. Homebrew Python may depend
on a newer macOS version. The app records the Python/Qt deployment target, and
the build inventories each included Mac binary's deployment target in
`build/payload.json`. See the compatibility caveat in
[distribution notes](docs/DISTRIBUTION.md). The package audit also
rejects unused QML plugin trees and unrelated Qt charting/3D libraries.

The Windows installer build requires [Inno Setup 6](https://jrsoftware.org/isinfo.php).
It installs for the current user and includes a Start Menu entry and uninstaller.
On macOS, open the disk image and drag the app to Applications. Close the app
before updating it. Development builds are not notarized or signed with a
trusted publisher certificate; downloaded builds may trigger an OS warning.

For a scripted local installation of the unpackaged build, run:

```sh
# macOS
uv run python scripts/install_app.py dist/Presenteriyaki.app

# Windows
uv run python scripts/install_app.py dist/Presenteriyaki
```

Close the installed app before updating it. `--check` verifies an installation;
`--uninstall` removes it while retaining preferences and documents.
Use Setup to update a Windows installation created by Setup, and Windows Settings
to remove it.

## Testing

Tests use original fixtures in `tests/fixtures`. Committed PDFs and videos allow
the suite to run without TeX or an FFmpeg command-line installation.

```sh
uv run python scripts/make_demo.py qa/demo.pdf
uv run python scripts/layout_smoke.py qa/demo.pdf qa/layout
uv run python scripts/check_bundle.py --output qa/packaged
uv run python scripts/check_installer.py --output qa/installer
```

Inspect rendered captures after changing the interface. The native CI workflow
tests and packages all three platform targets. Physical display, camera and tablet
checks are separate from automated tests.
The Windows installer check runs only on fresh CI runners because it creates
an uninstall entry and Start Menu shortcut.

Test browser video separately from native media. The pinned WebEngine build
decodes VP9/WebM but reports no H.264 support through `HTMLMediaElement.canPlayType`;
an MP4 `<video>` fails with `DEMUXER_ERROR_NO_SUPPORTED_STREAMS`. Native Qt
Multimedia MP4 decoding passes. Loading an HTML page alone does not establish
browser video playback: check decoded frame progress and media errors too.
Qt documents the required [WebEngine codec build option](https://doc.qt.io/qt-6/qtwebengine-features.html#audio-and-video-codecs).
This remains a browser compatibility limitation in the preview.

The internal `PageCue` storage name and bundle identity are retained for existing
preferences and OS permissions. Keep those compatibility identifiers stable.

## Releases

For a signed Mac build, set `PRESENTERIYAKI_CODESIGN_IDENTITY` to an installed
**Developer ID Application** certificate name or fingerprint before running
`scripts/build_app.py`. PyInstaller signs the app and its nested binaries with
the hardened runtime enabled. An Apple Development certificate is not sufficient.

After configuring a `notarytool` Keychain profile, run:

```sh
uv run python scripts/notarize_macos.py --profile presenteriyaki-notary
```

This submits the app to Apple, staples its ticket, builds and notarizes the DMG,
then checks both with Gatekeeper. Submission results remain in
`build/notarization/`. Credentials stay in Keychain; the command takes only the
profile name. Run the installer check against the resulting DMG before release.
See Apple's [notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow).

Run the native checks, review [distribution requirements](docs/DISTRIBUTION.md),
and publish platform application downloads with release notes. Keep internal QA
logs, research notes and personal acceptance history out of release documentation.

The native workflow's manual **Upload installers** option retains the tested
DMG and Setup files as `installer-*` artifacts. For an unsigned preview:

```sh
gh workflow run native.yml -f upload_installers=true
```

After all checks pass, create a draft prerelease targeting the tested commit.
Run the **Stage unsigned preview** workflow with that native run ID and version.
It transfers the installers within GitHub, adds `SHA256SUMS.txt`, and checks the
uploaded-file digests. It refuses to alter a published release or mix source
commits. Review the draft and its verification record before publishing.
