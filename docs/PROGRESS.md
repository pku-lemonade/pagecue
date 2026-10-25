# Implementation checkpoint

The rewrite remains active and incomplete. The project is local at `code/pagecue`;
the existing wrapper repository/application are unchanged. PageCue is a working
name. No binary release or Windows validation is claimed.

## Current implementation

- Original minimalist Qt presenter/audience canvases, notes, thumbnails and help.
- Independent pypdf metadata/notes reading and Qt PDF queued rendering with bounded
  caches. Sources stay unchanged; invalid reload retains the live deck.
- Navigation/history, physical overlay groups, section targets, recent page,
  clock/countdown/pause/reset, /Dur auto-advance and display controls.
- Drawing, selection/movement/scaling, board, pointer/spotlight, zoom/pan.
- LaTeX animate widget appearance extraction into an independent frame PDF;
  Qt renders transparent frame images over the base slide. Timing is read from
  recognized generated declarations without executing PDF JavaScript. Forward,
  reverse, stepping, endpoints, autoplay, loop, palindrome and speed controls exist.
- Linked/embedded Movie, Rendition and RichMedia playback, GIF/audio support,
  sequential muted poster loading, media rectangles and full-slide expansion.
- Camera service/device controls and a lazy native WebEngine content view.
- Window hide/restore, persisted display preference/window geometry, safe shutdown.

## Evidence

`uv run pytest -q`: **29 passed** on the development Mac at this checkpoint.

Tests include actual Qt PDF rendering, notes/annotations/encryption, original
LaTeX animate and Beamer-generated fixtures, controlled PDF labels/outlines,
/Dur event timing, GUI drawing/select/move/erase, and native media decoding.
Video tests use generated H.264 in Movie/Rendition/RichMedia annotations and verify
seeking, embedded/full-slide pixels, and forward/reverse stepping. A VFR fixture
checks the final B-frame; a silent WAV verifies audio loading without audible sound.

Offscreen/native Cocoa captures are local under `qa/` (ignored):

- `native-mac/`: presenter layout and keyboard/timer/reload JSON from the first
  checkpoint; presenter and audience captures were inspected.
- `animation/`: three captured animation frames; the green audience frame was
  inspected, while tests compare all three actual Qt-rendered frame colors.
- `media/`: native embedded rectangle and expanded playback captures, both opened
  for visual inspection; decoded-frame timestamp recorded in `result.json`.
- `web-fixed/`: native local web-content capture inspected. `results.json` confirms
  load/title, resize geometry and Escape returning to slides.

Reproduce the common checks:

```sh
uv run pytest -q
uv run python scripts/make_demo.py qa/demo.pdf
QT_QPA_PLATFORM=offscreen uv run python scripts/gui_smoke.py qa/demo.pdf qa/offscreen
QT_QPA_PLATFORM=cocoa uv run python scripts/gui_smoke.py qa/demo.pdf qa/native-mac
QT_QPA_PLATFORM=cocoa uv run python scripts/web_smoke.py qa/demo.pdf qa/web-fixed
```

The Cocoa commands require macOS. Tests generating LaTeX/video fixtures require
`pdflatex` (animate/beamer packages) and `ffmpeg`; they explicitly skip if missing.
Their sources are original fixtures in `tests/fixtures`, not upstream test copies.

## Issues found and corrected

- Beamer initially exposed its miniature/header and off-page hidden overlay text
  in notes. Extraction now checks page bounds and recognizes the miniature header.
- Application-wide Python event filtering caused a native Shiboken/WebEngine crash
  on macOS. Filters are now attached only to the relevant widgets/focus proxy.
  `Application` also requests shared graphics contexts before QApplication setup.
- Estimated-FPS seeking repeated/skipped video frames. Forward stepping now decodes
  the actual next frame before pausing; reverse seeks just before the current frame.
  Forward stepping can take the remaining frame duration, especially in VFR video.
  Do not reintroduce a naive timestamp-plus-average-FPS shortcut.
- Animation timing reader accepts current generated globals and older object
  fields. Unknown timing produces a diagnostic/manual fallback; this is not proof
  of full old-version compatibility.

## Required remaining work

1. Complete update/version checking and notifications, configurable privacy-video
   routing/direct-link behavior, and an actual release channel.
2. Expand action/link and animation coverage: a real older animate PDF, alternate
   forms/layouts, multiple animations, click/keyboard controls and long decks.
   Legacy timing has unit coverage but no compiled legacy integration fixture yet.
3. Audit camera permission/device lifecycle and test a real camera with deliberate
   user involvement. Camera frames are not captured automatically during QA.
4. Finish interaction/visual edge cases: small windows, changing DPI, crop/pan/zoom,
   selection scaling, persistent preferences, hide/fullscreen restoration and
   actual physical display selection/swap/unplug behavior.
5. Produce per-user installers/native packages with bundled Python/Qt, application
   identity/icon, camera entitlements/usage text, notices and source/relink guidance.
   Test clean startup, update/uninstall and executable paths containing Unicode.
6. Run Windows builds/tests and both platforms' physical-device acceptance checks.
   No Windows environment has been exercised yet. Keep these requirements open.
7. Do a requirement-by-requirement completion audit against `FEATURES.md`; do not
   substitute an unsupported-feature message for a feature's implementation.

The full PySide6 distribution currently includes all add-on/WebEngine packages.
Release size/startup/resource budgets remain unmeasured. No public repo for the new
app, packaged release, clean-room certification or full parity claim exists yet.
