from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtTest import QTest
from PySide6.QtGui import QFileOpenEvent

from presenteriyaki.app import Presenter
from presenteriyaki.document import Media
from presenteriyaki.model import Surface
from presenteriyaki.services import Release


def test_packaged_notice_menu_opens_the_local_index(qapp, qtbot, tmp_path, monkeypatch):
    from presenteriyaki import app as module
    index = tmp_path / "licenses/dependencies/index.html"
    index.parent.mkdir(parents=True)
    index.write_text("Original notice-index fixture")
    monkeypatch.setattr(module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(module.sys, "_MEIPASS", str(tmp_path), raising=False)
    opened = []
    monkeypatch.setattr(module.QDesktopServices, "openUrl", lambda url: opened.append(Path(url.toLocalFile())))
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    help_menu = app.presenter.menuBar().actions()[-1].menu()
    action = next(action for action in help_menu.actions() if action.text() == "Third-party notices")
    assert action.isEnabled()
    action.trigger()
    assert opened == [index]
    app.session.close()
    app.media.close()


def test_native_file_open_ignores_launcher_arguments_and_accepts_extensionless_pdf(qapp, qtbot, deck, tmp_path):
    script = tmp_path / "launcher.py"
    script.write_text("print('This is not a presentation')")
    with qtbot.assertNotEmitted(qapp.file_opened):
        qapp.sendEvent(qapp, QFileOpenEvent(str(script)))
        qapp.sendEvent(qapp, QFileOpenEvent("--junitxml=qa/tests.xml"))
    extensionless = tmp_path / "slides without extension"
    extensionless.write_bytes(deck.read_bytes())
    for path in (deck, extensionless):
        with qtbot.waitSignal(qapp.file_opened, timeout=1000) as signal:
            qapp.sendEvent(qapp, QFileOpenEvent(str(path)))
        assert signal.args == [str(path)]


def test_update_notification_click_opens_current_release_once(qapp, qtbot, monkeypatch):
    # Simulated delivery: never enable OS notifications or open a real browser.
    from presenteriyaki import app as module
    class Tray(QObject):
        messageClicked = Signal()
        isSystemTrayAvailable = staticmethod(lambda: True)
        supportsMessages = staticmethod(lambda: True)
        def __init__(self, icon, parent):
            super().__init__(parent)
            self.messages = []
        def show(self):
            pass
        def showMessage(self, title, message):
            self.messages.append((title, message))
        def hide(self):
            pass
    monkeypatch.setattr(module, "QSystemTrayIcon", Tray)
    opened = []
    monkeypatch.setattr(module.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    first = Release("0.2.0", "https://github.com/pku-lemonade/presenteriyaki/releases/tag/v0.2.0", True)
    second = Release("0.3.0", "https://github.com/pku-lemonade/presenteriyaki/releases/tag/v0.3.0", True)
    app._update_result(first, False)
    tray = app.update_tray
    tray.messageClicked.emit()
    assert opened == [first.url]
    app._update_result(second, False)
    assert app.update_tray is tray and len(tray.messages) == 2
    tray.messageClicked.emit()
    assert opened == [first.url, second.url]
    app._closed = True
    tray.messageClicked.emit()
    assert opened == [first.url, second.url]
    app.session.close()
    app.media.close()


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
    assert app.audience.presentation_fullscreen and not app.presenter.presentation_fullscreen
    app.hide_all()
    app.restore_all()
    assert app.fullscreen and app.audience_only_fullscreen
    assert app.audience.presentation_fullscreen and not app.presenter.presentation_fullscreen
    QTest.keyClick(app.view, Qt.Key.Key_F5)
    assert app.fullscreen and not app.audience_only_fullscreen
    assert app.audience.presentation_fullscreen and app.presenter.presentation_fullscreen
    QTest.keyClick(app.view, Qt.Key.Key_Escape)
    assert not app.fullscreen
    assert not app.audience.presentation_fullscreen and not app.presenter.presentation_fullscreen
    app.session.close()
    app.media.close()


def test_linked_gif_uses_actual_decoder(qapp, qtbot, tmp_path):
    from presenteriyaki.media import MediaPlayer
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
