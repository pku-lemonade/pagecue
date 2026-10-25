# Original test inputs

The `.tex` files and generated colored media are original PageCue test fixtures.
They contain no user presentations and no Présentation source or artwork.

Run `uv run python scripts/generate_fixtures.py` with TeX Live (animate/beamer)
and FFmpeg/libx264 to regenerate `generated/`. The manifest records tool versions
and SHA-256 hashes of inputs/outputs. PDF bytes can differ between builds because
TeX embeds build metadata; semantic/rendering tests establish the expected behavior.

Tests compile/generate fresh fixtures when the external tools are installed.
Otherwise they use these committed PDFs/MP4s, exercising the actual Qt renderers
and decoders on every supported platform without silently skipping those tests.
The PDFs include generated LaTeX/animate machinery and standard embedded fonts;
they are test documents, not code copied into the application implementation.
