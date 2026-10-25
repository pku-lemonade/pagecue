"""Desktop entry point and user commands for Presenteriyaki."""

import logging
from pathlib import Path
import sys
from urllib.parse import quote, urlsplit, urlunsplit

from PySide6.QtCore import QEvent, QObject, QPointF, QRect, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QKeySequence
from PySide6.QtWidgets import (QApplication, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
                              QFileDialog, QFormLayout, QInputDialog, QLineEdit, QMainWindow,
                              QMessageBox, QSlider, QSpinBox, QStackedWidget, QStatusBar, QSystemTrayIcon)

from . import __version__
from .canvas import Canvas
from .document import PasswordRequired
from .media import Camera, MediaPlayer, Posters
from .model import Surface
from .session import Session
from .services import ReleaseChecker, VideoRouter, video_url


class Application(QApplication):
    file_opened = Signal(str)

    def __init__(self, arguments):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        from .browser import initialize
        initialize()
        super().__init__(arguments)
        self.setWindowIcon(QIcon(str(Path(__file__).parent / "assets/presenteriyaki.svg")))

    def event(self, event):
        if event.type() == QEvent.Type.FileOpen:
            path = event.file()
            candidate = Path(path)
            is_pdf = bool(path) and candidate.suffix.lower() == ".pdf"
            if path and not is_pdf:
                # Cocoa can forward launcher arguments as file-open events.
                # Preserve extensionless PDFs, but ignore unrelated scripts/options.
                try:
                    with candidate.open("rb") as source:
                        is_pdf = b"%PDF-" in source.read(1024)
                except OSError:
                    pass
            if is_pdf:
                self.file_opened.emit(path)
                return True
            logging.getLogger(__name__).info("Ignored non-PDF file-open event: %r", path)
        return super().event(event)


class Window(QMainWindow):
    close_requested = Signal()
    restored = Signal()

    def __init__(self):
        super().__init__()
        self._presentation_flags = None

    @property
    def presentation_fullscreen(self):
        return self._presentation_flags is not None or self.isFullScreen()

    def enter_presentation_fullscreen(self):
        if QApplication.platformName() != "cocoa":
            self.showFullScreen()
            return
        # Native macOS fullscreen uses asynchronous, app-wide Spaces transitions.
        # Presentation windows need independent, immediate placement on displays.
        screen = self.screen()
        if self._presentation_flags is None:
            self._presentation_flags = self.windowFlags()
        self.setWindowFlags(self._presentation_flags | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setGeometry(screen.geometry())
        self.show()
        self.raise_()

    def leave_presentation_fullscreen(self):
        if self._presentation_flags is not None:
            flags, self._presentation_flags = self._presentation_flags, None
            self.setWindowFlags(flags)
        self.showNormal()

    def closeEvent(self, event):
        self.close_requested.emit()
        event.accept()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            if event.oldState() & Qt.WindowState.WindowMinimized and not self.isMinimized():
                self.restored.emit()


class Presenter(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.session = Session()
        self.presenter = Window()
        self.presenter.setWindowTitle("Presenteriyaki")
        self.audience = Window()
        self.audience.setWindowTitle("Presenteriyaki · audience")
        self.view = Canvas(self.session, True)
        self.slide = Canvas(self.session, False)
        self.presenter.setCentralWidget(self.view)
        self.audience_stack = QStackedWidget()
        self.audience_stack.addWidget(self.slide)
        self.audience.setCentralWidget(self.audience_stack)
        self.presenter.resize(1180, 780)
        self.audience.resize(960, 540)
        self.presenter.setMinimumSize(700, 420)
        self.audience.setMinimumSize(200, 120)
        self.status = QStatusBar()
        self.status.setSizeGripEnabled(False)
        self.status.setStyleSheet("QStatusBar {background:#101113; color:#adb3bf; border:0}")
        self.presenter.setStatusBar(self.status)
        self.status.hide()
        self.status_timer = QTimer()
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self.status.hide)
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 1000)
        self.seek.setToolTip("Media position")
        self.status.addPermanentWidget(self.seek)
        self.seek.hide()
        self.media = MediaPlayer()
        self.camera = Camera(self)
        self.posters = Posters()
        self.view.posters = self.slide.posters = self.posters.images
        self.posters.changed.connect(self.session.changed)
        self.media_source_rect = None
        self.media_source_page = None
        self.media.frame.connect(self._media_frame)
        self.camera.frame.connect(self._camera_frame)
        self.camera.changed.connect(self._camera_state_changed)
        self.media.error.connect(self.notify)
        self.camera.error.connect(self.notify)
        self.media.changed.connect(self._media_state)
        self.seek.sliderMoved.connect(lambda value: self.media.seek(round(value / 1000 * self.media.duration)))
        self.web = None
        self.session.message.connect(self.notify)
        self.session.action_requested.connect(self.activate)
        self.session.document_changed.connect(self._opened)
        self.session.changed.connect(self._surface_changed)
        self.view.command.connect(self.command)
        self.slide.command.connect(self.command)
        self.view.files_dropped.connect(self.open)
        self.slide.files_dropped.connect(self.open)
        self.presenter.close_requested.connect(self.quit)
        self.audience.close_requested.connect(self.audience.hide)
        self.presenter.restored.connect(self.restore_all)
        self.audience.restored.connect(self.restore_all)
        self.app.file_opened.connect(self.open)
        self.app.screenRemoved.connect(self._screen_removed)
        self.fullscreen = False
        self.audience_only_fullscreen = False
        self._mac_presentation = None
        if self.app.platformName() == "cocoa":
            from .macos import PresentationOptions
            self._mac_presentation = PresentationOptions()
        self.audience_screen = self.session.settings.value("audience-screen", None)
        self._windowed = None
        self._hidden = False
        self._hidden_fullscreen = False
        self._hidden_audience_only = False
        self._closed = False
        self.video_mode = str(self.session.settings.value("video-routing", ""))
        self.video_router = VideoRouter(self)
        self.video_router.resolved.connect(self._open_web_url)
        self.video_router.message.connect(self.notify)
        self._video_context = (id(self.session.snapshot), self.session.page, self.session.surface)
        self.updates = ReleaseChecker(self)
        self.updates.checked.connect(self._update_result)
        self.updates.failed.connect(lambda message, manual: self.notify(message) if manual and not self._closed else None)
        self.update_tray = None
        self._notified_release_url = None
        self._menus()
        self._load_camera_appearance()

    def _menus(self):
        file_menu = self.presenter.menuBar().addMenu("File")
        def action(menu, label, callback=None, shortcut=None):
            item = QAction(label, self.presenter)
            if callback is not None:
                item.triggered.connect(callback)
            if shortcut:
                item.setShortcut(shortcut)
            menu.addAction(item)
            return item
        action(file_menu, "Open PDF…", self.pick, QKeySequence.StandardKey.Open)
        self.recent_menu = file_menu.addMenu("Open Recent")
        self.recent_menu.aboutToShow.connect(self._recent_files)
        action(file_menu, "Reload", self.reload)
        action(file_menu, "Quit", self.quit, QKeySequence.StandardKey.Quit)
        view_menu = self.presenter.menuBar().addMenu("View")
        action(view_menu, "Fullscreen", self.toggle_fullscreen)
        action(view_menu, "Audience fullscreen", lambda: self.toggle_fullscreen(audience_only=True))
        action(view_menu, "Audience display…", self.choose_screen)
        action(view_menu, "Swap screens", self.swap)
        action(view_menu, "Notes layout…", self.choose_notes_layout)
        action(view_menu, "Reset notes / web zoom", self.reset_text_zoom)
        action(view_menu, "Show audience window", self.audience.show)
        self.automatic_action = action(view_menu, "Automatic playback",
            self.session.set_auto_advance)
        self.automatic_action.setCheckable(True)
        self.automatic_action.setChecked(self.session.auto_advance)
        self.automatic_action.setToolTip("Honor PDF page durations and start autoplay animations")
        action(view_menu, "Hide both windows", self.hide_all)
        timer_menu = self.presenter.menuBar().addMenu("Timer")
        self.timer_action = action(timer_menu, "Start timer", self.toggle_timer)
        action(timer_menu, "Reset timer", self.reset_timer)
        action(timer_menu, "Set duration…", self.set_duration)
        action(timer_menu, "Show clock / timer", self.toggle_clock)
        media_menu = self.presenter.menuBar().addMenu("Media")
        action(media_menu, "Open video or audio…", self.pick_media)
        action(media_menu, "Expand/restore media", self.expand_media)
        action(media_menu, "Choose camera…", lambda: self.toggle_camera(choose=True))
        action(media_menu, "Toggle camera", self.toggle_camera)
        action(media_menu, "Camera appearance…", self.configure_camera_appearance)
        action(media_menu, "Video link routing…", self.configure_video_routing)
        help_menu = self.presenter.menuBar().addMenu("Help")
        action(help_menu, "Keyboard help", self.toggle_help)
        notice_root = (Path(sys._MEIPASS) / "licenses/dependencies" if getattr(sys, "frozen", False)
                       else Path(__file__).resolve().parents[2] / "build/notices")
        notice_index = notice_root / "index.html"
        notice_action = action(help_menu, "Third-party notices", lambda:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(notice_index))))
        notice_action.setEnabled(notice_index.is_file())
        action(help_menu, "Check for updates…", lambda: self.updates.check(manual=True))
        self.auto_update_action = action(help_menu, "Notify about new versions")
        self.auto_update_action.setCheckable(True)
        self.auto_update_action.setChecked(self.session.settings.value("check-updates", False, type=bool))
        self.auto_update_action.toggled.connect(lambda checked: self.session.settings.setValue("check-updates", checked))
        action(help_menu, "About Presenteriyaki", lambda: QMessageBox.about(self.presenter, "Presenteriyaki",
            f"Presenteriyaki {__version__}\nA minimalist two-screen PDF presenter.\nMIT License"))

    def show(self):
        for name, window in (("presenter", self.presenter), ("audience", self.audience)):
            geometry = self.session.settings.value(f"geometry/{name}")
            if geometry is not None:
                window.restoreGeometry(geometry)
        self.presenter.show()
        self.audience.show()
        screens = self.app.screens()
        if len(screens) > 1:
            screen = next((s for s in screens if s.name() == self.audience_screen), screens[-1])
            self.audience_screen = screen.name()
            self._place(self.audience, screen)
        for window in (self.presenter, self.audience):
            if not any(screen.availableGeometry().intersects(window.frameGeometry()) for screen in screens):
                self._place(window, self.app.primaryScreen())
        self.presenter.raise_()
        self.view.setFocus()
        if self.auto_update_action.isChecked():
            QTimer.singleShot(2000, lambda: self.updates.check(manual=False) if not self._closed else None)

    def _update_result(self, release, manual):
        if self._closed:
            return
        if not release.newer:
            if manual:
                self.notify(f"Presenteriyaki {__version__} is up to date")
            return
        kind = " source update" if release.channel == "source" else ""
        message = f"Presenteriyaki {release.version}{kind} is available (installed: {__version__})"
        if manual:
            answer = QMessageBox.question(self.presenter, "Update available", message + "\nOpen this version on GitHub?",
                                          QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Open:
                QDesktopServices.openUrl(QUrl(release.url))
        else:
            self.notify(message)
            self.desktop_notification("Presenteriyaki update", message, release.url)

    def desktop_notification(self, title, message, url):
        """Request native delivery; Qt does not report whether the OS displayed it."""
        if self._closed or not QSystemTrayIcon.isSystemTrayAvailable() or not QSystemTrayIcon.supportsMessages():
            return False
        if self.update_tray is None:
            self.update_tray = QSystemTrayIcon(self.app.windowIcon(), self)
            self.update_tray.messageClicked.connect(self._open_notified_release)
            self.update_tray.show()
        self._notified_release_url = url
        self.update_tray.showMessage(title, message)
        return True

    def _open_notified_release(self):
        if not self._closed and self._notified_release_url:
            QDesktopServices.openUrl(QUrl(self._notified_release_url))

    def configure_video_routing(self):
        options = ["Direct YouTube links", "Find an Invidious instance automatically", "Use my Invidious instance"]
        current = 1 if self.video_mode == "auto" else 2 if self.video_mode else 0
        choice, okay = QInputDialog.getItem(self.presenter, "Video link routing", "YouTube links:", options, current, False)
        if not okay:
            return
        mode = "auto" if choice == options[1] else ""
        if choice == options[2]:
            mode, okay = QInputDialog.getText(self.presenter, "Invidious instance", "HTTPS base URL:",
                                            text=self.video_mode if self.video_mode != "auto" else "")
            if not okay:
                return
            try:
                video_url("https://www.youtube.com/watch?v=test", mode)
            except ValueError as error:
                self.notify(str(error))
                return
        self.video_mode = mode
        self.session.settings.setValue("video-routing", mode)

    def pick(self):
        path, _ = QFileDialog.getOpenFileName(self.presenter, "Open presentation", "", "PDF documents (*.pdf)")
        if path:
            self.open(path)

    def open(self, path, page=None, destination=None):
        if self._closed:
            return False
        password = ""
        while True:
            try:
                self.session.open(path, password=password, page=page, destination=destination)
                return True
            except PasswordRequired:
                password, okay = QInputDialog.getText(self.presenter, "Encrypted PDF", "Password:",
                                                      QLineEdit.EchoMode.Password)
                if not okay:
                    return False
            except Exception as error:
                QMessageBox.warning(self.presenter, "Could not open PDF", str(error))
                return False

    def _opened(self):
        path = self.session.snapshot.path
        name = path.name
        recent = self.session.settings.value("recent-files", [], type=list)
        self.session.settings.setValue("recent-files", ([str(path)] + [p for p in recent if p != str(path)])[:10])
        self.presenter.setWindowTitle(f"{name} · Presenteriyaki")
        self.audience.setWindowTitle(f"{name} · audience")
        self.media.stop()
        self.view.media_image = self.slide.media_image = None
        self.view.media_rect = self.slide.media_rect = None
        self.media_source_rect = self.media_source_page = None
        self.posters.reset(action.value for page in self.session.snapshot.pages
                           for action in page.actions if action.kind == "media")
        self.view.setFocus()

    def _recent_files(self):
        self.recent_menu.clear()
        paths = [Path(p) for p in self.session.settings.value("recent-files", [], type=list) if Path(p).is_file()]
        for path in paths:
            label = path.name
            if sum(p.name == path.name for p in paths) > 1:
                label += f" — {path.parent.name}"
            item = self.recent_menu.addAction(label)
            item.setToolTip(str(path))
            item.triggered.connect(lambda checked=False, path=path: self.open(path))
        if not paths:
            self.recent_menu.addAction("No recent PDFs").setEnabled(False)

    def reload(self):
        try:
            self.session.reload()
        except Exception as error:
            self.notify(f"Reload failed; kept the current presentation. {error}")

    def notify(self, message):
        if self._closed:
            return
        self.status.show()
        self.status.showMessage(message)
        self.status_timer.start(10000)

    def toggle_help(self):
        self.session.show_help = not self.session.show_help
        self.session.changed.emit()

    def toggle_clock(self):
        self.session.clock.show_wall = not self.session.clock.show_wall
        self.session.changed.emit()

    def toggle_timer(self):
        self.session.clock.toggle()
        self.session.changed.emit()

    def reset_timer(self):
        self.session.clock.reset()
        self.session.changed.emit()

    def set_duration(self):
        minutes, okay = QInputDialog.getDouble(self.presenter, "Presentation timer",
            "Duration in minutes (0 for elapsed time):", self.session.clock.duration / 60, 0, 1440, 1)
        if okay:
            self.session.clock.duration = minutes * 60
            self.session.clock.show_wall = False
            self.session.changed.emit()

    def hide_all(self):
        self._hidden_fullscreen = self.fullscreen
        self._hidden_audience_only = self.audience_only_fullscreen
        if self.fullscreen:
            self.leave_fullscreen()
        self._hidden = True
        self.presenter.showMinimized()
        self.audience.showMinimized()

    def restore_all(self):
        if not self._hidden:
            return
        self._hidden = False
        self.presenter.showNormal()
        self.audience.showNormal()
        if self._hidden_fullscreen:
            self.toggle_fullscreen(audience_only=self._hidden_audience_only)
        self.view.setFocus()

    def command(self, command):
        if isinstance(command, str):
            if command == "open":
                self.pick()
            elif command == "timer-toggle":
                self.toggle_timer()
            elif command == "fullscreen":
                self.toggle_fullscreen(audience_only=True)
            elif command == "media-toggle":
                self.media.toggle()
            elif command == "media-expand":
                self.expand_media()
            return
        event = command
        key, text, mods = event.key(), event.text(), event.modifiers()
        ctrl = bool(mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)
        state = self.session
        if ctrl and key == Qt.Key.Key_O:
            self.pick()
            return
        if key == Qt.Key.Key_F5 or (text.lower() == "f" and not ctrl):
            self.toggle_fullscreen()
            return
        if key == Qt.Key.Key_Escape:
            if state.digits:
                state.digits = ""
                state.changed.emit()
                return
            self.video_router.cancel()
            if self.fullscreen:
                self.leave_fullscreen()
            return
        if text == "?":
            self.toggle_help()
            return
        if not state.snapshot:
            return
        if ctrl and key in (Qt.Key.Key_W, Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D):
            horizontal = "left" if key == Qt.Key.Key_A else "right" if key == Qt.Key.Key_D else self.slide.camera_position.split("-")[1]
            vertical = "top" if key == Qt.Key.Key_W else "bottom" if key == Qt.Key.Key_S else self.slide.camera_position.split("-")[0]
            self.set_camera_appearance(self.slide.camera_width, self.slide.camera_opacity, f"{vertical}-{horizontal}")
            return
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_PageUp,
                   Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_PageDown):
            direction = -1 if key in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_PageUp) else 1
            if alt:
                state.history(direction < 0)
            else:
                state.navigate(direction, "section" if ctrl and (shift or key in (Qt.Key.Key_Up, Qt.Key.Key_Down))
                               else "frame" if ctrl else "page")
        elif key in (Qt.Key.Key_Home, Qt.Key.Key_End):
            state.go(0 if key == Qt.Key.Key_Home else state.navigation.count - 1)
        elif key == Qt.Key.Key_0 and not ctrl and not state.digits:
            self.reset_text_zoom()
        elif text.isdigit() and not ctrl:
            state.digits = (state.digits + text)[-7:]
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and state.digits:
            state.go(int(state.digits) - 1)
            state.digits = ""
        elif key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            if state.digits:
                state.digits = state.digits[:-1]
            elif state.ink.selected:
                state.ink.erase(state.ink_pages)
            elif state.ink.pages.get(state.ink_page):
                state.ink.pages[state.ink_page].pop()
        elif text.lower() == "q":
            self.quit()
        elif text.lower() == "r":
            self.reload()
        elif text.lower() == "x":
            self.swap()
        elif text.lower() == "h":
            self.hide_all()
        elif key == Qt.Key.Key_T and shift:
            self.toggle_clock()
        elif text.lower() == "t":
            self.toggle_timer()
        elif text == " ":
            if state.surface == Surface.MEDIA:
                self.media.toggle()
            elif state.snapshot.pages[state.page].duration:
                state.set_auto_advance(not state.auto_advance)
            elif state.animation_command("Toggle"):
                pass
            else:
                state.clock.toggle()
        elif text.lower() == "z":
            self.reset_timer()
        elif text in ("[", "]", "{", "}"):
            state.clock.duration = max(0, state.clock.duration + {"[": -60, "]": 60, "{": -600, "}": 600}[text])
            state.clock.show_wall = False
        elif text in ("+", "=", "-", "_"):
            factor = 1.1 if text in ("+", "=") else 1 / 1.1
            if ctrl:
                self.view.zoom_at(factor, self.view._from_page(state.pointer))
            elif state.surface == Surface.WEB and self.web:
                self.web.setZoomFactor(min(5, max(.25, self.web.zoomFactor() * factor)))
            else:
                state.notes_scale = min(4, max(.4, state.notes_scale * factor))
        elif ctrl and key == Qt.Key.Key_0:
            if state.surface == Surface.BOARD:
                state.board_zoom, state.board_pan = 1.0, QPointF()
            else:
                state.zoom, state.pan = 1.0, QPointF()
        elif text == ".":
            state.toggle_surface(Surface.BLACK)
        elif text.lower() == "b":
            state.toggle_surface(Surface.BOARD)
        elif text.lower() == "s":
            state.surface = Surface.SLIDES
        elif text.lower() == "l":
            state.pointer_mode = (state.pointer_mode + 1) % 3
            state.pointer_visible = True
        elif text in ("p", "P"):
            state.pointer_size = min(.5, max(.005, state.pointer_size * (1.5 if shift else 1 / 1.5)))
            state.stroke_width = state.pointer_size / 12
            state.pointer_visible = True
        elif text.lower() == "c":
            color = QColorDialog.getColor(QColor(state.color), self.presenter, "Ink color",
                                         QColorDialog.ColorDialogOption.ShowAlphaChannel)
            if color.isValid():
                state.color = color.name()
                state.ink_opacity = color.alphaF()
        elif text.lower() == "e":
            state.ink.erase(state.ink_pages)
        elif key == Qt.Key.Key_V and shift:
            self.view.camera_large = self.slide.camera_large = not self.slide.camera_large
        elif text.lower() == "v":
            self.toggle_camera()
        elif key == Qt.Key.Key_M and shift:
            self.expand_media()
        elif text.lower() == "m":
            if self.media.resource:
                if self.session.page != self.media_source_page:
                    self.view.media_rect = self.slide.media_rect = None
                state.toggle_surface(Surface.MEDIA)
            else:
                self.pick_media()
        elif text.lower() == "w":
            if self.web:
                state.toggle_surface(Surface.WEB)
            else:
                url, okay = QInputDialog.getText(self.presenter, "Open web content", "URL:")
                if okay and url:
                    self.open_web(url)
        elif text in ("<", ">"):
            if state.surface == Surface.MEDIA:
                self.media.step(1 if text == ">" else -1)
            else:
                state.animation_command("StepRight" if text == ">" else "StepLeft")
        state.changed.emit()

    def activate(self, action):
        if action.kind == "animation":
            identifier, command = str(action.value).split(":", 1)
            self.session.animation_command(command, int(identifier))
        elif action.kind == "page":
            self.session.go(int(action.value))
        elif action.kind == "named":
            name = action.value
            if name in ("/NextPage", "/PrevPage"):
                self.session.navigate(1 if name == "/NextPage" else -1)
            elif name in ("/FirstPage", "/LastPage"):
                self.session.go(0 if name == "/FirstPage" else self.session.navigation.count - 1)
            elif name in ("/GoBack", "/GoForward"):
                self.session.history(name == "/GoBack")
        elif action.kind == "media":
            self.play_media(action.value, action.rect)
        elif action.kind == "url":
            self.open_web(str(action.value))
        elif action.kind == "document":
            link = action.value
            if link.resource.path is not None:
                self.open(link.resource.path, destination=link.destination)
            elif link.resource.url:
                parsed = urlsplit(link.resource.url)
                fragment = (f"page={link.destination + 1}" if isinstance(link.destination, int)
                            else f"nameddest={quote(link.destination, safe='')}" if isinstance(link.destination, str)
                            else parsed.fragment)
                self.open_web(urlunsplit(parsed._replace(fragment=fragment)))

    def pick_media(self):
        from .document import Media
        path, _ = QFileDialog.getOpenFileName(self.presenter, "Open video/audio/GIF")
        if path:
            self.play_media(Media(Path(path).name, path=Path(path)))

    def play_media(self, resource, rect=None):
        previous = self.session.surface
        self.media_source_rect = rect if rect and rect[3] >= .03 else None
        self.media_source_page = self.session.page
        self.view.media_rect = self.slide.media_rect = self.media_source_rect
        self.view.media_image = self.slide.media_image = self.posters.images.get(resource.key)
        self.session.surface = Surface.MEDIA
        try:
            self.media.load(resource)
            self.status_timer.stop()
            self.status.show()
            self.status.showMessage("Click: play/pause · double-click or Shift+M: expand/restore · < >: step")
            self.seek.show()
        except Exception as error:
            self.session.surface = previous
            self.notify(str(error))
        self.session.changed.emit()

    def expand_media(self):
        if self.session.surface != Surface.MEDIA:
            return
        rect = self.media_source_rect if self.slide.media_rect is None else None
        self.view.media_rect = self.slide.media_rect = rect
        self.session.changed.emit()

    def _media_frame(self, image):
        self.view.media_image = self.slide.media_image = image
        self.session.changed.emit()

    def _camera_frame(self, image):
        if self._closed or not self.camera.active:
            return
        self.view.camera_image = self.slide.camera_image = image
        self.session.changed.emit()

    def _camera_state_changed(self):
        if not self.camera.active:
            self.view.camera_image = self.slide.camera_image = None
        if not self._closed:
            self.session.changed.emit()

    def _load_camera_appearance(self):
        settings = self.session.settings
        try:
            width = float(settings.value("camera/width", .20))
            opacity = float(settings.value("camera/opacity", .8))
        except (TypeError, ValueError):
            width, opacity = .20, .8
        position = str(settings.value("camera/position", "bottom-right"))
        self.set_camera_appearance(width, opacity, position, persist=False)

    def set_camera_appearance(self, width, opacity, position, *, persist=True):
        width, opacity = min(.9, max(.1, width)), min(1, max(.05, opacity))
        if position not in ("top-left", "top-right", "bottom-left", "bottom-right"):
            position = "bottom-right"
        for view in (self.view, self.slide):
            view.camera_width, view.camera_opacity, view.camera_position = width, opacity, position
        if persist:
            settings = self.session.settings
            settings.setValue("camera/width", width)
            settings.setValue("camera/opacity", opacity)
            settings.setValue("camera/position", position)
        self.session.changed.emit()

    def configure_camera_appearance(self):
        dialog = QDialog(self.presenter)
        dialog.setWindowTitle("Camera appearance")
        layout = QFormLayout(dialog)
        width, opacity = QSpinBox(), QSpinBox()
        width.setRange(10, 90)
        opacity.setRange(5, 100)
        for spin, value in ((width, self.slide.camera_width), (opacity, self.slide.camera_opacity)):
            spin.setSuffix(" %")
            spin.setValue(round(value * 100))
        position = QComboBox()
        positions = ["top-left", "top-right", "bottom-left", "bottom-right"]
        position.addItems([value.replace("-", " ").capitalize() for value in positions])
        position.setCurrentIndex(positions.index(self.slide.camera_position))
        layout.addRow("Inset size", width)
        layout.addRow("Opacity", opacity)
        layout.addRow("Position", position)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.set_camera_appearance(width.value() / 100, opacity.value() / 100, positions[position.currentIndex()])
        dialog.deleteLater()

    def _media_state(self):
        if not self.seek.isSliderDown() and self.media.duration:
            self.seek.setValue(round(self.media.position / self.media.duration * 1000))

    def toggle_camera(self, checked=False, choose=False):
        if self._closed:
            return
        if self.camera.requested and not choose:
            self.camera.stop()
            return
        devices = self.camera.devices()
        if not devices:
            self.notify("No camera is available")
            return
        device = devices[0]
        if len(devices) > 1 or choose:
            names = [f"{i + 1}: {d.description()}" for i, d in enumerate(devices)]
            name, okay = QInputDialog.getItem(self.presenter, "Camera", "Device:", names, 0, False)
            if not okay:
                return
            device = devices[names.index(name)]
        self.camera.start(device)

    def open_web(self, value):
        url = QUrl.fromUserInput(value)
        if not QUrl(value).scheme() and self.session.snapshot:
            local = self.session.snapshot.path.parent / value
            if local.exists():
                url = QUrl.fromLocalFile(str(local.resolve()))
        if url.scheme() not in ("https", "http", "file"):
            self.notify("Only web URLs and local document links can open here")
            return
        try:
            self.video_router.route(url.toString(), self.video_mode)
        except ValueError as error:
            self.notify(str(error))

    def _open_web_url(self, value):
        if self._closed:
            return
        url = QUrl(value)
        if self.web is None:
            from .browser import Browser
            self.web = Browser(self.slide, self.audience)
            self.audience_stack.addWidget(self.web)
            self.web.shortcut.connect(self._web_shortcut, Qt.ConnectionType.QueuedConnection)
            self.web.loadFinished.connect(lambda okay: None if okay else self.notify("Could not load web content"))
        self.web.load(url)
        self.session.surface = Surface.WEB
        self.session.changed.emit()

    def _web_shortcut(self, key):
        if self._closed or self.session.surface != Surface.WEB:
            return
        if key == Qt.Key.Key_Escape:
            self.session.surface = Surface.SLIDES
            self.session.changed.emit()
            self.slide.setFocus()
        elif key == Qt.Key.Key_F5:
            self.toggle_fullscreen()
            self.audience.activateWindow()

    def _surface_changed(self):
        self.automatic_action.setChecked(self.session.auto_advance)
        clock = self.session.clock
        self.timer_action.setText("Pause timer" if clock.started is not None else
                                  "Resume timer" if clock.elapsed else "Start timer")
        context = (id(self.session.snapshot), self.session.page, self.session.surface)
        if context != self._video_context:
            self.video_router.cancel()
            self._video_context = context
            if self.session.surface != Surface.MEDIA:
                self.media.pause()
                self.seek.hide()
        if self.web:
            visible = self.session.surface == Surface.WEB
            self.audience_stack.setCurrentWidget(self.web if visible else self.slide)
            self.web.update_camera()

    def _place(self, window, screen):
        window.winId()
        window.windowHandle().setScreen(screen)
        available = screen.availableGeometry()
        size = window.size().boundedTo(available.size())
        rect = QRect(available.center().x() - size.width() // 2,
                     available.center().y() - size.height() // 2, size.width(), size.height())
        window.setGeometry(rect)

    def choose_screen(self):
        screens = self.app.screens()
        names = [f"{i + 1}: {s.name()} ({s.size().width()}×{s.size().height()})" for i, s in enumerate(screens)]
        name, okay = QInputDialog.getItem(self.presenter, "Audience display", "Display:", names, 0, False)
        if okay:
            screen = screens[names.index(name)]
            was_fullscreen = self.fullscreen
            audience_only = self.audience_only_fullscreen
            if was_fullscreen:
                self.leave_fullscreen()
            self.audience_screen = screen.name()
            self.session.settings.setValue("audience-screen", self.audience_screen)
            self._place(self.audience, screen)
            if was_fullscreen:
                self.toggle_fullscreen(audience_only=audience_only)

    def leave_fullscreen(self):
        if not self.fullscreen:
            return
        for window in (self.presenter, self.audience):
            window.leave_presentation_fullscreen()
        if self._windowed:
            self.presenter.setGeometry(self._windowed[0])
            self.audience.setGeometry(self._windowed[1])
        self.fullscreen = False
        if self._mac_presentation:
            self._mac_presentation.leave()
        self.view.setFocus()

    def toggle_fullscreen(self, audience_only=False):
        if self.fullscreen:
            same_mode = audience_only == self.audience_only_fullscreen
            self.leave_fullscreen()
            if same_mode:
                return
        self._windowed = (self.presenter.geometry(), self.audience.geometry())
        screens = self.app.screens()
        target = next((s for s in screens if s.name() == self.audience_screen), screens[-1])
        self._place(self.audience, target)
        if self._mac_presentation:
            self._mac_presentation.enter()
        self.audience.enter_presentation_fullscreen()
        if len(screens) > 1 and not audience_only:
            other = next(s for s in screens if s != target)
            self._place(self.presenter, other)
            self.presenter.enter_presentation_fullscreen()
        self.fullscreen = True
        self.audience_only_fullscreen = audience_only
        self.view.setFocus()

    def swap(self):
        screens = self.app.screens()
        if len(screens) < 2:
            self.notify("Connect a second display to swap screens")
            return
        old_audience = self.audience.screen()
        new_audience = self.presenter.screen()
        if old_audience == new_audience:
            new_audience = next(s for s in screens if s != old_audience)
        was_fullscreen = self.fullscreen
        audience_only = self.audience_only_fullscreen
        if was_fullscreen:
            self.leave_fullscreen()
        self._place(self.audience, new_audience)
        self._place(self.presenter, old_audience)
        self.audience_screen = new_audience.name()
        self.session.settings.setValue("audience-screen", self.audience_screen)
        if was_fullscreen:
            self.toggle_fullscreen(audience_only=audience_only)

    def _screen_removed(self, screen):
        if self.fullscreen:
            self.leave_fullscreen()
        for window in (self.presenter, self.audience):
            self._place(window, self.app.primaryScreen())
        self.presenter.raise_()
        self.notify("Display disconnected; returned to windowed mode")

    def choose_notes_layout(self):
        options = ["Automatic", "Normal PDF", "Slides left / notes right"]
        value, okay = QInputDialog.getItem(self.presenter, "Notes layout", "PDF layout:", options, 0, False)
        if okay:
            self.session.notes_layout = {options[0]: "auto", options[1]: "off", options[2]: "right"}[value]
            self.reload()

    def reset_text_zoom(self):
        if self.session.surface == Surface.WEB and self.web:
            self.web.setZoomFactor(1.0)
        else:
            self.session.notes_scale = 1.0
            self.session.notes_scroll = 0.0
        self.session.changed.emit()

    def quit(self):
        if self._closed:
            return
        self._closed = True
        if self.fullscreen:
            self.leave_fullscreen()
        if not self.fullscreen:
            self.session.settings.setValue("geometry/presenter", self.presenter.saveGeometry())
            self.session.settings.setValue("geometry/audience", self.audience.saveGeometry())
        self.session.save()
        self.session.close()
        self.video_router.cancel()
        self.updates.cancel()
        if self.update_tray:
            self.update_tray.hide()
        self.camera.stop()
        self.posters.close()
        self.media.close()
        if self.web:
            self.web.shutdown()
        self.app.quit()


def main():
    from .cli import main as run
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
