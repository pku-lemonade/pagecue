# PageCue

A Qt/PySide rewrite of the PDF-presentation workflow, preserving a minimalist
presenter view and a separate audience screen. Independently implemented; no
Présentation source or artwork is included. PageCue is a working name.

**In development. Feature parity is not yet achieved.**
See [the feature ledger](docs/FEATURES.md) for implementation and verification status.

Development setup (Python 3.12–3.14 and [uv](https://docs.astral.sh/uv/)):

```sh
uv sync
uv run pagecue /path/to/slides.pdf
uv run pytest
```

The interface uses Qt Widgets and custom painting. Qt WebEngine is reserved for
the original presenter's web-content feature; it does not implement the main UI.
The existing Présentation and Présentation PDFPC installations are independent.

PageCue's original code is MIT licensed. Qt/PySide and other dependencies retain
their own licenses. Binary distribution must include the applicable notices and
Qt library source/replacement information. Packaging is still in development.
