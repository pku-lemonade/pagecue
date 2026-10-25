# Completion audit

The objective remains a Qt/PySide rewrite with the reference application's
minimalist layout and capabilities. **Completion is not established.**
Presenteriyaki is the chosen name; PageCue is its previous name. The detailed
capability inventory remains [FEATURES.md](FEATURES.md).

## Evidence reviewed

The rename implementation at `73c6830` passes native run
[40195062883](https://github.com/pku-lemonade/presenteriyaki/actions/runs/40195062883)
on Windows x64 and Mac arm64/Intel: 97 tests, 16 native interaction checks, and
packaged execution plus install/update/removal. Tests exercise generated PDFs,
actual Qt rendering/decoding and input events; their scope is described below.
The source reference hash in FEATURES.md was rechecked and still matches.

The finalized source-preview commit `0003fa8` passes the same checks in
[40196504437](https://github.com/pku-lemonade/presenteriyaki/actions/runs/40196504437)
and is published as `v0.2.0`. The live update checker verifies older/current
versions through both the current and legacy repository URLs.

| Requirements | Concrete evidence | Remaining scope |
|---|---|---|
| UI-01–02: minimalist two-window layout | Native layout captures, `test_gui.py`, minimum/help-scroll checks, real Mac two-display acceptance | Physical Windows display acceptance |
| UI-03, APP-03: display controls/platforms | `test_application.py`, actual Mac fullscreen/swap/hide/restore metadata, native platform packages/fonts | Real unplug, Windows projector/camera, mixed DPI and tablet |
| DOC-01, APP-04: opening and CLI | `test_application.py`, `test_cli.py`, opening smoke, frozen CLI/icon checks, user-confirmed Mac picker/Open With | Windows native picker/file-event acceptance |
| DOC-02–04: navigation/overlays/reload | Domain/application/link tests; actual 400-page navigation/rail/cache check; failed reload retains the live snapshot | No additional claim about image-heavy performance or arbitrary PDF compatibility |
| DOC-05–06: notes | Sidecar/embedded/annotation precedence and Unicode fixtures; actual Beamer notes crop/extraction | Covered for the listed formats; original inputs remain unchanged |
| DOC-07–08, VIEW-01: links and geometry | Actual PDF actions, zoom/pan hit testing, crop/media-box intersection and all quarter-turn rotations; painted pointer/spotlight/blackout tests | Physical mixed-DPI movement |
| TIME-01–02: timer and automatic playback | Monotonic clock tests, GUI clock toggles/reload, real /Dur fixture combined with animation and menu resume | Covered for these timer behaviors |
| INK-01–02: drawing/editing | GUI strokes/taps/select/move/delete and rendered wheel scaling with untouched unselected ink; overlay grouping tests | Physical tablet input |
| MEDIA-01–03: local/embedded media | Actual GIF/H.264/WAV playback/decoding, Movie/Rendition/RichMedia fixtures, CFR/VFR seek/step and rectangle/expanded captures | Audio tests use muted/silent input; physical sound output was not observed |
| CAMERA-01 | Authorized real Mac permission/live capture/stop, user-confirmed inset; simulated loss/switch/stale callbacks and synthetic composition | Actual device switch/unplug and Windows camera |
| WEB-01 | Packaged local WebEngine load/zoom/Escape and camera compositing on all targets | Covered for the tested local content/controls |
| WEB-02 | Real Qt public-directory routing/video metadata; actual watch page inspected | Watch page required human verification before providing a video player; live playback unverified |
| ANIM-01–02 | Compiled 2013/2016/2018/current animate output, actual frame pixels, posters, timing, controls, reverse playback and merged widgets | General PDF JavaScript/OCG animation was not a baseline feature |
| APP-01 | Real GitHub source-version check, transport/cancellation tests, native Mac notification banner after approved permission | Native notification click and Windows delivery |
| APP-02 | Native package/installer checks; Mac per-user installation/native launch; legacy settings, command/executable/shortcut compatibility | Ordinary Windows and downloaded-binary first-launch acceptance; binary source/notice audit before public binary release |

The new GUI ink-scaling check closes a specific gap: the earlier domain check
covered movement, not scaling. Its native capture was inspected. No implementation
change was required for that capability.

## What requires external participation or evidence

- The user declined a physical display-disconnect test for now. Do not repeat that
  request during this work session. Camera switching/unplug, Windows hardware,
  mixed DPI and a physical tablet need suitable devices and observation.
- macOS notification permission was approved and enabled. Native delivery and
  reuse by the renamed app were observed. The transient banner disappeared before
  the computer-use click could be verified; the click signal tests are simulated.
- Public privacy-video metadata succeeded, but the watch page presented a human
  verification challenge. No challenge was attempted and no playback was claimed.
- Public binary distribution still needs the exact Qt/WebEngine/Chromium source
  correspondence and full bundled third-party attribution work described in
  [DISTRIBUTION.md](DISTRIBUTION.md). No unaudited binary has been published.

The source-install runbook, per-user installer and native builds are available.
Keep the full rewrite objective active until its outstanding acceptance evidence
is resolved; this audit does not replace those checks with automated simulations.
