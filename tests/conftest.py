"""Original synthetic decks; no private or upstream test artifacts."""

from io import BytesIO
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
from PySide6.QtCore import QSettings


@pytest.fixture(scope="session")
def qapp_cls():
    from pagecue.app import Application
    return Application


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path):
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path / "settings"))


@pytest.fixture
def deck(tmp_path):
    output = BytesIO()
    painter = canvas.Canvas(output, pagesize=(960, 540))
    for number, color in enumerate(["#344c9b", "#177d73", "#a44a52"]):
        painter.setFillColor(color)
        painter.rect(0, 0, 960, 540, fill=1, stroke=0)
        painter.setFillColor("white")
        painter.setFont("Helvetica", 42)
        painter.drawString(65, 420, f"PageCue · test page {number + 1}")
        painter.setFont("Helvetica", 22)
        painter.drawString(65, 350, "A clear slide. Notes stay on the presenter screen.")
        painter.circle(750, 180, 85, fill=0, stroke=1)
        painter.line(60, 90, 880, 90)
        painter.showPage()
    painter.save()
    path = tmp_path / "sample.pdf"
    path.write_bytes(output.getvalue())
    path.with_suffix(".pdfpc").write_text(json.dumps({
        "pdfpcFormat": 2,
        "pages": [{"idx": 0, "note": "Presenter-only notes.\n中文讲稿：保持简洁，专注内容。"},
                  {"idx": 1, "note": "Second page notes."}]
    }, ensure_ascii=False))
    return path


@pytest.fixture
def embedded_deck(deck):
    writer = PdfWriter(clone_from=PdfReader(deck))
    writer.add_attachment("speaker-notes.json", json.dumps({"pdfpcFormat": 2, "pages": [
        {"idx": 0, "note": "Embedded notes take precedence"}]}).encode())
    path = deck.parent / "embedded.pdf"
    writer.write(path)
    path.with_suffix(".pdfpc").write_bytes(deck.with_suffix(".pdfpc").read_bytes())
    return path
