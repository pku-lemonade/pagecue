from io import BytesIO
import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Text
from pagecue.document import PasswordRequired, load_snapshot, rectangle


def test_notes_and_render_copy_preserve_original(deck):
    original = deck.read_bytes()
    snapshot = load_snapshot(deck)
    assert len(snapshot.pages) == 3
    assert "中文" in snapshot.notes.pages[0]
    assert snapshot.pages[0].size == (960.0, 540.0)
    assert deck.read_bytes() == original


def test_embedded_notes(embedded_deck):
    snapshot = load_snapshot(embedded_deck)
    assert snapshot.notes.pages == {0: "Embedded notes take precedence"}


def test_pdf_annotations_have_priority_and_are_removed_from_render_copy(deck):
    writer = PdfWriter(clone_from=PdfReader(deck))
    writer.add_annotation(0, Text(rect=(10, 10, 30, 30), text="Private PDF note"))
    writer.write(deck)
    snapshot = load_snapshot(deck)
    assert snapshot.notes.pages[0] == "Private PDF note"
    rendered = PdfReader(BytesIO(snapshot.render_bytes))
    assert not rendered.pages[0].get("/Annots")
    assert len(PdfReader(deck).pages[0]["/Annots"]) == 1


def test_encrypted_pdf_can_be_opened_with_password(deck):
    writer = PdfWriter(clone_from=PdfReader(deck))
    writer.encrypt("open-sesame")
    writer.write(deck)
    with pytest.raises(PasswordRequired):
        load_snapshot(deck)
    assert len(load_snapshot(deck, "open-sesame").pages) == 3


def test_annotation_coordinate_rotation(deck):
    page = PdfReader(deck).pages[0]
    assert rectangle(page, [0, 0, 480, 270]) == (0, .5, .5, .5)
    page.rotate(90)
    assert rectangle(page, [0, 0, 480, 270]) == (0, 0, .5, .5)
