# Implementation checkpoint

The rewrite is active and incomplete. The project is local at `code/pagecue`;
the existing wrapper repository/application were not changed by this implementation.
PageCue is a working name. No binary release is claimed.

## Current implementation

- Original Qt Widgets presenter/audience canvases with current/next, thumbnails,
  Unicode notes, clock, keyboard help and pointer/ink layers.
- Independent PDF metadata/notes reader using pypdf; render-only PDF copy removes
  note annotations; original file bytes remain unchanged.
- Qt PDF asynchronous rendering with bounded image cache and generation checks.
- Navigation/history, overlay grouping, section targets and recent-page storage.
- PDF and notes reload prepares a new backend before replacing the live session.
- Qt media player/audio/video sink plus GIF decoder, camera service, lazy web view.
- Display/fullscreen controls, basic drawing selection/transforms and tablet events.

## Evidence at this checkpoint

- `uv run pytest -q`: **14 passed** on the development Mac.
- Actual Qt PDF rendering checked with a synthetic three-page vector deck.
- PDF annotation precedence, embedded/sidecar notes, Unicode, encrypted PDFs,
  annotation rotation, physical-page navigation, timer and ink domain tests.
- Full application keyboard navigation from both windows, board mode, timer,
  reload retaining page/timer; actual two-frame GIF decoding.
- Offscreen and native Cocoa smoke runs generated presenter/audience captures.
  The native presenter capture and initial audience capture were visually opened.
  Font spacing and help clipping found during QA were corrected and rechecked.
- `qa/native-mac/smoke.json` records page-forward=1, audience-back=0, board mode,
  timer running and reload preserving the timer. QA artifacts are local/ignored.

Reproduce:

```sh
uv run python scripts/make_demo.py qa/demo.pdf
QT_QPA_PLATFORM=offscreen uv run python scripts/gui_smoke.py qa/demo.pdf qa/offscreen
QT_QPA_PLATFORM=cocoa uv run python scripts/gui_smoke.py qa/demo.pdf qa/native-mac
```

The Cocoa command is Mac-specific. Neither smoke run proves two physical screens,
real camera permission/device capture, all movie codecs, or Windows support.

## Next implementation work (required, not optional)

1. Implement LaTeX animate extraction and frame rendering/control, with original
   generated PDF fixtures. Cover old/new metadata, autoplay, reverse, loop,
   palindrome and visible widget controls. `pdflatex` is available locally.
2. Implement embedded-rectangle vs full-slide media playback, poster extraction,
   and test linked/embedded Movie, Rendition and RichMedia formats. `ffmpeg` is
   available locally; GIF playback alone is not video/audio validation.
3. Finish lifecycle/HCI behavior: clock display switching, media seek/step accuracy,
   audience keyboard events with web focus, web resize, camera controls/permissions,
   window hide/unhide and preferences/display persistence.
4. Exercise ink selection/movement/scaling, Beamer cropping, /Dur timing, page
   labels/sections and action links with actual PDFs rather than only domain tests.
5. Implement update/version check equivalent and configurable video proxy behavior.
6. Produce reproducible per-user installers/packages with bundled Python/Qt,
   notices and source/relink information. Test clean startup and installation.
7. Run Windows builds/tests and physical-display/camera acceptance checks. Keep
   unsupported/unavailable test environments explicitly unverified until tested.

Known design issues to address: the full PySide6 dependency currently includes all
add-on/WebEngine packages; release size has not been measured. Help is compact and
needs resize/accessibility checks. Most GUI commands exist but have not all been
exercised. No source-copying or license-clean-room certification is claimed.
