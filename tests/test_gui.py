from pathlib import Path
from PySide6.QtCore import QSettings, Qt
from pagecue.canvas import Canvas
from pagecue.session import Session


def test_settings_override_and_recent_page_are_isolated(qtbot, deck, tmp_path):
    session = Session()
    assert session.settings.format() == QSettings.Format.IniFormat
    assert Path(session.settings.fileName()).is_relative_to(tmp_path / "settings")
    session.open(deck)
    session.go(2)
    session.save()
    restored = Session()
    restored.open(deck)
    assert restored.page == 2
    restored.settings.setValue("recent/" + str(deck.resolve()), "invalid page")
    restored.open(deck)
    assert restored.page == 0
    session.close()
    restored.close()


def test_qt_renders_real_pdf_and_two_views(qtbot, deck, tmp_path):
    session = Session()
    session.open(deck)
    presenter = Canvas(session, True)
    audience = Canvas(session, False)
    qtbot.addWidget(presenter)
    qtbot.addWidget(audience)
    presenter.resize(1180, 780)
    audience.resize(960, 540)
    presenter.show()
    audience.show()
    qtbot.waitUntil(lambda: len(session.images.cache) >= 3, timeout=10000)
    image = audience.grab().toImage()
    assert image.pixelColor(400, 300).blue() > image.pixelColor(400, 300).red()
    assert not presenter.notes_box.isEmpty()
    assert audience.notes_box.isEmpty()
    presenter.grab().save(str(tmp_path / "presenter.png"))
    audience.grab().save(str(tmp_path / "audience.png"))
    session.go(1)
    qtbot.waitUntil(lambda: any(key[0] == 1 for key in session.images.cache), timeout=10000)
    session.tick.stop()


def test_failed_reload_preserves_live_document(qtbot, deck):
    session = Session()
    session.open(deck)
    session.go(1)
    original = session.snapshot
    generation = session.images.generation
    deck.write_bytes(b"partial PDF still being written")
    try:
        session.reload()
    except Exception:
        pass
    else:
        raise AssertionError("An invalid PDF must fail reload")
    assert session.snapshot is original
    assert session.page == 1
    assert session.images.generation == generation
    session.tick.stop()
