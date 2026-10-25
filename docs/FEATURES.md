# Feature parity ledger

Target: Présentation 3.4.0 plus the user's PDFPC notes extension. All rows are in
scope. A first working screen or passing unit tests do not establish completion.
“Pending” means required work, not a deferred or dropped feature.

Baseline inspected: upstream `presentation.py`, 2,592 lines, SHA-256
`9924ca533b96cdc21e56dbb7e3e6d8e87f5687b95d7d4f92133da32e75e63e5c`.
Implementation is independent, using public Qt and PDF APIs and behavioral needs.

| ID | Capability | Implementation | Verification |
|---|---|---|---|
| UI-01 | Minimal dark layout: clock, current/next, notes, thumbnail rail, help | Implemented; help wraps and scrolls in small windows | Native Mac minimum/normal/scrolled captures inspected; help scrolling preserves page; other-platform resize captures pending CI |
| UI-02 | Two independently resizable windows, single-screen rehearsal | Implemented | Two-window Qt/Cocoa smoke; physical screens pending |
| UI-03 | Display selection, swap, fullscreen, hide/unhide, unplug recovery | Implemented controls; hardware validation pending | Hide/restore unit integration passes; physical displays pending |
| DOC-01 | PDF picker, file arguments, drag/drop, OS file-open events | Implemented | Programmatic open tested; picker/drop/OS events pending |
| DOC-02 | Page labels, frame/overlay grouping, section/outlines navigation | Implemented | Actual PDF labels/outlines and domain overlay tests pass |
| DOC-03 | First/last, numeric jump, back/forward history, recent position | Implemented | Navigation/history tests; persistence test pending |
| DOC-04 | Safe reload of PDF and notes without losing active session | Implemented | Invalid reload retains document; valid reload retains page/timer |
| DOC-05 | PDF text annotations, sidecar/embedded format-2 notes, Unicode | Implemented | Sidecar/embedded/annotation/Unicode tests pass |
| DOC-06 | Beamer two-region notes cropping and zoomable notes text | Implemented | Real Beamer notes PDF excludes miniature/header/off-page text |
| DOC-07 | Internal/named/external links and hover hit testing | Implemented, including other-PDF destinations | Real direct/GoTo/named/GoToR/URI/Launch fixtures; zoom/pan click and hover; hidden links inactive in blackout; encoded file-URI round trip |
| TIME-01 | Wall clock, count up/down, pause/reset, duration adjustments | Implemented | Pause/reset domain, Shift+T clock, and reload tests pass |
| TIME-02 | PDF /Dur auto-advance and pause/resume | Implemented | Actual /Dur PDF auto-advance and disabled state tested |
| INK-01 | Draw on slides and board, color/opacity/width, tablet input | Implemented; device QA pending | GUI draw test passes; physical tablet pending |
| INK-02 | Select/move/scale strokes, delete/clear, overlay-aware persistence | Implemented | GUI select/move/erase and domain scaling/overlay tests pass |
| VIEW-01 | Crop/pan/zoom, cursor size, laser/spotlight, blackout | Initial implementation | GUI interaction/coordinate tests pending |
| MEDIA-01 | Local linked video/audio/GIF, poster, play/pause/seek/step | Implemented | Qt GIF/H.264/WAV decoding; seeking; CFR/VFR stepping tests pass |
| MEDIA-02 | Movie, Screen/Rendition, RichMedia embedded PDF media | Implemented | Movie/Rendition/RichMedia PDFs decoded through Qt |
| MEDIA-03 | Embedded-rectangle and full-slide playback | Implemented | Embedded/expanded pixel assertions and native Mac captures inspected |
| CAMERA-01 | Device choice, permission, inset, resize, position, opacity | Permission cancellation/device lifecycle; persisted width/opacity/corner controls and expansion implemented | Simulated permission cancellation/denial/device loss, stale-frame rejection and shutdown tests pass; synthetic compositing captures inspected; physical camera and OS permission flow pending |
| WEB-01 | In-app external web/local content and zoom | Implemented | Native Mac local content, resize and Escape check; capture inspected |
| WEB-02 | Configurable privacy video proxy/direct-link option | Direct/custom/automatic routing and persisted setting implemented | URL/instance-resolution tests; navigation/reload/view/Escape cancel stale callbacks; live instance availability varies |
| ANIM-01 | LaTeX animate frames, widget controls, frame stepping | Implemented for recognized widget-frame animations | Current and animate 2018/02/28 PDFs: actual Qt-rendered frame colors, controls and stepping pass; other methods/multiple animations pending |
| ANIM-02 | Autoplay, forward/reverse, loop, palindrome, old/new metadata | Implemented for recognized metadata | Current/2018 generated fixtures verify autoplay/loop/palindrome; reverse/speed/object metadata unit tests; broader formats pending |
| APP-01 | Menus, help, about, version/update check and notifications | Implemented; actual release channel pending | Real local HTTP/QtNetwork version and missing-release tests; OS notification delivery pending |
| APP-02 | Per-user installation, reproducible packages, update/uninstall | Native bundle recipe, staged installer and Windows Start Menu support | Windows x64 and Mac arm64/Intel CI install/update/remove and packaged execution pass; Windows Unicode shortcut lifecycle passes; OS first-launch approval flow pending |
| APP-03 | Windows/macOS support, fonts, mixed DPI, input devices | Windows x64 and Mac arm64/Intel packages run in CI | Windows presenter/Chinese notes capture inspected; mixed DPI and physical device acceptance pending |

No native code/toolkit choice proves media/animation parity. Keep actual fixture
evidence for each format and control. Do not mark “unsupported” as completion.
Platform-specific HCI may differ, but each user capability needs an equivalent.
