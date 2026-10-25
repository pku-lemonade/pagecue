from PySide6.QtCore import QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFileDialog, QInputDialog

from presenteriyaki.app import Presenter


def test_welcome_opens_pdf_and_recent_files_reopen_it(qapp, qtbot, deck, monkeypatch):
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    app.show()
    assert app.view.welcome.isVisible()
    assert app.slide.welcome is None
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(deck), "PDF"))
    QTest.mouseClick(app.view.welcome.open_button, Qt.MouseButton.LeftButton)
    assert app.session.snapshot.path == deck
    assert not app.view.welcome.isVisible()
    app.session.settings.setValue("recent-files", [str(deck), str(deck.parent / "deleted.pdf")])
    app._recent_files()
    actions = app.recent_menu.actions()
    assert len(actions) == 1 and actions[0].text() == deck.name
    app.session.navigate(1)
    actions[0].trigger()
    assert app.session.snapshot.path == deck
    assert app.session.page == 1
    app.session.close()
    app.media.close()


def test_clock_menu_and_keyboard_share_timer_state(qapp, qtbot, deck, monkeypatch):
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    app.show()
    app.open(deck)
    qapp.processEvents()
    app.view.repaint()
    QTest.mouseClick(app.view, Qt.MouseButton.LeftButton, pos=app.view.clock_box.center().toPoint())
    assert app.session.clock.started is not None
    assert app.timer_action.text() == "Pause timer"
    app.timer_action.trigger()
    assert app.session.clock.started is None
    assert app.timer_action.text() == "Resume timer"
    elapsed = app.session.clock.elapsed
    monkeypatch.setattr(QInputDialog, "getDouble", lambda *args: (12.5, True))
    app.set_duration()
    assert app.session.clock.duration == 750
    assert app.session.clock.elapsed == elapsed
    QTest.keyClick(app.view, Qt.Key.Key_Z)
    assert app.session.clock.elapsed == 0
    assert app.timer_action.text() == "Start timer"
    app.session.close()
    app.media.close()


def test_cancel_page_entry_preserves_fullscreen_and_leaving_clears_preview(qapp, qtbot, deck):
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    app.show()
    app.open(deck)
    app.toggle_fullscreen()
    QTest.keyClick(app.view, Qt.Key.Key_2)
    QTest.keyClick(app.view, Qt.Key.Key_Escape)
    assert not app.session.digits and app.session.page == 0
    assert app.fullscreen
    app.session.preview = 2
    qapp.sendEvent(app.view, QEvent(QEvent.Type.Leave))
    assert app.session.preview is None
    QTest.keyClick(app.view, Qt.Key.Key_Escape)
    assert not app.fullscreen
    app.session.close()
    app.media.close()
