# Feature parity ledger

Target: Présentation 3.4.0 plus the user's PDFPC notes extension. All rows are in
scope. A first working screen or passing unit tests do not establish completion.
“Pending” means required work, not a deferred or dropped feature.

Baseline inspected: upstream `presentation.py`, 2,592 lines, SHA-256
`9924ca533b96cdc21e56dbb7e3e6d8e87f5687b95d7d4f92133da32e75e63e5c`.
Implementation is independent, using public Qt and PDF APIs and behavioral needs.

| ID | Capability | Implementation | Verification |
|---|---|---|---|
| UI-01 | Minimal dark layout: clock, current/next, notes, thumbnail rail, help | Implemented; help wraps and scrolls in small windows | Mac and Windows minimum/scrolled captures inspected, including Intel; layout checks pass on all three targets and help scrolling preserves page |
| UI-02 | Two independently resizable windows, single-screen rehearsal | Implemented | Qt/Cocoa smoke and real two-display Mac check pass; user confirmed separate views |
| UI-03 | Display selection, swap, fullscreen, hide/unhide, unplug recovery | Implemented; Mac presentation mode uses borderless Qt windows to avoid Spaces transition races | Real Mac audience-only/both-screen fullscreen, full-display frame bounds, swap, hide/restore and windowed restoration pass; unplug and Windows physical checks pending |
| DOC-01 | PDF picker, file arguments, drag/drop, OS file-open events | Implemented | Unicode PDF drag/drop, Qt widget file picker and QApplication QFileOpenEvent routes pass; packaged arguments pass; native OS-dialog/event delivery pending |
| DOC-02 | Page labels, frame/overlay grouping, section/outlines navigation | Implemented | Actual PDF labels/outlines and domain overlay tests pass |
| DOC-03 | First/last, numeric jump, back/forward history, recent position | Implemented | Navigation/history and saved-page restoration pass; 400-page rapid jumps, variable-size rail scroll/click and notes alignment pass; explicit page overrides persistence |
| DOC-04 | Safe reload of PDF and notes without losing active session | Implemented | Invalid reload retains document; valid reload retains page/timer |
| DOC-05 | PDF text annotations, sidecar/embedded format-2 notes, Unicode | Implemented | Sidecar/embedded/annotation/Unicode tests pass |
| DOC-06 | Beamer two-region notes cropping and zoomable notes text | Cropping, size adjustment and reset implemented | Real Beamer notes PDF excludes miniature/header/off-page text; keyboard/menu reset preserves numeric page entry |
| DOC-07 | Internal/named/external links and hover hit testing | Implemented, including other-PDF destinations | Real direct/GoTo/named/GoToR/URI/Launch fixtures; zoom/pan click and hover; hidden links inactive in blackout; encoded file-URI round trip |
| TIME-01 | Wall clock, count up/down, pause/reset, duration adjustments | Implemented | Pause/reset domain, Shift+T clock, and reload tests pass |
| TIME-02 | PDF /Dur auto-advance and pause/resume | Implemented | Actual /Dur PDF auto-advance and disabled state tested |
| INK-01 | Draw on slides and board, color/opacity/width, tablet input | Implemented; device QA pending | GUI draw test passes; physical tablet pending |
| INK-02 | Select/move/scale strokes, delete/clear, overlay-aware persistence | Implemented | GUI select/move/erase and domain scaling/overlay tests pass |
| VIEW-01 | Crop/pan/zoom, cursor size, laser/spotlight, blackout | Implemented; pan corrected for letterboxing, zoom anchored to cursor, crosshair size now follows P/Shift+P | Qt drag/wheel/keyboard tests pass on slides, board and notes-cropped PDF; rendered crosshair resizing/spotlight/blackout pixels and timeout pass; native Mac captures inspected |
| MEDIA-01 | Local linked video/audio/GIF, poster, play/pause/seek/step | Implemented | Qt GIF/H.264/WAV decoding; seeking; CFR/VFR stepping tests pass |
| MEDIA-02 | Movie, Screen/Rendition, RichMedia embedded PDF media | Implemented | Movie/Rendition/RichMedia PDFs decoded through Qt |
| MEDIA-03 | Embedded-rectangle and full-slide playback | Implemented | Embedded/expanded pixel assertions and native Mac captures inspected |
| CAMERA-01 | Device choice, permission, inset, resize, position, opacity | Implemented; corrected real PySide permission signature; default inset bounds both dimensions | Authorized real Mac permission grant/live capture/stop/clear checks pass (no images saved); user accepted corrected corner placement; square/portrait/landscape inset tests pass; real device switch/unplug and Windows checks pending |
| WEB-01 | In-app external web/local content and zoom | Implemented, including zoom reset | Native Mac local content, resize, zoom reset and Escape check; capture inspected; reset added to packaged smoke check |
| WEB-02 | Configurable privacy video proxy/direct-link option | Direct/custom/automatic routing and persisted setting implemented | URL/instance-resolution tests; navigation/reload/view/Escape cancel stale callbacks; live instance availability varies |
| ANIM-01 | LaTeX animate frames, widget controls, frame stepping | Widget and named-icon frame formats, including initial posters | Compiled 2013/2016/2018/current output; rendered colors, poster-last/poster-none, clicked controls, keyboard stepping and merged widget PDFs pass; native Mac captures inspected |
| ANIM-02 | Autoplay, forward/reverse, loop, palindrome, old/new metadata | Implemented for supported generated metadata | Compiled object-style interval, dotted and modern timing; autoplay/loop/palindrome; reverse pause/resume, speed, independent controls and page timer lifecycle pass |
| APP-01 | Menus, help, about, version/update check and notifications | Implemented, including opening the release page from a notification click; actual release channel pending | HTTP/QtNetwork tests and live HTTPS missing-release response; simulated notification click opens the current release once; OS notification delivery pending |
| APP-02 | Per-user installation, reproducible packages, update/uninstall | Native bundle recipe, staged installer and Windows Start Menu support | Windows x64 and Mac arm64/Intel CI install/update/remove and packaged execution pass; Windows Unicode shortcut lifecycle passes; OS first-launch approval flow pending |
| APP-03 | Windows/macOS support, fonts, mixed DPI, input devices | Windows x64 and Mac arm64/Intel packages run in CI | Windows presenter/Chinese notes capture inspected; mixed DPI and physical device acceptance pending |
| APP-04 | CLI help/version, initial page/duration, direct video and icon export | Implemented, including original short aliases and optional PNG output path | Headless subprocess export tests pass; actual Windows/Mac arm64/Intel packages verify PNG export and `-p 2 -d 12.5 -y` session settings |

No native code/toolkit choice proves media/animation parity. Keep actual fixture
evidence for each format and control. Do not mark “unsupported” as completion.
Platform-specific HCI may differ, but each user capability needs an equivalent.

Reference animation scope was rechecked in the installed 3.4.0 source (same hash
above): `prepare_animations` at lines 733–766 selects named frame widgets;
`advance_animation` at 776–827 uses a fixed FPS/loop/direction state. The baseline
does not provide general OCG-frame or arbitrary JavaScript playback. PageCue also
supports older named-icon frames as an addition. The author's
[feature description](https://iihm.imag.fr/blanch/software/osx-presentation/) explicitly
excludes fancy page-transition effects; PDF duration-based page advance remains
in scope and is implemented.
