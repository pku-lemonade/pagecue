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

`animation-2018.pdf` uses the same authored source with the unmodified animate
2018/02/28 package from [the maintainer's archived repository](https://github.com/agrahn/animate).
The generator fetches a pinned commit, checks its SHA-256, and keeps the `.sty`
only in a temporary directory. This third-party package is LPPL licensed; its
source URL and hash are recorded in the manifest. Regeneration requires network
access for that source. The PDF is compiled with the installed TeX toolchain,
so it tests the historic package's output structures, not a historical OS/TeX setup.

`multiple-animations.pdf` covers independent controls/rates, last-frame and absent
posters, and page changes. `animation-2016.pdf` compiles the original single-animation
source with animate 2016/02/04's default icon method and its historic `animfp.sty`
dependency. Both are pinned by source URL/hash in the generator and manifest.
The LPPL-licensed dependency is retained in the R `animation` maintainer's repository;
it is downloaded temporarily for fixture generation, never included in app code.
This fixture exercises the PDF `/Names/AP` appearance tree and dotted timing fields.

`animation-2013.pdf` uses animate 2013/12/20's default widgets. Its button images
live in `/MK/I`, with object-style `dt` timing and a scheduled autoplay call. The
unmodified historic package is pinned and uses the same `animfp.sty` dependency.
Frame colors, controls, timing, autoplay, loop and palindrome are tested through
the actual PDF parser and Qt renderer for all four package generations.
