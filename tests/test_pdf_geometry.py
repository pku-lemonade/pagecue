"""Original PDF landmarks verify crop/rotation against actual Qt rasterization."""

from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link
from pypdf.generic import RectangleObject
from reportlab.pdfgen import canvas
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest

from presenteriyaki.app import Presenter


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("crop,visible_size,center", [
    ((80, 40, 520, 360), (440, 320), (3 / 11, 21 / 32)),
    # The PDF visible area is the intersection of CropBox and MediaBox.
    ((-80, -40, 520, 360), (520, 360), (5 / 13, 7 / 12)),
], ids=["offset-crop", "crop-outside-media"])
def test_rotated_cropped_landmark_and_link(qapp, qtbot, tmp_path, rotation, crop, visible_size, center):
    source = BytesIO()
    painter = canvas.Canvas(source, pagesize=(600, 400))
    for number in range(3):
        painter.setFillColor("#18372b")
        painter.rect(0, 0, 600, 400, fill=1, stroke=0)
        painter.setFillColor("#ee3322")
        painter.rect(160, 120, 80, 60, fill=1, stroke=0)
        painter.showPage()
    painter.save()
    writer = PdfWriter(clone_from=PdfReader(source))
    writer.pages[0].cropbox = RectangleObject(crop)
    writer.pages[0].rotate(rotation)
    writer.add_annotation(0, Link(rect=(160, 120, 240, 180), target_page_index=2))
    path = tmp_path / "geometry.pdf"
    writer.write(path)
    original = path.read_bytes()
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    app.session.notes_layout = "off"
    app.show()
    app.open(path)
    try:
        expected_size = visible_size[::-1] if rotation in (90, 270) else visible_size
        qt_size = app.session.images.document.pagePointSize(0)
        assert (qt_size.width(), qt_size.height()) == pytest.approx(expected_size)
        assert app.session.snapshot.pages[0].size == pytest.approx(expected_size)
        u, v = center
        location = {0: (u, v), 90: (1 - v, u), 180: (1 - u, 1 - v), 270: (v, 1 - u)}[rotation]
        app.session.zoom, app.session.pan = 1.2, QPointF(.03, -.02)
        app.session.changed.emit()
        qtbot.waitUntil(lambda: bool(app.session.images.cache) and not app.session.images.pending)
        view = app.slide
        view.repaint()
        point = view._from_page(QPointF(*location))
        rendered = view.grab().toImage()
        ratio = rendered.devicePixelRatio()
        color = rendered.pixelColor(round(point.x() * ratio), round(point.y() * ratio))
        assert color.name() == "#ee3322", color.name()
        action = view._action_at(point)
        assert action is not None and action.kind == "page" and action.value == 2
        rendered.save(str(tmp_path / "rotated-crop.png"))
        QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=point.toPoint())
        assert app.session.page == 2  # empty-space navigation would only reach page 2 (index 1)
        assert path.read_bytes() == original
    finally:
        app.session.close()
        app.media.close()
