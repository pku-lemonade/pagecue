"""Exercise shared view transforms and overlays through actual Qt input/painting."""

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest

from pagecue.app import Presenter
from pagecue.model import Surface


def wheel(qapp, canvas, point, delta, modifiers=Qt.KeyboardModifier.NoModifier):
    event = QWheelEvent(point, canvas.mapToGlobal(point.toPoint()), QPoint(), QPoint(0, delta),
                        Qt.MouseButton.NoButton, modifiers, Qt.ScrollPhase.NoScrollPhase, False)
    qapp.sendEvent(canvas, event)
    canvas.repaint()


def pixel(image, point):
    ratio = image.devicePixelRatio()
    return image.pixelColor(round(point.x() * ratio), round(point.y() * ratio))


def move(qapp, canvas, point):
    # Target this widget explicitly: the two test windows can overlap on the
    # virtual desktop, where a global QTest cursor move can hit the other view.
    event = QMouseEvent(QEvent.Type.MouseMove, QPointF(point), canvas.mapToGlobal(point),
                        Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    qapp.sendEvent(canvas, event)


@pytest.fixture
def presenter(qapp, qtbot, deck):
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    app.show()
    app.open(deck)
    # Deliberately letterbox the wide slide to expose pan denominator mistakes.
    app.audience.resize(700, 700)
    qtbot.waitUntil(lambda: bool(app.session.images.cache))
    app.view.repaint()
    app.slide.repaint()
    yield app
    app.session.close()
    app.media.close()


@pytest.mark.parametrize("surface", ["slides", "board", "notes-right"])
def test_pan_tracks_drag_and_zoom_keeps_anchor(qapp, qtbot, presenter, surface, tmp_path):
    app = presenter
    state, view = app.session, app.slide
    if surface == "board":
        QTest.keyClick(app.view, Qt.Key.Key_B)
    elif surface == "notes-right":
        state.notes_layout = "right"
        state.reload()
    view.repaint()
    anchor = view._from_page(QPointF(.2, .55)).toPoint()
    page_point = view._to_page(QPointF(anchor))
    delta = QPoint(35, 28)
    QTest.mousePress(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, anchor)
    QTest.mouseMove(view, anchor + delta)
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, anchor + delta)
    view.repaint()
    moved = view._from_page(page_point)
    assert moved.x() == pytest.approx(anchor.x() + delta.x(), abs=1)
    assert moved.y() == pytest.approx(anchor.y() + delta.y(), abs=1)
    before = view._to_page(moved)
    wheel(qapp, view, moved, 240, Qt.KeyboardModifier.ControlModifier)
    after = view._to_page(moved)
    assert after.x() == pytest.approx(before.x(), abs=1e-6)
    assert after.y() == pytest.approx(before.y(), abs=1e-6)
    # Keyboard zoom anchors to the same shared pointer, including cropped notes.
    state.pointer = before
    app.view.repaint()
    QTest.keyClick(app.view, Qt.Key.Key_Plus, Qt.KeyboardModifier.ControlModifier)
    view.repaint()
    assert view._from_page(before).x() == pytest.approx(moved.x(), abs=1e-6)
    assert view._from_page(before).y() == pytest.approx(moved.y(), abs=1e-6)
    view.grab().save(str(tmp_path / f"{surface}-zoom.png"))
    QTest.keyClick(app.view, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    view.repaint()
    zoom, pan = (state.board_zoom, state.board_pan) if surface == "board" else (state.zoom, state.pan)
    assert zoom == 1 and pan == QPointF()
    assert state.page == 0
    assert not state.ink.visible(state.ink_pages)


def test_pointer_modes_size_timeout_and_blackout(qapp, qtbot, presenter, tmp_path):
    app, state = presenter, presenter.session
    view = app.slide
    point = view._from_page(QPointF(.4, .55)).toPoint()
    move(qapp, view, point)
    state.pointer_visible = False
    plain = view.grab().toImage()
    state.pointer_visible = True
    cross = view.grab().toImage()
    beyond_cross = QPointF(point) + QPointF(round(state.pointer_size * view._scene.width() / 4) + 2, 0)
    QTest.keyClick(app.view, Qt.Key.Key_P, Qt.KeyboardModifier.ShiftModifier)
    enlarged = view.grab().toImage()
    enlarged.save(str(tmp_path / "enlarged-crosshair.png"))
    assert pixel(enlarged, beyond_cross).red() > pixel(cross, beyond_cross).red() + 100
    QTest.keyClick(app.view, Qt.Key.Key_P)
    # Laser and spotlight render on both windows from a shared page coordinate.
    QTest.keyClick(app.view, Qt.Key.Key_L)
    move(qapp, view, point)
    laser = view.grab().toImage()
    assert state.pointer_mode == 1
    assert view._from_page(state.pointer).x() == pytest.approx(point.x(), abs=1)
    assert view._from_page(state.pointer).y() == pytest.approx(point.y(), abs=1)
    assert pixel(laser, QPointF(point)).red() > pixel(plain, QPointF(point)).red()
    QTest.keyClick(app.view, Qt.Key.Key_L)
    lit = view.grab().toImage()
    outside = QPointF(point + QPoint(65, 0))
    assert pixel(lit, outside).blue() < pixel(plain, outside).blue() * .6
    assert pixel(lit, QPointF(point)).blue() == pytest.approx(pixel(plain, outside).blue(), abs=5)
    original_radius = state.pointer_size
    QTest.keyClick(app.view, Qt.Key.Key_P, Qt.KeyboardModifier.ShiftModifier)
    assert state.pointer_size > original_radius
    app.view.repaint()
    presenter_image = app.view.grab().toImage()
    presenter_point = app.view._from_page(state.pointer)
    assert pixel(presenter_image, presenter_point).blue() > 100
    lit.save(str(tmp_path / "spotlight.png"))
    presenter_image.save(str(tmp_path / "presenter-spotlight.png"))
    QTest.keyClick(app.view, Qt.Key.Key_Period)
    black = view.grab().toImage()
    assert pixel(black, QPointF(point)).name() == "#000000"
    assert pixel(black, outside).name() == "#000000"
    assert state.surface == Surface.BLACK
    QTest.keyClick(app.view, Qt.Key.Key_Period)
    # Exercise the actual timeout connection without a five-second test delay.
    state.pointer_timer.start(1)
    qtbot.waitUntil(lambda: not state.pointer_visible)
    restored = view.grab().toImage()
    assert pixel(restored, outside).blue() == pixel(plain, outside).blue()
    assert state.page == 0


def test_notes_zoom_reset_preserves_numeric_page_input(presenter):
    app, state = presenter, presenter.session
    QTest.keyClick(app.view, Qt.Key.Key_Plus)
    assert state.notes_scale > 1
    QTest.keyClick(app.view, Qt.Key.Key_0)
    assert state.notes_scale == 1 and state.digits == ""
    # Zero continues a page number already being entered.
    QTest.keyClick(app.view, Qt.Key.Key_1)
    QTest.keyClick(app.view, Qt.Key.Key_0)
    assert state.digits == "10" and state.page == 0
    QTest.keyClick(app.view, Qt.Key.Key_Return)
    assert state.page == 2 and state.digits == ""  # clamped to this fixture's last page
    state.notes_scale, state.notes_scroll = 2, 30
    view_menu = next(action.menu() for action in app.presenter.menuBar().actions() if action.text() == "View")
    next(action for action in view_menu.actions() if action.text() == "Reset notes / web zoom").trigger()
    assert state.notes_scale == 1 and state.notes_scroll == 0
