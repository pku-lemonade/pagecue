# Development

Use Python 3.13 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --frozen --python 3.13
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

- macOS: `dist/Presenteriyaki.app` (macOS 14 or later)
- Windows: `dist/Presenteriyaki/Presenteriyaki.exe`
- Installers: `dist/installers/` (`.dmg` on macOS, `-setup.exe` on Windows)

These include the Python and Qt runtime. macOS arm64, macOS Intel and Windows x64
are built separately.

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

The internal `PageCue` storage name and bundle identity are retained for existing
preferences and OS permissions. Keep those compatibility identifiers stable.

## Releases

Run the native checks, review [distribution requirements](docs/DISTRIBUTION.md),
and publish platform application downloads with release notes. Keep internal QA
logs, research notes and personal acceptance history out of release documentation.
