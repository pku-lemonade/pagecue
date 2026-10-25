"""Shared presenter/audience state and transactional document replacement."""

from pathlib import Path
from PySide6.QtCore import QObject, QPointF, QRectF, QSettings, QTimer, Signal

from . import STORAGE_NAME
from .document import load_snapshot
from .model import Ink, Navigation, Surface, TalkClock
from .render import PdfImages
from .animation import AnimationState


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
        self.animation_images = PdfImages(self, budget=64 * 1024 * 1024)
        self.animation_images.image_ready.connect(self.changed)
        self.animations = {}
        self.animation_timers = {}
        self.selected_animation = None
        self.navigation = None
        self.clock = TalkClock()
        self.ink = Ink()
        self.surface = Surface.SLIDES
        self.notes_scale = 1.0
        self.notes_scroll = 0.0
        self.preview = None
        self.show_help = False
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
        # The organization/application-only constructor always uses NativeFormat,
        # even after setDefaultFormat(). Honor explicit QA/portable overrides.
        self.settings = QSettings(QSettings.defaultFormat(), QSettings.Scope.UserScope, STORAGE_NAME, STORAGE_NAME)
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

    def open(self, path, *, password="", page=None, reload=False, destination=None):
        candidate = load_snapshot(Path(path), password, self.notes_layout)
        old, previous = self.snapshot, self.page
        if isinstance(destination, str):
            if destination not in candidate.destinations:
                raise ValueError(f"The linked destination {destination!r} does not exist in this PDF")
            page = candidate.destinations[destination]
        elif isinstance(destination, int):
            page = destination
        if page is None:
            try:
                page = previous if reload or (old and old.path == candidate.path) else int(
                    self.settings.value("recent/" + str(candidate.path), 0))
            except (TypeError, ValueError):
                page = 0
        navigation = Navigation(len(candidate.pages), [p.label for p in candidate.pages], candidate.sections, page)
        animation_images = PdfImages(self, budget=64 * 1024 * 1024)
        try:
            if candidate.animation_pdf:
                animation_images.open_data(candidate.animation_pdf)
            self.images.open(candidate)
        except Exception:
            animation_images.close()
            animation_images.deleteLater()
            raise
        # Both renderers are ready; commit the new document and navigation state.
        self.animation_images.close()
        self.animation_images.deleteLater()
        self.animation_images = animation_images
        animation_images.image_ready.connect(self.changed)
        for timer in self.animation_timers.values():
            timer.stop()
            timer.deleteLater()
        self.animation_timers.clear()
        self.animations = {spec.identifier: AnimationState(spec) for spec in candidate.animations}
        self.selected_animation = None
        for identifier in self.animations:
            timer = QTimer(self)
            timer.timeout.connect(lambda identifier=identifier: self._animation_tick(identifier))
            self.animation_timers[identifier] = timer
        if old is not None:
            self.settings.setValue("recent/" + str(old.path), previous)
        self.snapshot = candidate
        self.navigation = navigation
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

    def set_auto_advance(self, enabled):
        enabled = bool(enabled)
        if enabled == self.auto_advance:
            return
        self.auto_advance = enabled
        self._schedule()
        self.changed.emit()

    def _schedule(self):
        self.turn_timer.stop()
        for identifier, state in self.animations.items():
            self.animation_timers[identifier].stop()
            state.direction = 0
            if state.spec.page == self.page and state.spec.autoplay and self.auto_advance:
                state.frame = 0
                state.play()
                self._animation_schedule(identifier)
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

    def _animation_schedule(self, identifier):
        state = self.animations[identifier]
        timer = self.animation_timers[identifier]
        timer.stop()
        if state.direction and state.spec.page == self.page:
            timer.start(max(4, round(1000 / (state.spec.fps * state.speed))))

    def _animation_tick(self, identifier):
        state = self.animations[identifier]
        state.advance()
        if not state.direction:
            self.animation_timers[identifier].stop()
        self.changed.emit()

    def animation_command(self, command, identifier=None):
        candidates = [key for key, state in self.animations.items() if state.spec.page == self.page]
        if not candidates:
            return False
        identifier = identifier if identifier in candidates else (
            self.selected_animation if self.selected_animation in candidates else candidates[0])
        self.selected_animation = identifier
        self.animations[identifier].command(command)
        self._animation_schedule(identifier)
        self.changed.emit()
        return True

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

    def close(self):
        self.tick.stop()
        self.turn_timer.stop()
        self.pointer_timer.stop()
        for timer in self.animation_timers.values():
            timer.stop()
        self.images.close()
        self.animation_images.close()
