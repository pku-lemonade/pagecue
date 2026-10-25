from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from pagecue.app import Presenter
from pagecue.document import Media
from pagecue.model import Surface


@pytest.mark.parametrize("interrupt", ["navigate", "reload", "board", "escape"])
def test_delayed_video_link_does_not_interrupt_new_context(qapp, qtbot, deck, monkeypatch, interrupt):
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    app.open(deck)
    app.video_mode = "auto"
    callbacks, resolved = [], []
    monkeypatch.setattr(app.video_router.requests, "get", lambda url, callback: callbacks.append(callback))
    app.video_router.resolved.connect(resolved.append)
    app.open_web("https://youtu.be/test")
    if interrupt == "navigate":
        app.session.navigate(1)
    elif interrupt == "reload":
        app.reload()
    elif interrupt == "board":
        app.session.toggle_surface(Surface.BOARD)
    else:
        QTest.keyClick(app.view, Qt.Key.Key_Escape)
    callbacks[0]([["video.example", {"api": True}]], None)
    assert resolved == []
    assert app.web is None
    app.session.close()
    app.media.close()


def test_application_commands_and_state_preserving_reload(qapp, qtbot, deck):
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    app.show()
    assert app.open(deck)
    qtbot.waitUntil(lambda: len(app.session.images.cache) > 0)
    QTest.keyClick(app.view, Qt.Key.Key_Right)
    assert app.session.page == 1
    QTest.keyClick(app.slide, Qt.Key.Key_Left)
    assert app.session.page == 0
    QTest.keyClick(app.view, Qt.Key.Key_3)
    QTest.keyClick(app.view, Qt.Key.Key_Return)
    assert app.session.page == 2
    QTest.keyClick(app.view, Qt.Key.Key_T)
    assert app.session.clock.started is not None
    QTest.keyClick(app.view, Qt.Key.Key_T, Qt.KeyboardModifier.ShiftModifier)
    assert app.session.clock.show_wall
    assert app.session.clock.started is not None
    QTest.keyClick(app.view, Qt.Key.Key_T, Qt.KeyboardModifier.ShiftModifier)
    assert not app.session.clock.show_wall
    app.reload()
    assert app.session.page == 2
    assert app.session.clock.started is not None
    QTest.keyClick(app.view, Qt.Key.Key_B)
    assert app.session.surface == Surface.BOARD
    QTest.keyClick(app.view, Qt.Key.Key_S)
    assert app.session.surface == Surface.SLIDES
    QTest.keyClick(app.view, Qt.Key.Key_W, Qt.KeyboardModifier.ControlModifier)
    assert app.slide.camera_position.startswith("top")
    app.session.tick.stop()
    app.media.close()


def test_hide_restore_keeps_both_windows_available(qapp, qtbot, deck):
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    app.show()
    assert app.open(deck)
    app.hide_all()
    assert app.presenter.isMinimized() and app.audience.isMinimized()
    app.presenter.showNormal()
    qtbot.waitUntil(lambda: not app.audience.isMinimized())
    assert not app._hidden
    app.session.close()


def test_audience_only_fullscreen_and_restore_on_two_screen_topology(qapp, qtbot, deck, monkeypatch):
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    app.show()
    app.open(deck)
    # Exercise the multi-screen decision without claiming physical monitor QA.
    screens = [SimpleNamespace(name=lambda: "presenter"), SimpleNamespace(name=lambda: "audience")]
    monkeypatch.setattr(qapp, "screens", lambda: screens)
    placements = []
    monkeypatch.setattr(app, "_place", lambda window, screen: placements.append((window, screen)))
    QTest.mouseDClick(app.slide, Qt.MouseButton.LeftButton)
    assert app.fullscreen and app.audience_only_fullscreen
    assert app.audience.isFullScreen() and not app.presenter.isFullScreen()
    app.hide_all()
    app.restore_all()
    assert app.fullscreen and app.audience_only_fullscreen
    assert app.audience.isFullScreen() and not app.presenter.isFullScreen()
    QTest.keyClick(app.view, Qt.Key.Key_F5)
    assert app.fullscreen and not app.audience_only_fullscreen
    assert app.audience.isFullScreen() and app.presenter.isFullScreen()
    QTest.keyClick(app.view, Qt.Key.Key_Escape)
    assert not app.fullscreen
    assert not app.audience.isFullScreen() and not app.presenter.isFullScreen()
    app.session.close()
    app.media.close()


def test_linked_gif_uses_actual_decoder(qapp, qtbot, tmp_path):
    from pagecue.media import MediaPlayer
    path = tmp_path / "colors.gif"
    Image.new("RGB", (64, 64), "red").save(path, save_all=True,
        append_images=[Image.new("RGB", (64, 64), "blue")], duration=150, loop=0)
    player = MediaPlayer()
    frames = []
    player.frame.connect(lambda image: frames.append(image.copy()))
    player.load(Media(path.name, path=path))
    qtbot.waitUntil(lambda: len(frames) >= 2)
    assert any(image.pixelColor(30, 30).red() > 200 for image in frames)
    assert any(image.pixelColor(30, 30).blue() > 200 for image in frames)
    player.step(-1)
    assert player.gif.currentFrameNumber() == 0
    player.close()
