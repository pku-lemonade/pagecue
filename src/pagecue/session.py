"""Shared presenter/audience state and transactional document replacement."""

from pathlib import Path
from PySide6.QtCore import QObject, QPointF, QRectF, QSettings, QTimer, Signal

from .document import load_snapshot
from .model import Ink, Navigation, Surface, TalkClock
from .render import PdfImages


class Session(QObject):
    changed = Signal()
    document_changed = Signal()
    message = Signal(str)
    action_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.snapshot = None
        self.images = PdfImages(self)
        self.images.image_ready.connect(self.changed)
        self.navigation = None
        self.clock = TalkClock()
        self.ink = Ink()
        self.surface = Surface.SLIDES
        self.notes_scale = 1.0
        self.notes_scroll = 0.0
        self.preview = None
        self.show_help = True
        self.pointer = QPointF(0.5, 0.5)
        self.pointer_mode = 0
        self.pointer_size = 0.035
        self.pointer_visible = False
        self.color = "#ffe066"
        self.stroke_width = 0.003
        self.ink_opacity = 1.0
        self.zoom = 1.0
        self.pan = QPointF()
        self.board_zoom = 1.0
        self.board_pan = QPointF()
        self.selection = QRectF()
        self.digits = ""
        self.auto_advance = True
        self.notes_layout = "auto"
        self.settings = QSettings("PageCue", "PageCue")
        self.tick = QTimer(self)
        self.tick.setInterval(250)
        self.tick.timeout.connect(self.changed)
        self.tick.start()
        self.turn_timer = QTimer(self)
        self.turn_timer.setSingleShot(True)
        self.turn_timer.timeout.connect(lambda: self.navigate(1))
        self.pointer_timer = QTimer(self)
        self.pointer_timer.setSingleShot(True)
        self.pointer_timer.timeout.connect(self._hide_pointer)

    @property
    def page(self):
        return self.navigation.page if self.navigation else 0

    @property
    def ink_page(self):
        return -1 if self.surface == Surface.BOARD else self.page

    @property
    def ink_pages(self):
        return [-1] if self.surface == Surface.BOARD else self.navigation.overlay_pages(self.page)

    def open(self, path, *, password="", page=None, reload=False):
        candidate = load_snapshot(Path(path), password, self.notes_layout)
        # This may fail, leaving the live document/state unchanged.
        self.images.open(candidate)
        old = self.snapshot
        previous = self.page
        if old is not None:
            self.settings.setValue("recent/" + str(old.path), previous)
        self.snapshot = candidate
        if page is None:
            page = previous if reload else int(self.settings.value("recent/" + str(candidate.path), 0))
        self.navigation = Navigation(len(candidate.pages), [p.label for p in candidate.pages], candidate.sections, page)
        if not reload:
            self.ink = Ink()
            self.zoom = 1
            self.pan = QPointF()
        self.surface = Surface.SLIDES
        self.preview = None
        self.notes_scroll = 0
        self._schedule()
        self.document_changed.emit()
        self.changed.emit()
        if candidate.notes.diagnostics:
            self.message.emit("; ".join(candidate.notes.diagnostics[:3]))

    def reload(self):
        if self.snapshot:
            self.open(self.snapshot.path, password=self.snapshot.password, reload=True)

    def _schedule(self):
        self.turn_timer.stop()
        if self.snapshot and self.auto_advance:
            duration = self.snapshot.pages[self.page].duration
            if duration and self.page + 1 < len(self.snapshot.pages):
                self.turn_timer.start(max(1, round(duration * 1000)))

    def go(self, page):
        if self.navigation and self.navigation.go(page):
            self._after_navigation()

    def navigate(self, direction, unit="page"):
        if self.navigation and self.navigation.adjacent(direction, unit):
            self._after_navigation()

    def history(self, backwards):
        if self.navigation and self.navigation.history(backwards):
            self._after_navigation()

    def _after_navigation(self):
        self.surface = Surface.SLIDES
        self.preview = None
        self.notes_scroll = 0
        self.ink.selected.clear()
        self._schedule()
        self.changed.emit()

    def toggle_surface(self, surface):
        self.surface = Surface.SLIDES if self.surface == surface else surface
        self.changed.emit()

    def show_pointer(self, point):
        self.pointer = point
        self.pointer_visible = True
        self.pointer_timer.start(5000)
        self.changed.emit()

    def _hide_pointer(self):
        self.pointer_visible = False
        self.changed.emit()

    def save(self):
        if self.snapshot:
            self.settings.setValue("recent/" + str(self.snapshot.path), self.page)
        self.settings.sync()
