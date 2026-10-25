"""Sparse, custom-painted presenter and audience views."""

import math
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QRadialGradient, QTextDocument
from PySide6.QtWidgets import QWidget, QToolTip

from .model import Stroke, Surface
from .typography import ui_font


HELP = [
    ("← → / click", "previous / next page"), ("Ctrl/⌘ + ← →", "previous / next frame"),
    ("Alt + arrows", "history back / forward"), ("0–9 ↵", "go to physical page"),
    ("F5 / Esc", "fullscreen / windowed"), ("X", "swap screens"),
    ("T / Shift+T / Z", "timer / clock / reset"), ("[ ] / { }", "adjust talk duration"),
    ("+ −", "notes text size"), ("R", "reload PDF and notes"),
    (". / B", "blackout / whiteboard"), ("L / P", "pointer mode / size"),
    ("drag / Shift", "draw / draw immediately"), ("Alt + drag", "select ink"),
    ("Shift + drag", "move selected ink"), ("⌘/Ctrl + drag", "pan slide"),
    ("⌘/Ctrl + wheel", "zoom slide"), ("C / E / ⌫", "color / clear / erase last"),
    ("V / M / W", "camera / media / web"), ("?", "toggle this help"),
]


def fit_rect(box: QRectF, width: float, height: float) -> QRectF:
    ratio = min(box.width() / max(width, 1), box.height() / max(height, 1))
    result = QRectF(0, 0, width * ratio, height * ratio)
    result.moveCenter(box.center())
    return result


class Canvas(QWidget):
    command = Signal(object)
    files_dropped = Signal(str)

    def __init__(self, session, presenter, parent=None):
        super().__init__(parent)
        self.session = session
        self.presenter = presenter
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)
        self.session.changed.connect(self._refresh)
        self.session.document_changed.connect(self._new_document)
        self.current_box = QRectF()
        self.notes_box = QRectF()
        self.next_box = QRectF()
        self.help_box = QRectF()
        self.help_scroll = 0.0
        self.rail = QRectF()
        self.thumb_rects = {}
        self.thumb_scroll = 0.0
        self._last_page = -1
        self._drag = None
        self._press = QPointF()
        self._previous = QPointF()
        self._stroke = None
        self._scene = QRectF()
        self._crop = QRectF(0, 0, 1, 1)
        self.media_image = None
        self.media_rect = None
        self.posters = {}
        self.camera_image = None
        self.camera_position = "bottom-right"
        self.camera_large = False
        self.camera_width = .28
        self.camera_opacity = .8
        self._animation_last = {}
        self._cursor_context = None

    def _refresh(self):
        context = (id(self.session.snapshot), self.session.page, self.session.surface)
        if context != self._cursor_context:
            self._cursor_context = context
            self.setCursor(Qt.CursorShape.ArrowCursor)
            QToolTip.hideText()
        self.update()

    def _new_document(self):
        self.thumb_scroll = 0
        self._last_page = -1
        self._drag = None
        self._animation_last.clear()
        self.update()

    def _text(self, painter, rect, text, size, color="#e5e5e5", flags=None):
        font = ui_font(size)
        font.setWeight(QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(rect, flags or (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor("#101113") if self.presenter else QColor("black"))
        if self.session.snapshot is None:
            self._text(painter, QRectF(self.rect()), "Drop a PDF to begin\n⌘/Ctrl O to open", 22,
                       flags=Qt.AlignmentFlag.AlignCenter)
            return
        if self.presenter:
            self._paint_presenter(painter)
        else:
            self.current_box = QRectF(self.rect())
            self._paint_current(painter)

    def _paint_presenter(self, painter):
        width, height = self.width(), self.height()
        rail_width = max(82, min(120, width * .10))
        margin = max(18, min(42, width * .028))
        content = width - rail_width - margin * 3
        left_width = content * .68
        top = max(64, height * .09)
        page = self.session.snapshot.pages[self.session.page]
        ratio = page.size[0] / page.size[1] / (2 if page.notes_crop else 1)
        current_height = min(left_width / ratio, height * .56)
        self.current_box = QRectF(margin, top, left_width, current_height)
        self.next_box = QRectF(margin * 2 + left_width, top, content - left_width, current_height * .65)
        self.notes_box = QRectF(margin, top + current_height + margin * .7,
                               left_width, max(20, height - top - current_height - margin * 1.4))
        self.rail = QRectF(width - rail_width, 0, rail_width, height)
        self._text(painter, QRectF(margin, 12, left_width * .65, top - 20), self.session.clock.text(),
                   min(34, width * .027), "#efb267" if self.session.clock.duration and
                   self.session.clock.elapsed > self.session.clock.duration else "#f3f3f3")
        label = f"{page.label}   {self.session.page + 1}/{len(self.session.snapshot.pages)}"
        if self.session.digits:
            label = f"Go to {self.session.digits} ↵"
        self._text(painter, QRectF(margin + left_width * .55, 12, left_width * .45, top - 20), label,
                   12, "#999da5", Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._paint_current(painter)
        next_page = self.session.preview if self.session.preview is not None else self.session.page + 1
        if next_page < len(self.session.snapshot.pages):
            self._paint_pdf(painter, next_page, self.next_box, navigation=False)
            self._text(painter, QRectF(self.next_box.x(), self.next_box.bottom() + 6,
                                      self.next_box.width(), 22), f"NEXT  ·  {next_page + 1}", 9, "#777c86")
        self._paint_notes(painter)
        self.help_box = QRectF()
        if self.session.show_help:
            self._paint_help(painter)
        self._paint_thumbnails(painter)

    def _paint_help(self, painter):
        top = self.next_box.bottom() + 54
        self.help_box = QRectF(self.next_box.x(), top, self.next_box.width(), max(0, self.height() - top - 16))
        font_size = min(12, max(10, self.help_box.width() / 22))
        metrics = QFontMetricsF(ui_font(font_size))
        split = min(110, self.help_box.width() * .40)
        widths = (split - 8, self.help_box.width() - split - 7)
        flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
        rows = []
        for key, description in HELP:
            height = max(metrics.boundingRect(QRectF(0, 0, width, 1000), int(flags), text).height()
                         for width, text in zip(widths, (key, description))) + 6
            rows.append((key, description, height))
        maximum = max(0, sum(row[2] for row in rows) - self.help_box.height())
        self.help_scroll = min(maximum, max(0, self.help_scroll))
        self._text(painter, QRectF(self.help_box.x(), top - 23, self.help_box.width(), 18),
                   "SHORTCUTS · SCROLL" if maximum else "SHORTCUTS", 9, "#777c86")
        painter.save()
        painter.setClipRect(self.help_box)
        y = self.help_box.top() - self.help_scroll
        for key, description, height in rows:
            self._text(painter, QRectF(self.help_box.x(), y, widths[0], height), key, font_size, "#adb3bf", flags)
            self._text(painter, QRectF(self.help_box.x() + split, y, widths[1], height),
                       description, font_size, "#858a94", flags)
            y += height
        painter.restore()
        if maximum:
            painter.fillRect(QRectF(self.help_box.right() - 2,
                                   self.help_box.top() + self.help_scroll / maximum * (self.help_box.height() - 24),
                                   2, 24), QColor("#656b77"))

    def _paint_notes(self, painter):
        text = self.session.snapshot.notes.pages.get(self.session.page, "")
        if not text:
            return
        doc = QTextDocument()
        doc.setDefaultFont(ui_font(max(17, self.width() * .018) * self.session.notes_scale))
        doc.setPlainText(text)
        doc.setTextWidth(self.notes_box.width())
        maximum = max(0, doc.size().height() - self.notes_box.height())
        self.session.notes_scroll = max(0, min(maximum, self.session.notes_scroll))
        painter.save()
        painter.setClipRect(self.notes_box)
        painter.translate(self.notes_box.topLeft() - QPointF(0, self.session.notes_scroll))
        # Default palette is dark here; specify foreground for plain text layout.
        from PySide6.QtGui import QAbstractTextDocumentLayout, QPalette
        context = QAbstractTextDocumentLayout.PaintContext()
        context.palette.setColor(QPalette.ColorRole.Text, QColor("#e7e8eb"))
        doc.documentLayout().draw(painter, context)
        painter.restore()
        if maximum > 0:
            painter.fillRect(QRectF(self.notes_box.right() - 2,
                                   self.notes_box.top() + self.session.notes_scroll / maximum * (self.notes_box.height() - 28),
                                   2, 28), QColor("#656b77"))

    def _paint_thumbnails(self, painter):
        painter.fillRect(self.rail, QColor("#181a1e"))
        self.thumb_rects = {}
        width = self.rail.width() - 16
        heights = []
        for page in self.session.snapshot.pages:
            aspect = page.size[0] / page.size[1] / (2 if page.notes_crop else 1)
            heights.append(width / aspect + 24)
        total = sum(heights) + 10
        if self._last_page != self.session.page:
            page_top = sum(heights[:self.session.page])
            page_bottom = page_top + heights[self.session.page]
            if page_top < self.thumb_scroll:
                self.thumb_scroll = page_top
            elif page_bottom > self.thumb_scroll + self.height():
                self.thumb_scroll = page_bottom - self.height()
            self._last_page = self.session.page
        self.thumb_scroll = min(max(0, self.thumb_scroll), max(0, total - self.height()))
        y = 8 - self.thumb_scroll
        painter.save()
        painter.setClipRect(self.rail)
        for index, height in enumerate(heights):
            rect = QRectF(self.rail.x() + 8, y, width, height - 24)
            self.thumb_rects[index] = QRectF(rect.x(), y, width, height)
            if y + height > 0 and y < self.height():
                self._paint_pdf(painter, index, rect, navigation=False)
                if index == self.session.page:
                    painter.setPen(QPen(QColor("#e6cf6b"), 2))
                    painter.drawRect(rect.adjusted(-1, -1, 1, 1))
                self._text(painter, QRectF(rect.x(), rect.bottom(), width, 21), str(index + 1), 9,
                           "#e6cf6b" if index == self.session.page else "#818792")
            y += height
        painter.restore()

    def _paint_pdf(self, painter, index, box, navigation):
        info = self.session.snapshot.pages[index]
        crop = QRectF(0, 0, .5 if info.notes_crop else 1, 1)
        scene = fit_rect(box, info.size[0] * crop.width(), info.size[1])
        if navigation:
            zoom, pan = self.session.zoom, self.session.pan
            center = scene.center() + QPointF(pan.x() * scene.width(), pan.y() * scene.height())
            scene.setSize(scene.size() * zoom)
            scene.moveCenter(center)
            self._scene, self._crop = scene, crop
        image = self.session.images.get(index, scene.width() / crop.width(), scene.height(), self.devicePixelRatioF())
        painter.save()
        painter.setClipRect(box)
        painter.fillRect(scene, QColor("#fafafa"))
        if image is not None:
            source = QRectF(crop.x() * image.width(), crop.y() * image.height(),
                            crop.width() * image.width(), crop.height() * image.height())
            painter.drawImage(scene, image, source)
        for action in info.actions:
            if action.kind == "media" and action.value.key in self.posters:
                x, y, width, height = action.rect
                target = QRectF(scene.x() + (x - crop.x()) / crop.width() * scene.width(),
                                scene.y() + (y - crop.y()) / crop.height() * scene.height(),
                                width / crop.width() * scene.width(), height / crop.height() * scene.height())
                poster = self.posters[action.value.key]
                painter.drawImage(fit_rect(target, poster.width(), poster.height()), poster)
        self._paint_animations(painter, index, scene, crop)
        painter.restore()

    def _paint_animations(self, painter, page, scene, crop):
        def position(rect):
            x, y, width, height = rect
            return QRectF(scene.x() + (x - crop.x()) / crop.width() * scene.width(),
                          scene.y() + (y - crop.y()) / crop.height() * scene.height(),
                          width / crop.width() * scene.width(), height / crop.height() * scene.height())
        for state in self.session.animations.values():
            if state.spec.page != page:
                continue
            rect = position(state.spec.rect)
            if state.visible:
                frame = self.session.animation_images.get(state.spec.frames[state.frame], rect.width(), rect.height(), self.devicePixelRatioF())
                if frame is not None:
                    self._animation_last[state.spec.identifier] = frame
                displayed = self._animation_last.get(state.spec.identifier)
                if displayed is not None:
                    painter.drawImage(rect, displayed)
            if state.direction:
                next_index = (state.frame + state.direction) % len(state.spec.frames)
                self.session.animation_images.get(state.spec.frames[next_index], rect.width(), rect.height(), self.devicePixelRatioF())
            labels = {"EndLeft": "|◀", "EndRight": "▶|", "StepLeft": "◀", "StepRight": "▶",
                      "Minus": "−", "Plus": "+", "Reset": "1×"}
            for control in state.spec.controls:
                area = position(control.rect)
                painter.fillRect(area.adjusted(.5, .5, -.5, -.5), QColor("#ededed"))
                painter.setPen(QPen(QColor("#777777"), .5))
                painter.drawRect(area)
                label = labels.get(control.command)
                if label is None:
                    direction = -1 if control.command.endswith("Left") else 1
                    label = "Ⅱ" if state.direction == direction else "◀" if direction < 0 else "▶"
                self._text(painter, area, label, max(8, area.height() * .58), "#252525", Qt.AlignmentFlag.AlignCenter)

    def _paint_current(self, painter):
        surface = self.session.surface
        painter.save()
        painter.setClipRect(self.current_box)
        if surface == Surface.BOARD:
            self._scene = QRectF(self.current_box)
            center = self._scene.center() + QPointF(self.session.board_pan.x() * self._scene.width(),
                                                    self.session.board_pan.y() * self._scene.height())
            self._scene.setSize(self._scene.size() * self.session.board_zoom)
            self._scene.moveCenter(center)
            self._crop = QRectF(0, 0, 1, 1)
            painter.fillRect(self.current_box, QColor("#fbfaf5"))
        elif surface == Surface.BLACK:
            painter.fillRect(self.current_box, QColor("black"))
            if self.presenter:
                self._text(painter, self.current_box, "BLACKOUT", 13, "#646b76", Qt.AlignmentFlag.AlignCenter)
        elif surface == Surface.MEDIA:
            if self.media_rect is not None:
                self._paint_pdf(painter, self.session.page, self.current_box, navigation=True)
                source = QRectF(*self.media_rect)
                target = QRectF(self._from_page(source.topLeft()), self._from_page(source.bottomRight()))
            else:
                target = self.current_box
            painter.fillRect(target, QColor("black"))
            if self.media_image is not None:
                rect = fit_rect(target, self.media_image.width(), self.media_image.height())
                painter.drawImage(rect, self.media_image)
            else:
                self._text(painter, target, "Loading media…", 13, "#a0a5af", Qt.AlignmentFlag.AlignCenter)
        elif surface == Surface.WEB:
            self._text(painter, self.current_box, "Web content on audience screen", 15,
                       "#9299a5", Qt.AlignmentFlag.AlignCenter)
        else:
            self._paint_pdf(painter, self.session.page, self.current_box, navigation=True)
        if surface in (Surface.BOARD, Surface.SLIDES):
            self._paint_ink(painter)
            if self.session.pointer_visible:
                point = self._from_page(self.session.pointer)
                radius = self.session.pointer_size * self._scene.width()
                if self.session.pointer_mode == 1:
                    gradient = QRadialGradient(point, max(1, radius / 2))
                    gradient.setColorAt(0, QColor("#ff4040"))
                    gradient.setColorAt(1, QColor(255, 0, 0, 0))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(gradient)
                    painter.drawEllipse(point, radius / 2, radius / 2)
                elif self.session.pointer_mode == 2:
                    mask = QPainterPath()
                    mask.addRect(self.current_box)
                    mask.addEllipse(point, radius, radius)
                    mask.setFillRule(Qt.FillRule.OddEvenFill)
                    painter.fillPath(mask, QColor(0, 0, 0, 155))
                else:
                    painter.setPen(QPen(QColor("#ffcf59"), 1.5))
                    painter.drawLine(point - QPointF(6, 0), point + QPointF(6, 0))
                    painter.drawLine(point - QPointF(0, 6), point + QPointF(0, 6))
        if self.camera_image is not None:
            box = self.current_box.adjusted(16, 16, -16, -16)
            if not self.camera_large:
                size = fit_rect(QRectF(0, 0, box.width() * self.camera_width, box.height()),
                                self.camera_image.width(), self.camera_image.height()).size()
                width, height = size.width(), size.height()
                x = box.left() if "left" in self.camera_position else box.right() - width
                y = box.top() if "top" in self.camera_position else box.bottom() - height
                box = QRectF(x, y, width, height)
            painter.setOpacity(self.camera_opacity)
            painter.drawImage(fit_rect(box, self.camera_image.width(), self.camera_image.height()), self.camera_image)
        painter.restore()

    def _paint_ink(self, painter):
        for stroke in self.session.ink.visible(self.session.ink_pages):
            if not stroke.points:
                continue
            path = QPainterPath(self._from_page(QPointF(*stroke.points[0])))
            for point in stroke.points[1:]:
                path.lineTo(self._from_page(QPointF(*point)))
            color = QColor(stroke.color)
            color.setAlphaF(stroke.opacity)
            pen = QPen(color, max(1, stroke.width * self._scene.width()))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            if self.presenter and any(stroke is s for s in self.session.ink.selected):
                painter.setPen(QPen(QColor("#65b7ff"), 1, Qt.PenStyle.DashLine))
                painter.drawRect(path.boundingRect().adjusted(-3, -3, 3, 3))
        if self.presenter and not self.session.selection.isEmpty():
            r = self.session.selection
            painter.setPen(QPen(QColor("#65b7ff"), 1, Qt.PenStyle.DashLine))
            painter.drawRect(QRectF(self._from_page(r.topLeft()), self._from_page(r.bottomRight())))

    def _to_page(self, point):
        if self._scene.isEmpty():
            return QPointF()
        return QPointF(self._crop.x() + (point.x() - self._scene.x()) / self._scene.width() * self._crop.width(),
                       self._crop.y() + (point.y() - self._scene.y()) / self._scene.height() * self._crop.height())

    def _from_page(self, point):
        return QPointF(self._scene.x() + (point.x() - self._crop.x()) / self._crop.width() * self._scene.width(),
                       self._scene.y() + (point.y() - self._crop.y()) / self._crop.height() * self._scene.height())

    def _base_scene(self):
        if self.session.surface == Surface.BOARD:
            return QRectF(self.current_box)
        info = self.session.snapshot.pages[self.session.page]
        return fit_rect(self.current_box, info.size[0] / (2 if info.notes_crop else 1), info.size[1])

    def zoom_at(self, factor, point):
        """Keep the content under the requested widget position stationary."""
        if self.session.surface not in (Surface.SLIDES, Surface.BOARD):
            return
        base = self._base_scene()
        if base.isEmpty():
            return
        zoom_field, pan_field = ("board_zoom", "board_pan") if self.session.surface == Surface.BOARD else ("zoom", "pan")
        old_zoom = getattr(self.session, zoom_field)
        zoom = min(12, max(.25, old_zoom * factor))
        ratio = zoom / old_zoom
        pan = getattr(self.session, pan_field)
        anchor = QPointF((point.x() - base.center().x()) / base.width(),
                         (point.y() - base.center().y()) / base.height())
        setattr(self.session, zoom_field, zoom)
        setattr(self.session, pan_field, pan * ratio + anchor * (1 - ratio))
        self.session.changed.emit()

    def keyPressEvent(self, event):
        self.command.emit(event)

    def _action_at(self, pos):
        if self.session.surface != Surface.SLIDES or not self.current_box.contains(pos):
            return None
        point = self._to_page(pos)
        return next((action for action in self.session.snapshot.pages[self.session.page].actions
                     if QRectF(*action.rect).contains(point)), None)

    def mousePressEvent(self, event):
        self.setFocus()
        if not self.session.snapshot:
            return
        pos = event.position()
        if event.button() == Qt.MouseButton.RightButton:
            self.session.navigate(-1)
            return
        if self.presenter and self.rail.contains(pos):
            for page, rect in self.thumb_rects.items():
                if rect.contains(pos):
                    self.session.go(page)
                    return
        if not self.current_box.contains(pos):
            return
        self._press = self._previous = pos
        modifiers = event.modifiers()
        if modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            self._drag = "pan"
        elif modifiers & Qt.KeyboardModifier.AltModifier:
            self._drag = "select"
        elif modifiers & Qt.KeyboardModifier.ShiftModifier and self.session.ink.selected:
            self._drag = "move"
        elif modifiers & Qt.KeyboardModifier.ShiftModifier or self.session.surface == Surface.BOARD:
            self._start_stroke(pos)
        else:
            self._drag = "click"

    def _start_stroke(self, pos):
        point = self._to_page(pos)
        self._drag = "draw"
        self._stroke = Stroke([(point.x(), point.y())], self.session.color,
                              self.session.stroke_width, self.session.ink_opacity)
        self.session.ink.add(self.session.ink_page, self._stroke)

    def mouseMoveEvent(self, event):
        if not self.session.snapshot:
            return
        pos = event.position()
        if self.presenter and self.rail.contains(pos) and self._drag is None:
            preview = next((page for page, rect in self.thumb_rects.items() if rect.contains(pos)), None)
            if preview != self.session.preview:
                self.session.preview = preview
                self.session.changed.emit()
        elif self.session.preview is not None:
            self.session.preview = None
            self.session.changed.emit()
        if self.current_box.contains(pos):
            point = self._to_page(pos)
            self.session.show_pointer(point)
        action = self._action_at(pos)
        self.setCursor(Qt.CursorShape.PointingHandCursor if action else Qt.CursorShape.ArrowCursor)
        if action and action.title:
            QToolTip.showText(event.globalPosition().toPoint(), action.title, self)
        else:
            QToolTip.hideText()
        if self._drag == "click" and (pos - self._press).manhattanLength() > 5:
            self._start_stroke(self._press)
        if self._drag == "draw":
            point = self._to_page(pos)
            self._stroke.points.append((point.x(), point.y()))
        elif self._drag == "pan":
            delta = pos - self._previous
            field = "board_pan" if self.session.surface == Surface.BOARD else "pan"
            base = self._base_scene()
            setattr(self.session, field, getattr(self.session, field) +
                    QPointF(delta.x() / max(1, base.width()),
                            delta.y() / max(1, base.height())))
        elif self._drag == "select":
            self.session.selection = QRectF(self._to_page(self._press), self._to_page(pos)).normalized()
        elif self._drag == "move":
            delta = self._to_page(pos) - self._to_page(self._previous)
            self.session.ink.transform_selected(delta.x(), delta.y())
        self._previous = pos
        if self._drag:
            self.session.changed.emit()

    def mouseReleaseEvent(self, event):
        if self._drag == "click":
            if self.session.surface == Surface.MEDIA:
                self.command.emit("media-toggle")
                self._drag = None
                return
            action = self._action_at(event.position())
            if action:
                self.session.action_requested.emit(action)
            else:
                self.session.navigate(1)
        elif self._drag == "select":
            rectangle = self.session.selection
            self.session.ink.selected = [stroke for stroke in self.session.ink.visible(self.session.ink_pages)
                                         if all(rectangle.contains(QPointF(*point)) for point in stroke.points)]
            self.session.selection = QRectF()
        self._drag = None
        self._stroke = None
        self.session.changed.emit()

    def mouseDoubleClickEvent(self, event):
        if self.session.surface == Surface.MEDIA:
            self.command.emit("media-expand")
        elif not self.presenter:
            self.command.emit("fullscreen")

    def wheelEvent(self, event):
        if not self.session.snapshot:
            return
        delta = event.angleDelta().y() or event.pixelDelta().y()
        if self.presenter and self.rail.contains(event.position()):
            self.thumb_scroll -= delta / 2
            self.update()
        elif self.presenter and self.notes_box.contains(event.position()):
            self.session.notes_scroll -= delta / 3
            self.update()
        elif self.presenter and self.help_box.contains(event.position()):
            self.help_scroll -= delta / 3
            self.update()
        elif event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            self.zoom_at(math.exp(delta / 1200), event.position())
        elif self.session.ink.selected:
            point = self._to_page(event.position())
            self.session.ink.transform_selected(scale=math.exp(delta / 1200), center=(point.x(), point.y()))
            self.session.changed.emit()
        else:
            self.session.navigate(-1 if delta > 0 else 1)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(url.toLocalFile().lower().endswith(".pdf") for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf"):
                self.files_dropped.emit(path)
                event.acceptProposedAction()
                return

    def tabletEvent(self, event):
        from PySide6.QtCore import QEvent
        if not self.session.snapshot or self.session.surface not in (Surface.SLIDES, Surface.BOARD):
            event.ignore()
            return
        if event.type() == QEvent.Type.TabletPress:
            self._start_stroke(event.position())
        elif event.type() == QEvent.Type.TabletMove and self._stroke:
            point = self._to_page(event.position())
            self._stroke.points.append((point.x(), point.y()))
        elif event.type() == QEvent.Type.TabletRelease:
            self._drag = None
            self._stroke = None
        self.session.show_pointer(self._to_page(event.position()))
        event.accept()
