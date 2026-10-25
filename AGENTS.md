# PageCue implementation instructions

The active objective is a Qt/PySide rewrite of Présentation with its minimalist
style/basic layout and **no dropped features**. `docs/FEATURES.md` is the parity
ledger, not a menu of optional scope. Keep incomplete capabilities visible.

- Read `README.md`, `docs/FEATURES.md` and `docs/PROGRESS.md` before continuing.
- Work independently from behavioral requirements and public APIs. Do not copy
  the original GPL presenter/wrapper source, tests or artwork into this project.
- Preserve the existing Présentation and Présentation PDFPC installations.
- Native Qt custom painting owns the main UI. Do not replace it with a web UI.
  WebEngine is only for the existing external web-content capability.
- Install development dependencies with `uv sync`; run tests with `uv run pytest`.
- Use newly authored fixtures. Avoid committing private slides or notes.
- Run actual widget rendering and inspect captures after layout changes. A
  passing import test does not establish launch, media, camera or display parity.
- Use `scripts/make_demo.py` and `scripts/gui_smoke.py` for reproducible local QA.
  Offscreen tests are useful but do not prove physical monitor correctness.
- Keep PDF/notes sources unmodified and preserve the live session on failed reload.
- `--hardware-camera` activates a real camera. Run it only after explicit user
  authorization for a local preview test; never run it in ordinary CI or installer
  checks. The hardware diagnostic records metadata only, never images/video.
- Do not mark the goal complete until the feature ledger has concrete evidence
  for every capability and the supported platform builds have been checked.
