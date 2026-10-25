# Feature parity ledger

Target: Présentation 3.4.0 plus the user's PDFPC notes extension. All rows are in
scope. A first working screen or passing unit tests do not establish completion.
“Pending” means required work, not a deferred or dropped feature.

Baseline inspected: upstream `presentation.py`, 2,592 lines, SHA-256
`9924ca533b96cdc21e56dbb7e3e6d8e87f5687b95d7d4f92133da32e75e63e5c`.
Implementation is independent, using public Qt and PDF APIs and behavioral needs.

| ID | Capability | Implementation | Verification |
|---|---|---|---|
| UI-01 | Minimal dark layout: clock, current/next, notes, thumbnail rail, help | Implemented | Native Mac presenter capture inspected; resize cases pending |
| UI-02 | Two independently resizable windows, single-screen rehearsal | Implemented | Two-window Qt/Cocoa smoke; physical screens pending |
| UI-03 | Display selection, swap, fullscreen, hide/unhide, unplug recovery | Initial implementation | Mac and Windows physical displays pending |
| DOC-01 | PDF picker, file arguments, drag/drop, OS file-open events | Implemented | Programmatic open tested; picker/drop/OS events pending |
| DOC-02 | Page labels, frame/overlay grouping, section/outlines navigation | Implemented | Domain tests; real overlay/outlines PDF fixtures pending |
| DOC-03 | First/last, numeric jump, back/forward history, recent position | Implemented | Navigation/history tests; persistence test pending |
| DOC-04 | Safe reload of PDF and notes without losing active session | Implemented | Invalid reload retains document; valid reload retains page/timer |
| DOC-05 | PDF text annotations, sidecar/embedded format-2 notes, Unicode | Implemented | Sidecar/embedded/annotation/Unicode tests pass |
| DOC-06 | Beamer two-region notes cropping and zoomable notes text | Initial implementation | Beamer fixture/crop QA pending |
| DOC-07 | Internal/named/external links and hover hit testing | Initial implementation | PDF action fixtures pending |
| TIME-01 | Wall clock, count up/down, pause/reset, duration adjustments | Partial; wall-clock return control pending | Clock domain and pause/reload tests pass |
| TIME-02 | PDF /Dur auto-advance and pause/resume | Implemented | Real /Dur event timing test pending |
| INK-01 | Draw on slides and board, color/opacity/width, tablet input | Initial implementation | Actual drawing/tablet QA pending |
| INK-02 | Select/move/scale strokes, delete/clear, overlay-aware persistence | Implemented | Domain selection/transforms; GUI tests pending |
| VIEW-01 | Crop/pan/zoom, cursor size, laser/spotlight, blackout | Initial implementation | GUI interaction/coordinate tests pending |
| MEDIA-01 | Local linked video/audio/GIF, poster, play/pause/seek/step | Partial | Actual GIF decoder passes; video/audio/seek tests pending |
| MEDIA-02 | Movie, Screen/Rendition, RichMedia embedded PDF media | Metadata extraction implemented | All format/decoder fixtures pending |
| MEDIA-03 | Embedded-rectangle and full-slide playback | Pending | Pending |
| CAMERA-01 | Device choice, permission, inset, resize, position, opacity | Initial implementation | Physical camera and permission flow pending |
| WEB-01 | In-app external web/local content and zoom | Initial implementation | Focus/resize/content testing pending |
| WEB-02 | Configurable privacy video proxy/direct-link option | Pending | Pending |
| ANIM-01 | LaTeX animate frames, widget controls, frame stepping | Pending | Pending |
| ANIM-02 | Autoplay, forward/reverse, loop, palindrome, old/new metadata | Pending | Pending |
| APP-01 | Menus, help, about, version/update check and notifications | Partial; update checking pending | Menus/help/about present; lifecycle tests pending |
| APP-02 | Per-user installation, reproducible packages, update/uninstall | Pending | Clean machines pending |
| APP-03 | Windows/macOS support, fonts, mixed DPI, input devices | Native Mac development launch works | Windows and physical device acceptance pending |

No native code/toolkit choice proves media/animation parity. Keep actual fixture
evidence for each format and control. Do not mark “unsupported” as completion.
Platform-specific HCI may differ, but each user capability needs an equivalent.
