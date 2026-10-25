# Development instructions

Presenteriyaki is a standalone desktop app. Keep its public documentation focused
on the app's features, installation and use. Put contributor instructions in
CONTRIBUTING.md; keep conversation history and local QA logs out of app docs.

- Preserve the minimalist interface and existing capabilities.
- Use Qt Widgets/custom painting for the main UI; WebEngine is for web content.
- Set up with `uv sync --frozen --python 3.13`; run relevant tests with `uv run pytest`.
- Use original synthetic fixtures. Keep PDFs and notes unmodified during use.
- Visually check GUI changes with the rendering scripts and fixtures under `scripts/`.
- Keep ordinary tests and CI independent of physical camera access. Live camera
  tests require explicit authorization and must not save frames.
- Preserve existing preferences, app identity and installer rollback behavior.
- Include applicable dependency notices when packaging; see docs/DISTRIBUTION.md.
