from pathlib import Path
import shutil
import subprocess

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import FloatObject, NameObject
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from pagecue.canvas import Canvas
from pagecue.app import Presenter
from pagecue.document import load_snapshot
from pagecue.session import Session


def test_real_beamer_notes_exclude_slide_miniature_and_hidden_text(tmp_path):
    engine = shutil.which("pdflatex")
    if not engine:
        shutil.copyfile(Path(__file__).parent / "fixtures/generated/beamer-notes.pdf", tmp_path / "beamer-notes.pdf")
    else:
        source = Path(__file__).parent / "fixtures/beamer-notes.tex"
        for _ in range(2):
            result = subprocess.run([engine, "-interaction=nonstopmode", "-halt-on-error",
                f"-output-directory={tmp_path}", str(source)], capture_output=True, text=True)
            assert result.returncode == 0, result.stdout[-2000:]
    snapshot = load_snapshot(tmp_path / "beamer-notes.pdf")
    assert len(snapshot.pages) == 3
    assert all(page.notes_crop for page in snapshot.pages)
    # pgfpages can repeat labels in combined-page output; retain the PDF's actual
    # metadata. Explicit overlay grouping is tested with controlled labels below.
    assert [page.label for page in snapshot.pages] == PdfReader(tmp_path / "beamer-notes.pdf").page_labels
    assert snapshot.notes.pages[0] == "Detailed speaker transcript. This text belongs only to the presenter."
    assert snapshot.notes.pages[1] == snapshot.notes.pages[0]
    assert snapshot.notes.pages[2] == "Final speaker transcript."


def test_pdf_page_labels_outline_and_auto_advance(qtbot, deck):
    writer = PdfWriter(clone_from=PdfReader(deck))
    writer.set_page_label(0, 1, prefix="A")
    writer.set_page_label(2, 2, prefix="B")
    writer.add_outline_item("First section", 0)
    writer.add_outline_item("Second section", 2)
    writer.pages[0][NameObject("/Dur")] = FloatObject(.08)
    writer.write(deck)
    session = Session()
    session.auto_advance = False
    session.open(deck)
    assert session.navigation.frames == [0, 2]
    assert session.navigation.sections == [0, 2]
    QTest.qWait(120)
    assert session.page == 0
    session.auto_advance = True
    session._schedule()
    qtbot.waitUntil(lambda: session.page == 1, timeout=1000)
    session.navigate(1, "section")
    assert session.page == 2
    session.close()


def test_space_pauses_timed_page_with_animation_and_menu_resumes(qapp, qtbot, tmp_path):
    writer = PdfWriter(clone_from=PdfReader(Path(__file__).parent / "fixtures/generated/animation.pdf"))
    writer.pages[0][NameObject("/Dur")] = FloatObject(.1)
    writer.add_blank_page(600, 400)
    path = tmp_path / "timed-animation.pdf"
    writer.write(path)
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    app.open(path)
    try:
        state = app.session
        assert state.turn_timer.isActive() and state.animation_timers[0].isActive()
        QTest.keyClick(app.view, Qt.Key.Key_Space)
        assert not state.auto_advance
        assert not state.turn_timer.isActive() and not state.animation_timers[0].isActive()
        QTest.qWait(150)
        assert state.page == 0
        view_menu = next(action.menu() for action in app.presenter.menuBar().actions() if action.text() == "View")
        automatic = next(action for action in view_menu.actions() if action.text() == "Automatic playback")
        assert not automatic.isChecked()
        state.go(1)
        state.go(0)
        assert not state.turn_timer.isActive() and not state.animation_timers[0].isActive()
        automatic.trigger()
        assert state.auto_advance and automatic.isChecked()
        assert state.animation_timers[0].isActive()
        qtbot.waitUntil(lambda: state.page == 1, timeout=1000)
    finally:
        app.session.close()
        app.media.close()


def test_canvas_draw_select_move_and_erase(qtbot, deck):
    session = Session()
    session.open(deck)
    view = Canvas(session, True)
    qtbot.addWidget(view)
    view.resize(1180, 780)
    view.show()
    qtbot.waitUntil(lambda: bool(session.images.cache))
    start = view.current_box.center().toPoint() - QPoint(60, 20)
    end = start + QPoint(100, 40)
    QTest.mousePress(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, start)
    QTest.mouseMove(view, end)
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, end)
    assert len(session.ink.pages[0]) == 1
    stroke = session.ink.pages[0][0]
    assert len(stroke.points) >= 2
    QTest.mousePress(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.AltModifier, start - QPoint(10, 10))
    QTest.mouseMove(view, end + QPoint(10, 10))
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.AltModifier, end + QPoint(10, 10))
    assert session.ink.selected == [stroke]
    before = stroke.points[0]
    QTest.mousePress(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, start)
    QTest.mouseMove(view, start + QPoint(20, 20))
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, start + QPoint(20, 20))
    assert stroke.points[0][0] > before[0] and stroke.points[0][1] > before[1]
    session.ink.erase(session.ink_pages)
    assert not session.ink.pages[0]
    session.close()


def test_single_point_annotation_is_visible_without_a_pointer(qtbot, deck):
    session = Session()
    session.open(deck)
    session.color, session.stroke_width = "#ff0000", .012
    view = Canvas(session, False)
    qtbot.addWidget(view)
    view.resize(640, 360)
    view.show()
    qtbot.waitUntil(lambda: bool(session.images.cache))
    point = view.current_box.center().toPoint()
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, point)
    session.pointer_visible = False
    image = view.grab().toImage()
    image.save(str(deck.parent / "single-point.png"))
    ratio = image.devicePixelRatio()
    color = image.pixelColor(round(point.x() * ratio), round(point.y() * ratio))
    assert color.red() > 200 and color.green() < 50
    assert session.page == 0 and len(session.ink.pages[0][0].points) == 1
    session.close()
