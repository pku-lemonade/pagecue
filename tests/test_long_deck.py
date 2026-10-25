"""Long-deck navigation, rail interaction and asynchronous rendering acceptance."""

import hashlib
import json
import time

from reportlab.pdfgen import canvas
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest

from pagecue.app import Presenter


def test_long_deck_rapid_navigation_rail_and_render_budget(qapp, qtbot, tmp_path):
    path = tmp_path / "long deck 讲稿.pdf"
    count = 400
    colors = ("#2354a1", "#2e8867", "#b45637", "#823f98")
    pdf = canvas.Canvas(str(path), pagesize=(960, 540))
    for page in range(count):
        # Different page proportions exercise the variable-height thumbnail rail.
        width, height = (720, 540) if page % 7 == 0 else (960, 540)
        pdf.setPageSize((width, height))
        pdf.setFillColor(colors[page % len(colors)])
        pdf.rect(0, 0, width, height, fill=1, stroke=0)
        pdf.setFillColor("white")
        pdf.setFont("Helvetica", 36)
        pdf.drawString(45, height - 70, f"Original long-deck fixture: {page + 1}")
        pdf.showPage()
    pdf.save()
    path.with_suffix(".pdfpc").write_text(json.dumps({"pdfpcFormat": 2, "pages": [
        {"idx": page, "note": f"Notes for physical page {page + 1}"} for page in range(count)]}), encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    app.show()
    started = time.monotonic()
    assert app.open(path)
    view, audience, state = app.view, app.slide, app.session
    observations = []

    def rendered_color():
        image = audience.grab().toImage()
        point = audience._from_page(QPointF(.5, .6))
        dpr = image.devicePixelRatio()
        return image.pixelColor(round(point.x() * dpr), round(point.y() * dpr)).name()

    def wait_for_page(page):
        qtbot.waitUntil(lambda: any(key[0] == page for key in state.images.cache)
                       and rendered_color() == colors[page % len(colors)], timeout=15000)
        view.repaint()
        assert state.page == page
        assert state.snapshot.notes.pages[page] == f"Notes for physical page {page + 1}"
        assert view.rail.intersects(view.thumb_rects[page])
        observations.append({"page": page, "cached_bytes": state.images.cache_bytes,
                             "cached_images": len(state.images.cache), "pending": len(state.images.pending)})

    wait_for_page(0)
    first_frame_seconds = time.monotonic() - started
    # Issue requests faster than the rasterizer finishes; final pixels must match
    # the selected page, and browsing must not render/cache the entire document.
    for page in [100, 203, 45, 350, 127, 398, 6, 270, 31, 399]:
        state.go(page)
        view.repaint()
        audience.repaint()
    wait_for_page(399)
    assert state.images.cache_bytes <= state.images.budget
    assert len({key[0] for key in state.images.cache}) < count // 4
    assert len(state.images.pending) <= 12
    view.grab().save(str(tmp_path / "last-page.png"))

    # Scrolling the rail must preserve the current page, then clicking a visible
    # thumbnail must select its actual page despite the changed rail offset.
    position = view.rail.center()
    event = QWheelEvent(position, view.mapToGlobal(position.toPoint()), QPoint(), QPoint(0, 600),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    qapp.sendEvent(view, event)
    view.repaint()
    assert state.page == 399
    target = next(page for page, rect in view.thumb_rects.items()
                  if 0 < rect.center().y() < view.height() and page % 4 != 399 % 4)
    point = view.thumb_rects[target].center().toPoint()
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=point)
    wait_for_page(target)
    QTest.keyClick(view, Qt.Key.Key_Home)
    wait_for_page(0)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    (tmp_path / "result.json").write_text(json.dumps({
        "pages": count, "passed": True, "first_frame_seconds": first_frame_seconds,
        "total_seconds": time.monotonic() - started, "observations": observations,
        "source_unchanged": True,
    }, indent=2), encoding="utf-8")
    state.close()
    app.media.close()
