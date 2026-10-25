import json
import pytest

from pagecue.model import Ink, Navigation, Stroke, TalkClock
from pagecue.notes import choose, decode


def test_navigation_keeps_physical_overlay_pages_and_history():
    nav = Navigation(5, ["1", "2", "2", "2", "3"], [0, 4])
    assert nav.frames == [0, 1, 4]
    nav.go(2)
    assert list(nav.overlay_pages(2)) == [1, 2]
    nav.adjacent(1, "frame")
    assert nav.page == 4
    nav.history(True)
    assert nav.page == 2
    nav.history(False)
    assert nav.page == 4
    nav.adjacent(-1, "section")
    assert nav.page == 0
    nav.go(999)
    assert nav.page == 4


def test_clock_pause_uses_elapsed_not_tick_count():
    now = [100.0]
    clock = TalkClock(duration=120, clock=lambda: now[0])
    clock.toggle()
    now[0] += 35
    assert clock.text() == "00:01:25"
    clock.toggle()
    now[0] += 500
    assert clock.elapsed == 35
    clock.toggle()
    now[0] += 90
    assert clock.text() == "−00:00:05"
    clock.reset()
    assert clock.elapsed == 0


def test_empty_embedded_notes_do_not_revive_sidecar(tmp_path):
    path = tmp_path / "talk.pdf"
    sidecar = {"pdfpcFormat": 2, "pages": [{"idx": 0, "note": "stale"}]}
    path.with_suffix(".pdfpc").write_text(json.dumps(sidecar))
    result = choose(path, 2, [("talk.pdfpc", b'{"pdfpcFormat":2,"pages":[]}')], {1: "PDF note"})
    assert result.pages == {1: "PDF note"}
    assert result.source == "embedded: talk.pdfpc"


def test_notes_validate_indexes_without_logging_note_content():
    value = {"pdfpcFormat": 2, "pages": [
        {"idx": True, "note": "private"}, {"idx": 8, "note": "private"},
        {"idx": 1, "note": "中文\r\nHello"}, {"idx": 1, "note": "Another paragraph"}]}
    notes, warnings = decode(json.dumps(value).encode(), 3)
    assert notes == {1: "中文\nHello\n\nAnother paragraph"}
    assert len(warnings) == 2
    assert all("private" not in item for item in warnings)


def test_ink_selection_changes_only_selected_strokes():
    ink = Ink()
    selected = Stroke([(0.1, .2), (.2, .3)])
    unchanged = Stroke([(.5, .5)])
    ink.add(0, selected)
    ink.add(1, unchanged)
    ink.selected = [selected]
    ink.transform_selected(dx=.1)
    assert selected.points[0] == pytest.approx((.2, .2))
    assert unchanged.points == [(.5, .5)]
    ink.erase([0, 1])
    assert ink.visible([0, 1]) == [unchanged]
