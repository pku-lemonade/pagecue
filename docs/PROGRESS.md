# Implementation checkpoint

The rewrite remains active and incomplete, at `code/pagecue` and the public
repository https://github.com/pku-lemonade/pagecue. The existing wrapper repository/
application are unchanged. PageCue is a working name. No binary release is claimed.

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
- Async version check, opt-in background notification, configurable direct/custom/
  automatic privacy-video routing. Delayed routing is cancelled on context changes
  and Escape. No release exists at the configured GitHub endpoint yet.
- Original SVG app icon, PyInstaller native bundle recipe and runtime notices.
  Standard-library installer stages and verifies copies, checks app identity,
  restores the previous app on failed commit, and preserves a recovery copy if
  restoration also fails. Removal leaves preferences/documents intact.
- Local/direct/named PDF links, other-PDF numeric/named destinations, Unicode file
  specifications and file-URI decoding. Link hover/click coordinates track slide
  zoom/pan; hidden links cannot activate during blackout.
- Native CI builds/tests/packages on Windows x64, Mac arm64 and Mac Intel. Small
  original generated fixtures (72 KiB) keep PDF/media tests active without TeX or
  FFmpeg. Their manifest ties outputs to the authored sources and generator.
- Windows Start Menu helper preserves unrelated shortcuts and uses per-user shell
  links without changing PDF associations; CI coverage added. The first scripting
  helper failed to set a Unicode target in Windows CI; it has been replaced with
  native IShellLinkW/IPersistFile calls and is awaiting re-verification.
- An original animation fixture compiled with the maintainer's pinned, unmodified
  animate 2018/02/28 package now renders all frames with correct timing/controls.
  The fixture generator records its source/hash and does not vendor the package.

## Evidence

`uv run pytest -q`: **54 passed** on the development Mac at this checkpoint.
The initial native CI revision (`441b353`) ran **43 tests without skips** on Windows.

Tests include actual Qt PDF rendering, notes/annotations/encryption, original
LaTeX animate and Beamer-generated fixtures, controlled PDF labels/outlines,
/Dur event timing, GUI drawing/select/move/erase, and native media decoding.
Video tests use generated H.264 in Movie/Rendition/RichMedia annotations and verify
seeking, embedded/full-slide pixels, and forward/reverse stepping. A VFR fixture
checks the final B-frame; a silent WAV verifies audio loading without audible sound.
New coverage exercises real QtNetwork HTTP release responses, stale URL callbacks,
and installation/update/removal/rollback boundaries in temporary directories.
Windows-shaped installer fixture tests on a Mac are not Windows execution evidence.
Actual Windows CI execution is now available separately below.

Offscreen/native Cocoa captures are local under `qa/` (ignored):

- `native-mac/`: presenter layout and keyboard/timer/reload JSON from the first
  checkpoint; presenter and audience captures were inspected.
- `animation/`: three captured animation frames; the green audience frame was
  inspected, while tests compare all three actual Qt-rendered frame colors.
- `media/`: native embedded rectangle and expanded playback captures, both opened
  for visual inspection; decoded-frame timestamp recorded in `result.json`.
- `web-fixed/`: native local web-content capture inspected. `results.json` confirms
  load/title, resize geometry and Escape returning to slides.
- `bundle-mac/`: actual frozen macOS executable; PDF/navigation/reload, H.264 and
  local WebEngine checks all pass. Presenter, embedded media and web captures were
  inspected. `codesign --verify --deep --strict` passes for the ad-hoc signed app.
- `installed-mac/`: rebuilt executable installed into a path with spaces/Chinese
  characters, launched from `/tmp` with PYTHONPATH/PYTHONHOME/VIRTUAL_ENV removed.
  `result.json` reports frozen=true and all PDF/media/web checks passing. The
  installation was updated, verified and removed; original fixture/source files
  and built application remained. This is not a separate clean-machine test.
- `windows-ci/`: downloaded evidence from [native run 40167752910](https://github.com/pku-lemonade/pagecue/actions/runs/40167752910).
  The Windows Server 2025 AMD64 packaged executable reports Qt 6.12, frozen=true,
  PDF/navigation/reload, media decode, web load and Escape all passing. Installation,
  update, verification and removal passed from a Unicode path. Presenter (including
  Chinese notes) and WebEngine captures were inspected. This proves that runner
  configuration, not physical Windows laptops/projectors or first-launch prompts.
  Mac arm64 and Intel also completed the workflow successfully. Downloaded runner
  evidence is under `mac-arm-ci/` and `mac-intel-ci/`; the second run must still
  verify the latest link and Start Menu changes.
- [Second native run 40168249300](https://github.com/pku-lemonade/pagecue/actions/runs/40168249300):
  all 52 application tests and both Mac packages passed. Windows packaging built,
  but the new shortcut helper failed before the runtime smoke. Do not present that
  revision's Windows installer as fully validated. A native Unicode API replacement
  and an early Windows shell-link check are now prepared for the next run.

Reproduce the common checks:

```sh
uv run pytest -q
uv run python scripts/make_demo.py qa/demo.pdf
QT_QPA_PLATFORM=offscreen uv run python scripts/gui_smoke.py qa/demo.pdf qa/offscreen
QT_QPA_PLATFORM=cocoa uv run python scripts/gui_smoke.py qa/demo.pdf qa/native-mac
QT_QPA_PLATFORM=cocoa uv run python scripts/web_smoke.py qa/demo.pdf qa/web-fixed
```

The Cocoa commands require macOS. Tests regenerate LaTeX/video fixtures when
`pdflatex` (animate/beamer packages) and `ffmpeg` are available, otherwise use the
committed generated fixtures; missing generation tools no longer skip those tests.
Sources/manifest are in `tests/fixtures`, not upstream test copies. Regenerate with
`uv run python scripts/generate_fixtures.py`. The 43-test portable path also passed
locally with TeX/FFmpeg excluded from PATH.

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
- Parent asynchronous network service roots to QCoreApplication (or Presenter):
  short-lived unparented test services caused native deferred-destruction crashes.
- Cancel an outstanding automatic video URL lookup before aborting replies: Qt
  can emit completion inline. Late replies must not open web content after the
  presenter navigates, reloads, switches views, or presses Escape.
- GoToR /D values were incorrectly interpreted as current-deck destinations.
  They now open the target document at the requested numeric/named destination;
  missing destinations fail transactionally. /UF file specifications remain Unicode.
- animate 2018 emits FPS as a constant JavaScript ternary (`4==0?1e-6:4`). This
  previously raised SyntaxError and prevented the entire PDF from opening. A
  narrowly numeric reader now handles it; invalid numeric syntax is a recoverable
  metadata error. No PDF JavaScript is executed. Actual legacy frame colors pass.

## Required remaining work

1. Create an actual release channel; validate OS update notification delivery and
   real privacy-video service behavior. Release parsing/routing now have coverage.
2. Expand animation coverage: alternate forms/layouts, multiple animations,
   click/keyboard controls and long decks. Current and compiled 2018 widget output
   are covered; older object-style timing still has unit coverage only. A 2016
   package probe needs its historical `animfp.sty` dependency before compilation.
3. Audit camera permission/device lifecycle and test a real camera with deliberate
   user involvement. Camera frames are not captured automatically during QA.
4. Finish interaction/visual edge cases: small windows, changing DPI, crop/pan/zoom,
   selection scaling, persistent preferences, hide/fullscreen restoration and
   actual physical display selection/swap/unplug behavior.
5. Complete native package verification and the binary dependency/source/notice
   audit. Mac bundled Python/Qt, identity/icon, camera entitlements,
   usage text and staged installer exist. Clean-machine startup remains pending;
   local Mac Unicode-path install/update/uninstall and startup checks pass.
6. Rerun native checks for the link/shortcut changes,
   and complete both platforms' physical-device acceptance and ordinary-user
   first-launch checks. Windows CI is not equivalent to hardware acceptance.
7. Do a requirement-by-requirement completion audit against `FEATURES.md`; do not
   substitute an unsupported-feature message for a feature's implementation.

The Mac development app occupies approximately 562 MiB (`du -sh`); it includes
WebEngine for original web-view parity. Startup/resource budgets remain unmeasured.
No public packaged release, clean-room certification or full parity claim exists
yet. `docs/DISTRIBUTION.md` explicitly records the
remaining dependency-notice/source audit before public binary distribution.
