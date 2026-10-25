# Physical-device acceptance

Use the original `qa/demo.pdf` fixture. Preserve original apps and real talks.
Ordinary tests/builds never activate a physical camera. Do not add the camera
diagnostic to CI or run it during an installation without explicit user approval.

## Authorized local check

Build the app, then run its executable with a PDF and an output directory:

```sh
dist/PageCue.app/Contents/MacOS/PageCue qa/demo.pdf \
  --hardware-output qa/hardware-check --hardware-camera
```

On Windows use the built `dist/PageCue/PageCue.exe` executable and equivalent
arguments. Omit `--hardware-camera` for display-only checks. The camera flag is
an explicit opt-in, not a substitute for obtaining the user's authorization.
The OS may also require the user to approve its camera prompt.

The check uses isolated preferences. It exercises audience-only fullscreen,
both-display fullscreen, screen swap, hide/restore and return to windowed mode.
On macOS the windows cover their selected displays without entering native
Spaces fullscreen. The app temporarily auto-hides the menu bar/Dock during
presentation and restores its previous presentation options on exit.

When authorized, the default camera then appears as a corner inset for 15 seconds.
It is stopped automatically. The check verifies incoming frames, cleared views
and the absence of further frames after stopping. It does **not** expand the
camera automatically; expansion remains the user's Shift+V action.

`result.json` contains screen dimensions, window geometry, camera permission
state, frame dimensions/counts, checks and errors. It never contains camera
images, video, audio, device names or device identifiers. No screenshots are
taken by this diagnostic. Close the app to stop the test early; its camera is
also stopped on errors/timeouts. A successful JSON result still needs the user's
visual confirmation that the output appears on the intended physical displays.

## Observed on the development Mac, 2026-10-25

The user explicitly authorized a local camera preview with two connected displays,
without saving or uploading camera frames. The first run exposed two real defects:
the permission request omitted PySide's required QObject context, and native
macOS fullscreen transitions broke mode switching/swap/restoration. Both were
corrected; the permission simulation now uses the actual three-argument signature.

The corrected executable passed all display and camera checks on two physical
displays at DPR 2.0. Permission changed from Undetermined to Granted, 399 frames
arrived during the preview, and stopping cleared both views with no later frames.
The user confirmed the separate views and live preview worked, but requested a
smaller corner inset. A second run with the smaller inset passed with 403 frames;
the user accepted placement and asked for a slight size increase without further
tuning. The default was adjusted from 18% to 20%; synthetic rendering tests cover
square, portrait and landscape feeds. No camera images were saved or uploaded.

Local metadata is under `qa/hardware-live-fixed-20261025/` and
`qa/hardware-small-inset-live/` (ignored by Git). The first failed run remains in
`qa/hardware-live-20261025/` to preserve the evidence for the corrections.

## Still to verify

- Disconnect/reconnect an actual presentation display: return to usable windowed
  mode, preserve page/timer/ink, then choose the reconnected audience display.
- Switch real camera devices and disconnect an external camera while previewing:
  clear the stale frame, report loss and permit a new selection. Simulations pass.
- Repeat physical monitor/camera checks on Windows; native Windows CI is available
  but does not provide a real projector or webcam.
- Mixed-DPI monitor movement and physical tablet input. The two tested Mac
  displays had the same DPR, so they do not establish mixed-DPI acceptance.
- Native OS file picker, OS file-open delivery and ordinary-user first launch.
  The local Computer Use service currently returns `cgWindowNotFound` for the
  running app; Qt widget-dialog tests do not substitute for those OS checks.
