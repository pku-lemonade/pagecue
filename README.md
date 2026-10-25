# PageCue

A Qt/PySide rewrite of the PDF-presentation workflow, preserving a minimalist
presenter view and a separate audience screen. Independently implemented; no
Présentation source or artwork is included. PageCue is a working name.

**In development. Feature parity is not yet achieved.**
See [the feature ledger](docs/FEATURES.md) for implementation and verification status.

Development setup (Python 3.12–3.14 and [uv](https://docs.astral.sh/uv/)):

```sh
uv sync
uv run pagecue /path/to/slides.pdf
uv run pytest
```

The interface uses Qt Widgets and custom painting. Qt WebEngine is reserved for
the original presenter's web-content feature; it does not implement the main UI.
The existing Présentation and Présentation PDFPC installations are independent.

The keyboard-help panel scrolls when the window is small. Press **V** to toggle
the camera, **Shift+V** to expand it, and use **Media → Camera appearance…** to
adjust inset size, opacity and corner. Camera capture starts only after you request
it and grant the OS permission; device loss clears the preview. Camera appearance
is remembered between launches, while capture never starts automatically.

Double-click the audience view (or choose **View → Audience fullscreen**) to fill
its screen while keeping the presenter windowed. **F5** selects general fullscreen;
**Esc** returns both windows to their previous sizes. Hide/restore preserves the
selected fullscreen mode. Ctrl/⌘ + wheel zooms around the cursor; Ctrl/⌘ + drag
pans, and Ctrl/⌘ + 0 resets the slide or whiteboard view.
Use **+ / −** for notes or web zoom and **0** to reset it. Zero still works inside
a page number already being entered (for example, **1 0 Enter**).

Command-line options include `-p/--page` (1-based), `-d/--duration` (minutes),
`-y/--youtube/--direct-video`, `-v/--version`, and `-i/--icon [FILE]`.
For example, `uv run pagecue -p 2 -d 20 slides.pdf` starts on page two with a
20-minute timer. `uv run pagecue --icon icon.png` exports PageCue's own PNG icon
without opening a window. Omitting the filename writes binary PNG to stdout;
use a filename with the packaged Windows GUI executable, which has no console.

PageCue's original code is MIT licensed. Qt/PySide and other dependencies retain
their own licenses. Binary distribution must include the applicable notices and
Qt library source/replacement information. Packaging is still in development.

## Build and install with an agent

Give an agent this instruction:

> Install https://github.com/pku-lemonade/pagecue for my user. Read README.md,
> AGENTS.md and docs/DISTRIBUTION.md. Build PageCue using the
> pinned environment, run the checks, then install it for my user. Preserve my
> existing Présentation apps, PDF associations, slides and notes. Report actual
> results and any untested platform/device features.

The current development workflow requires Python 3.12–3.14 and `uv` for building.
The resulting application includes its Python/Qt runtime. Launching it does not
require activating a Python environment. A public binary release is not ready yet.

1. Clone the repository into an unused directory (or preserve local changes in
   an existing checkout). Check the OS and architecture, inspect the working tree,
   and run `uv sync --frozen`, then `uv run pytest -q`. Tests use original committed
   PDF/video fixtures when `pdflatex` or `ffmpeg` is unavailable; no decoder tests
   are skipped merely because fixture-generation tools are absent.
2. Run `uv run python scripts/build_app.py` on the target OS.
3. On macOS, run `uv run python scripts/install_app.py dist/PageCue.app`.
   On Windows, run `uv run python scripts/install_app.py dist/PageCue`.
   Close PageCue before installing an update. The same command updates an existing
   identified PageCue app; it refuses unrelated applications at the destination.
4. Run `uv run python scripts/install_app.py --check`, then launch the installed
   app with an original test PDF. Check both windows, notes and navigation.

Default destinations are `~/Applications/PageCue.app` on macOS and
`%LOCALAPPDATA%\Programs\PageCue` on Windows. Use `--destination PATH` to override.
On Windows use the PageCue Start Menu shortcut, or launch `PageCue.exe` inside
that directory. `--no-shortcut` leaves Start Menu entries untouched for portable
or secondary installations. Existing shortcuts for another installation are
preserved; the installer will report the conflict rather than replace them.

For automated packaged checks, pass a PDF plus `--smoke-output DIR` to the installed
executable, optionally adding `--smoke-media VIDEO --smoke-web`. Inspect the
result JSON and captures in that directory. Those checks use separate temporary
preferences and do not activate the camera or prove physical display behavior.

To remove the installed app, run `uv run python scripts/install_app.py --uninstall`
(and the same `--destination` if customized). Preferences and documents remain.
The installer never changes the default PDF viewer. It uses no administrator rights.
See [distribution notes](docs/DISTRIBUTION.md) for signing and dependency details.

## Native build verification

The GitHub Actions workflow targets Windows x64, Mac arm64 and Mac Intel. It runs
the tests, builds the app, installs it into a Unicode path, launches that executable
to exercise PDF/media/WebEngine, then verifies update/removal. It uploads JSON,
test reports and screenshots for review, without publishing an unaudited binary.
The presence of the workflow is not proof that any particular run/platform passed;
inspect the run's logs and evidence. Physical display/camera testing is separate.

The [verified implementation revision](https://github.com/pku-lemonade/pagecue/actions/runs/40174372319)
passes 72 tests on Windows x64 and Mac arm64/Intel. Its packaged apps also pass
PDF/media/web execution and Unicode-path installation checks. Windows shortcut lifecycle
checks also pass. Windows evidence is from a
Windows Server 2025 runner, not a Windows 11 laptop with a projector. Full parity
and hardware acceptance remain incomplete; see the feature ledger for details.

Locally, after building and generating `qa/demo.pdf`, reproduce the packaged check:

```sh
uv run python scripts/check_bundle.py --output qa/packaged
```

For minimum-size layouts, help scrolling and camera compositing without opening
a camera, run `uv run python scripts/layout_smoke.py qa/demo.pdf qa/layout`.
This uses a drawn image and saves captures for inspection.

`uv run python scripts/opening_smoke.py qa/demo.pdf qa/opening` checks drag/drop,
Qt's widget file dialog, application file-open events and recent-page restoration
using isolated preferences. Native OS dialog/event-delivery acceptance is separate.
