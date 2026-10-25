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
  native IShellLinkW/IPersistFile calls and passes native Windows verification.
- An original animation fixture compiled with the maintainer's pinned, unmodified
  animate 2018/02/28 package now renders all frames with correct timing/controls.
  The fixture generator records its source/hash and does not vendor the package.

## Evidence

`uv run pytest -q`: **79 passed** on the development Mac at this checkpoint.
The user authorized real local camera/two-display tests with no saved/uploaded
camera frames. Those checks exposed a wrong permission-call signature and actual
macOS fullscreen transition failures. PySide's request now includes the Camera
QObject context, and the permission simulation matches the real API. Mac
presentation fullscreen now uses independently placed borderless Qt windows with
temporary AppKit menu/Dock auto-hide, avoiding app-wide Spaces transitions.
Full-display geometry, selected screens, swap, hide/restore and return to windowed
mode all pass on the user's two physical displays. Permission was granted and
live camera capture/stop/clear passed (399 frames, then 403 on the inset retest).
The user confirmed both displays and the preview looked correct. See
`docs/HARDWARE_ACCEPTANCE.md` for the scope and remaining physical checks.

The user requested a smaller corner camera. The inset now bounds both dimensions,
preserving square/portrait feeds without covering a large fraction of a slide.
After the user accepted 18% but found it slightly small, the default was nudged to
20%; no further live-camera tuning was requested. Three synthetic aspect-ratio
tests pass. The hardware diagnostic no longer expands the camera automatically.
Only numeric/geometry metadata was recorded from real camera tests; no camera
images were saved or uploaded.

Update notification clicks now open the current release page once, with a
simulated delivery test that neither enables OS notifications nor opens a browser.
Live Qt HTTPS calls successfully read the public Invidious directory and an
instance's stats (Invidious software 2026.10.24-43d51d1); a later directory lookup
fell back to the original URL. This establishes live transport/routing behavior,
not video playback reliability. GitHub's real release endpoint still reports no
published release. Local metadata is under `qa/live-services/`.

Run 40175806222 passed Windows' 75 tests, six native interaction tests and package
checks. Both Mac native-test steps stalled and reached the job timeout; the
terminal run is cancelled, not successful. The next native-test step has verbose
output, a 30-second Python stack dump and a five-minute step limit for diagnosis;
the checks have not been removed or marked optional. Windows native artifacts are
under `qa/native-font-windows-ci/`. Fresh CI must verify the current corrections.
The CLI restores `-v`, `-y`, and `-i/--icon`; optional file output supports a Windows
GUI executable without stdout. Icon export paints PageCue's original SVG, with no
GUI application/font dependency. Subprocess tests use an invalid platform-plugin
name to verify that version/icon commands never initialize a GUI. The actual Mac
bundle exports PNG and starts with `-p 2 -d 12.5 -y`; packaged diagnostics confirm
page two, 750 seconds and direct routing, plus PDF/media/web/zoom-reset behavior.
The staged install/update/remove check passes under `qa/cli-bundle/`.

Run 40174814252 failed all targets before executing tests: `--basetemp=qa/tests`
requires its parent directory, which a fresh runner did not have. The workflow
now generates the original demo/QA directory before pytest. This corrects the
evidence-path setup; it does not weaken the tests. Run 40175202365 now passes all
three targets, including the 75 tests and actual packaged CLI/icon checks.

Pointer-size controls originally changed the laser/spotlight but left the default
crosshair fixed at six pixels. Crosshair arms now follow the shared size setting;
actual before/after pixel checks pass with offscreen and Cocoa backends. The
enlarged crosshair capture was inspected. The six interaction/long-deck checks now
also run in CI with the native Windows/Cocoa backend and preserve their captures.
Windows' offscreen test captures showed missing-font boxes; the real installed
Windows app capture renders correctly. Do not use offscreen Windows captures as
font-acceptance evidence. Fresh CI must verify the additional native-test step.
Packaged diagnostics now record Python/PySide, Qt build, WebEngine and Chromium
baseline/security-patch versions separately to support the distribution audit.
Bare 0 now resets notes/web zoom unless a page number is already being entered;
the View menu also exposes reset. Numeric input such as 10 remains intact. The
native offline WebEngine check under `qa/web-zoom-reset/` confirms real zoom reset,
geometry and Escape, and packaged diagnostics now check this behavior. Updated
700×420 help rendering was captured/inspected under `qa/layout-reset/`.
The new interaction checks also pass with the native Cocoa plugin. A simulated
two-screen topology verifies audience-only fullscreen by double-click, mode
switching with F5, Escape and hide/restore. This is not physical monitor evidence.
Ctrl/Command dragging now tracks the mouse on letterboxed slides: the previous
denominator used the window box rather than the fitted slide dimensions. Wheel
and keyboard zoom keep the cursor's content point stationary, including on the
board and a notes-cropped PDF. Actual painted laser/spotlight, pointer resizing,
blackout and pointer timeout checks pass; native captures are under
`qa/view-interactions-native/` and the two spotlight captures were inspected.
A newly authored 400-page PDF exercises rapid navigation, varying aspect ratios,
thumbnail rail scroll/click, notes alignment and return to page one. Source hashes
remain unchanged. Offscreen and native Cocoa checks pass; the last-page capture
under `qa/long-deck-native/` was inspected. Sampled native raster-cache usage was
12–43 MiB, within its 96 MiB budget; this measures that image cache, not process
memory, and the simple generated deck is not an image-heavy performance benchmark.
The native test recorded approximately 0.11 seconds to its first rendered page on
this development Mac. These timings are observations, not release performance gates.
New work covers multiple animations, last/absent posters, reverse pause/resume,
and duplicate source field names in merged PDFs. Native Cocoa captures of the
poster and previously invisible first-frame states were inspected under
`qa/animation-ui-check/`. `scripts/opening_smoke.py` passes Unicode drag/drop,
Qt widget-dialog selection, QApplication QFileOpenEvent handling and recent-page
restoration. Those checks do not simulate native OS dialog/event delivery.
Older animation tests now compile actual 2013, 2016 and 2018 packages as well as
the current one. The 2013 button-icon `/MK/I` format and object-style interval/
scheduled-autoplay metadata, plus 2016 `/Names/AP` icons, render correctly through
Qt. Source package/dependency versions and hashes are in the fixture manifest.
The current changes add scrollable/wrapped help and camera permission/device
lifecycle, plus persisted inset width/opacity/corner controls. Native macOS
captures under `qa/layout-camera/` show minimum, scrolled and normal layouts and
synthetic inset/expanded camera images; all five were visually inspected. The
layout check confirms that scrolling help does not navigate the PDF. No physical
camera was activated or photographed by these checks. Windows minimum/scrolled
and Intel Mac minimum captures were also inspected from the CI artifacts.
The verified implementation commit **`cc399f3`** passes **75 tests without skips on
Windows x64, Mac arm64 and Mac Intel**, plus all three packaged executable checks:
[native run 40175202365](https://github.com/pku-lemonade/pagecue/actions/runs/40175202365).
Windows downloaded reports under `qa/cli-windows-ci/` confirm 75 tests,
frozen executable PDF/media/web operation and install/update/remove/shortcut
lifecycle, icon export and page/duration/direct-video CLI settings. Its icon and
packaged presenter captures were inspected. The run also completed both Mac jobs
successfully. Crosshair resizing and richer runtime diagnostics postdate this
verified revision and need fresh CI.
Downloaded reports and opening results under `qa/animation-opening-ci/` confirm
all 67 tests on each target, Unicode Qt widget-dialog selection, drag/drop,
QFileOpenEvent handling, recent-page restoration and unchanged source PDFs.
Windows additionally passes Unicode shell-link create/read/update/conflict/removal.
Earlier downloaded JSON, JUnit reports and captures are under `qa/camera-windows-ci/`,
`qa/camera-arm-ci/` and `qa/camera-intel-ci/`. Local rebuilt-bundle checks also pass
under `qa/camera-bundle/`. Only authored fixtures/synthetic camera images were used.
This is automated runner evidence, not physical-device or ordinary-user OS approval
acceptance. Documentation-only commits after that revision do not change binaries.

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
  evidence is under `mac-arm-ci/` and `mac-intel-ci/`. These earlier artifacts
  remain distinct from the final successful run listed above.
- [Second native run 40168249300](https://github.com/pku-lemonade/pagecue/actions/runs/40168249300):
  all 52 application tests and both Mac packages passed. Windows packaging built,
  but the new shortcut helper failed before the runtime smoke. Do not present that
  revision's Windows installer as fully validated. A native Unicode API replacement
  and an early Windows shell-link check corrected that failure in the final run.

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

- QSettings' organization/application constructor ignores setDefaultFormat and
  selects NativeFormat. Earlier QA overrides therefore did not isolate preferences
  as intended. Session now supplies the format/scope explicitly; regression tests
  inspect the actual settings filename. All QA scripts set output-local INI paths.
  The local PageCue preference file was backed up under `qa/preference-recovery/`;
  seven synthetic-deck history entries and the exact camera values left by the
  clamp test were removed. Other preferences and original Présentation apps remain.
- Animation extraction ignored last-frame/absent posters and reused numeric source
  IDs globally, losing an animation after merged PDFs repeated a field name. The
  initial visible frame now comes from annotation flags/appearance references;
  application IDs are independent of per-page source IDs. Space pauses either
  playback direction and resumes that direction instead of switching to forward.
- Pixel checks now account for the captured widget's device pixel ratio; logical
  coordinates cannot index a Retina-resolution QImage directly.
- The first opening-smoke CI attempt passed drag/drop and file events but failed
  to select a filename in the dialog. Programmatic selectFile calls after showing
  left the focused filename field empty. The check now uses the documented initial
  filename parameter, waits for the real selection, captures the widget dialog,
  accepts it and verifies the returned file. Offscreen, Cocoa and all three native
  CI targets now pass this correction.

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
- Cold Mac CI media initialization exposed a paused-load race: starting playback
  and waiting for a first frame before pausing could advance the video clock while
  hardware initialization/conversion stalled. Non-autoplay loads now pause
  immediately after priming and before image conversion. A delayed-event test
  checks that frame zero remains selected. All three native CI targets pass.
- Windows shell-link verification must normalize 8.3 and long parent names; the
  native API can expand RUNNER~1. Comparing raw strings incorrectly rejected a
  newly created shortcut. Verification now resolves paths before comparison,
  including after the executable is removed. Native Windows CI passes.

## Required remaining work

1. Create an actual release channel; validate OS update notification delivery and
   real privacy-video service behavior. Release parsing/routing now have coverage.
2. Complete the remaining rendering/long-deck audit. Current and compiled
   2013/2016/2018 animation output now cover widget and named-icon forms, original
   object-style timing, independent animations, posters and click/keyboard controls.
   The baseline implementation's widget/fixed-timing boundary was rechecked and
   recorded in FEATURES.md; general OCG/arbitrary JavaScript playback was not an
   implemented feature of the reference app.
   The 400-page synthetic-deck interaction/render check now passes. A renewed
   baseline help/CLI audit found explicit notes-size/web-zoom reset commands and
   icon export missing. Notes/web reset, original short CLI aliases and PageCue
   icon export are now restored and tested, including actual Mac bundle execution.
3. Finish camera device-switch/unplug acceptance and Windows hardware coverage.
   Authorized real Mac permission/live preview/stop checks now pass. Camera frames
   are not captured automatically during ordinary QA.
   Width/opacity/position now have persisted controls. Permission callbacks are
   cancelled on stop/switch/quit; device loss clears both views, and each capture
   generation has its own sink to reject late frames. Six simulated lifecycle/
   preference tests pass. The actual Mac permission call was corrected after the
   hardware test found the simulation's incomplete signature. The Mac bundle opts
   into the Continuity Camera device type.
4. Finish interaction/visual edge cases: small windows, changing DPI, crop/pan/zoom,
   selection scaling, persistent preferences, hide/fullscreen restoration and
   remaining physical unplug and Windows display behavior. Mac two-display
   selection/fullscreen/swap/hide/restore now pass with user visual confirmation.
   The overlapping help at 700×420 is corrected: rows wrap at readable sizes and
   the panel scrolls. `qa/layout-camera/minimum.png` and `minimum-scrolled.png`
   show the correction; native Windows/Intel resize captures are added to CI.
   Native file-picker/OS-open acceptance is still pending. A normal LaunchServices
   launch ran the packaged Cocoa event loop and painted (sampled process evidence),
   but Computer Use returned `cgWindowNotFound` for both the app path and bundle ID,
   so no successful native picker interaction is claimed. The owned QA process was
   stopped after investigation; original Présentation apps were untouched.
   A fresh attempt against the rebuilt CLI-capable app again returned
   `cgWindowNotFound` while the app inventory showed it running. The owned QA
   process was stopped; no alternate OS-input automation was used.
5. Complete native package verification and the binary dependency/source/notice
   audit. Mac bundled Python/Qt, identity/icon, camera entitlements,
   usage text and staged installer exist. Fresh CI runner startup passes; ordinary
   user first-launch permission/signing checks remain pending. WebEngine's separate
   runtime version and missing notices are recorded in DISTRIBUTION.md.
6. Complete both platforms' physical-device acceptance and ordinary-user
   first-launch checks. Windows CI is not equivalent to hardware acceptance.
   The user has authorized and completed the local Mac camera/two-display check;
   this does not authorize saving/uploading camera frames or prove Windows,
   mixed-DPI, physical unplug or tablet behavior.
7. Do a requirement-by-requirement completion audit against `FEATURES.md`; do not
   substitute an unsupported-feature message for a feature's implementation.

The Mac development app occupies approximately 562 MiB (`du -sh`); it includes
WebEngine for original web-view parity. Startup/resource budgets remain unmeasured.
No public packaged release, clean-room certification or full parity claim exists
yet. `docs/DISTRIBUTION.md` explicitly records the
remaining dependency-notice/source audit before public binary distribution.
