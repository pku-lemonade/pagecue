"""Real PDF actions, navigation and canvas hit testing with original synthetic decks."""

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject, TextStringObject
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest

from pagecue.app import Presenter
from pagecue.document import filespec, load_snapshot
from pagecue.session import Session
from pagecue.model import Surface


def pdf(value):
    if isinstance(value, dict):
        return DictionaryObject({NameObject(k): pdf(v) for k, v in value.items()})
    if isinstance(value, list):
        return ArrayObject([pdf(v) for v in value])
    if isinstance(value, str):
        return NameObject(value) if value.startswith("/") else TextStringObject(value)
    if isinstance(value, int):
        return NumberObject(value)
    return value


def link(writer, action=None, destination=None):
    annotation = pdf({"/Type": "/Annot", "/Subtype": "/Link", "/Rect": [192, 216, 576, 432]})
    if action is not None:
        annotation[NameObject("/A")] = pdf(action)
    if destination is not None:
        annotation[NameObject("/Dest")] = destination
    writer.add_annotation(0, annotation)


@pytest.mark.parametrize("form", ["direct", "goto", "named-destination", "named-action"])
def test_local_links_activate_through_zoomed_canvas(qapp, qtbot, deck, form):
    writer = PdfWriter(clone_from=PdfReader(deck))
    destination = ArrayObject([writer.pages[2].indirect_reference, NameObject("/Fit")])
    if form == "direct":
        link(writer, destination=destination)
    elif form == "goto":
        link(writer, {"/S": "/GoTo", "/D": destination})
    elif form == "named-destination":
        writer.add_named_destination("closing", 2)
        link(writer, destination=TextStringObject("closing"))
    else:
        link(writer, {"/S": "/Named", "/N": "/LastPage"})
    writer.write(deck)
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    app.show()
    app.open(deck)
    app.session.zoom = 1.4
    app.session.pan = QPointF(.08, .04)
    app.session.changed.emit()
    qtbot.waitUntil(lambda: bool(app.session.images.cache))
    app.view.repaint()
    point = app.view._from_page(QPointF(.4, .4)).toPoint()
    assert app.view.current_box.contains(point)
    QTest.mouseMove(app.view, point + QPoint(2, 2))
    QTest.mouseMove(app.view, point)
    assert app.view.cursor().shape() == Qt.CursorShape.PointingHandCursor
    QTest.mouseClick(app.view, Qt.MouseButton.LeftButton, pos=point)
    assert app.session.page == 2
    app.session.history(True)
    assert app.session.page == 0
    app.session.toggle_surface(Surface.BLACK)
    QTest.mouseMove(app.view, point)
    assert app.view.cursor().shape() == Qt.CursorShape.ArrowCursor
    QTest.mouseClick(app.view, Qt.MouseButton.LeftButton, pos=point)
    assert app.session.page == 1  # a hidden link must not jump to the last page
    app.session.close()
    app.media.close()


@pytest.mark.parametrize("destination", [2, "closing"])
def test_remote_pdf_link_opens_target_deck_at_destination(qapp, qtbot, deck, destination):
    target = deck.parent / "linked 讲稿.pdf"
    remote = PdfWriter(clone_from=PdfReader(deck))
    remote.add_named_destination("closing", 2)
    remote.write(target)
    writer = PdfWriter(clone_from=PdfReader(deck))
    link(writer, {"/S": "/GoToR", "/F": {"/F": "ascii-fallback.pdf", "/UF": target.name},
                  "/D": [destination, "/Fit"] if isinstance(destination, int) else destination})
    writer.write(deck)
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    app.open(deck)
    action = app.session.snapshot.pages[0].actions[0]
    assert action.kind == "document"
    app.activate(action)
    assert app.session.snapshot.path == target
    assert app.session.page == 2
    app.session.close()
    app.media.close()


def test_bad_remote_destination_preserves_current_deck(deck):
    session = Session()
    session.open(deck)
    session.go(1)
    original = session.snapshot
    with pytest.raises(ValueError, match="does not exist"):
        session.open(deck, destination="missing")
    assert session.snapshot is original and session.page == 1
    session.close()


def test_uri_and_local_file_spec_links_are_not_stringified_dictionaries(deck):
    writer = PdfWriter(clone_from=PdfReader(deck))
    link(writer, {"/S": "/URI", "/URI": "https://example.org/talk?q=two%20words"})
    link(writer, {"/S": "/Launch", "/F": {"/UF": "local 讲稿.pdf"}})
    writer.write(deck)
    actions = load_snapshot(deck).pages[0].actions
    assert actions[0].kind == "url"
    assert actions[0].value == "https://example.org/talk?q=two%20words"
    assert actions[1].kind == "document"
    assert actions[1].value.resource.path == deck.parent / "local 讲稿.pdf"


def test_encoded_file_uri_round_trip(deck):
    target = deck.parent / "talk with spaces 中文.pdf"
    target.write_bytes(deck.read_bytes())
    assert filespec(target.as_uri(), deck.parent).path == target
