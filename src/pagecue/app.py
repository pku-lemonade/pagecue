"""Desktop entry point and user commands for PageCue."""

import argparse
from pathlib import Path
import sys

from PySide6.QtCore import QEvent, QObject, QPointF, QRect, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtWidgets import (QApplication, QColorDialog, QFileDialog, QInputDialog,
                              QLineEdit, QMainWindow, QMessageBox, QSlider, QStatusBar)

from . import __version__
from .canvas import Canvas
from .document import PasswordRequired
from .media import Camera, MediaPlayer, Posters
from .model import Surface
from .session import Session


class Application(QApplication):
    file_opened = Signal(str)

    def __init__(self, arguments):
        # WebEngine is created lazily, but its shared graphics context must be
        # requested before constructing QApplication (not when a link is clicked).
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        super().__init__(arguments)

    def event(self, event):
        if event.type() == QEvent.Type.FileOpen:
            self.file_opened.emit(event.file())
            return True
        return super().event(event)


class Window(QMainWindow):
    close_requested = Signal()
    restored = Signal()

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
        self.presenter.setWindowTitle("PageCue")
        self.audience = Window()
        self.audience.setWindowTitle("PageCue · audience")
        self.view = Canvas(self.session, True)
        self.slide = Canvas(self.session, False)
        self.presenter.setCentralWidget(self.view)
        self.audience.setCentralWidget(self.slide)
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
        self.camera = Camera()
        self.posters = Posters()
        self.view.posters = self.slide.posters = self.posters.images
        self.posters.changed.connect(self.session.changed)
        self.media_source_rect = None
        self.media_source_page = None
        self.media.frame.connect(self._media_frame)
        self.camera.frame.connect(self._camera_frame)
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
        self.slide.installEventFilter(self)
        self.app.file_opened.connect(self.open)
        self.app.screenRemoved.connect(self._screen_removed)
        self.fullscreen = False
        self.audience_screen = self.session.settings.value("audience-screen", None)
        self._windowed = None
        self._hidden = False
        self._hidden_fullscreen = False
        self._closed = False
        self._menus()

    def _menus(self):
        file_menu = self.presenter.menuBar().addMenu("File")
        def action(menu, label, callback, shortcut=None):
            item = QAction(label, self.presenter)
            item.triggered.connect(callback)
            if shortcut:
                item.setShortcut(shortcut)
            menu.addAction(item)
            return item
        action(file_menu, "Open PDF…", self.pick, QKeySequence.StandardKey.Open)
        action(file_menu, "Reload", self.reload)
        action(file_menu, "Quit", self.quit, QKeySequence.StandardKey.Quit)
        view_menu = self.presenter.menuBar().addMenu("View")
        action(view_menu, "Fullscreen", self.toggle_fullscreen)
        action(view_menu, "Audience display…", self.choose_screen)
        action(view_menu, "Swap screens", self.swap)
        action(view_menu, "Notes layout…", self.choose_notes_layout)
        action(view_menu, "Show audience window", self.audience.show)
        action(view_menu, "Show clock / timer", self.toggle_clock)
        action(view_menu, "Hide both windows", self.hide_all)
        media_menu = self.presenter.menuBar().addMenu("Media")
        action(media_menu, "Open video or audio…", self.pick_media)
        action(media_menu, "Expand/restore media", self.expand_media)
        action(media_menu, "Choose camera…", lambda: self.toggle_camera(choose=True))
        action(media_menu, "Toggle camera", self.toggle_camera)
        help_menu = self.presenter.menuBar().addMenu("Help")
        action(help_menu, "Keyboard help", self.toggle_help)
        action(help_menu, "About PageCue", lambda: QMessageBox.about(self.presenter, "PageCue",
            f"PageCue {__version__}\nA minimalist Qt PDF presenter.\nIndependent implementation · MIT\n"
            "In development: see the feature parity ledger."))

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

    def pick(self):
        path, _ = QFileDialog.getOpenFileName(self.presenter, "Open presentation", "", "PDF documents (*.pdf)")
        if path:
            self.open(path)

    def open(self, path, page=None):
        password = ""
        while True:
            try:
                self.session.open(path, password=password, page=page)
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
        name = self.session.snapshot.path.name
        self.presenter.setWindowTitle(f"{name} · PageCue")
        self.audience.setWindowTitle(f"{name} · audience")
        self.media.stop()
        self.view.media_image = self.slide.media_image = None
        self.view.media_rect = self.slide.media_rect = None
        self.media_source_rect = self.media_source_page = None
        self.posters.reset(action.value for page in self.session.snapshot.pages
                           for action in page.actions if action.kind == "media")
        self.view.setFocus()

    def reload(self):
        try:
            self.session.reload()
        except Exception as error:
            self.notify(f"Reload failed; kept the current presentation. {error}")

    def notify(self, message):
        self.status.show()
        self.status.showMessage(message)
        self.status_timer.start(10000)

    def toggle_help(self):
        self.session.show_help = not self.session.show_help
        self.session.changed.emit()

    def toggle_clock(self):
        self.session.clock.show_wall = not self.session.clock.show_wall
        self.session.changed.emit()

    def hide_all(self):
        self._hidden_fullscreen = self.fullscreen
        if self.fullscreen:
            self.toggle_fullscreen()
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
            self.toggle_fullscreen()
        self.view.setFocus()

    def eventFilter(self, watched, event):
        if self._closed:
            return False
        if watched is self.slide and event.type() == QEvent.Type.Resize and self.web:
            self.web.setGeometry(self.slide.geometry())
        if self.web and self.session.surface == Surface.WEB and event.type() == QEvent.Type.KeyPress:
            from PySide6.QtWidgets import QWidget
            in_web = isinstance(watched, QWidget) and (watched is self.web or self.web.isAncestorOf(watched))
            if in_web and event.key() == Qt.Key.Key_Escape:
                self.session.surface = Surface.SLIDES
                self.session.changed.emit()
                self.slide.setFocus()
                return True
            if in_web and event.key() == Qt.Key.Key_F5:
                self.toggle_fullscreen()
                return True
        return super().eventFilter(watched, event)

    def command(self, command):
        if isinstance(command, str):
            if command == "fullscreen":
                self.toggle_fullscreen()
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
            if self.fullscreen:
                self.toggle_fullscreen()
            return
        if text == "?":
            self.toggle_help()
            return
        if not state.snapshot:
            return
        if ctrl and key in (Qt.Key.Key_W, Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D):
            horizontal = "left" if key == Qt.Key.Key_A else "right" if key == Qt.Key.Key_D else self.slide.camera_position.split("-")[1]
            vertical = "top" if key == Qt.Key.Key_W else "bottom" if key == Qt.Key.Key_S else self.slide.camera_position.split("-")[0]
            self.view.camera_position = self.slide.camera_position = f"{vertical}-{horizontal}"
            state.changed.emit()
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
            state.clock.toggle()
        elif text == " ":
            if state.surface == Surface.MEDIA:
                self.media.toggle()
            elif state.animation_command("Toggle"):
                pass
            elif state.snapshot.pages[state.page].duration:
                state.auto_advance = not state.auto_advance
                state._schedule()
            else:
                state.clock.toggle()
        elif text.lower() == "z":
            state.clock.reset()
        elif text in ("[", "]", "{", "}"):
            state.clock.duration = max(0, state.clock.duration + {"[": -60, "]": 60, "{": -600, "}": 600}[text])
            state.clock.show_wall = False
        elif text in ("+", "=", "-", "_"):
            factor = 1.1 if text in ("+", "=") else 1 / 1.1
            if ctrl:
                field = "board_zoom" if state.surface == Surface.BOARD else "zoom"
                setattr(state, field, min(12, max(.25, getattr(state, field) * factor)))
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
        if not self.camera.active:
            return
        self.view.camera_image = self.slide.camera_image = image
        self.session.changed.emit()

    def _media_state(self):
        if not self.seek.isSliderDown() and self.media.duration:
            self.seek.setValue(round(self.media.position / self.media.duration * 1000))

    def toggle_camera(self, checked=False, choose=False):
        if self.camera.active and not choose:
            self.camera.stop()
            self.view.camera_image = self.slide.camera_image = None
            self.session.changed.emit()
            return
        devices = self.camera.devices()
        if not devices:
            self.notify("No camera is available")
            return
        device = devices[0]
        if len(devices) > 1 or choose:
            names = [d.description() for d in devices]
            name, okay = QInputDialog.getItem(self.presenter, "Camera", "Device:", names, 0, False)
            if not okay:
                return
            device = devices[names.index(name)]
        from PySide6.QtCore import QCameraPermission
        permission = QCameraPermission()
        status = self.app.checkPermission(permission)
        if status == Qt.PermissionStatus.Undetermined:
            self.app.requestPermission(permission, lambda p: self.camera.start(device)
                if p.status() == Qt.PermissionStatus.Granted else self.notify("Camera access was not granted"))
        elif status == Qt.PermissionStatus.Granted:
            self.camera.start(device)
        else:
            self.notify("Camera permission is disabled in system settings")

    def open_web(self, value):
        url = QUrl.fromUserInput(value)
        if not QUrl(value).scheme() and self.session.snapshot:
            local = self.session.snapshot.path.parent / value
            if local.exists():
                url = QUrl.fromLocalFile(str(local.resolve()))
        if url.scheme() not in ("https", "http", "file"):
            self.notify("Only web URLs and local document links can open here")
            return
        if self.web is None:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            self.web = QWebEngineView(self.audience)
            self.web.installEventFilter(self)
            self.web.loadFinished.connect(lambda okay: None if okay else self.notify("Could not load web content"))
            self.web.loadFinished.connect(lambda _: self._web_keyboard_filter())
        self.web.setGeometry(self.audience.centralWidget().geometry())
        self.web.load(url)
        self.session.surface = Surface.WEB
        self.session.changed.emit()

    def _web_keyboard_filter(self):
        # Limit Python event filtering to actual widgets. Filtering every Qt
        # application event can re-enter Shiboken while WebEngine constructs
        # private QObject wrappers, causing a native crash on macOS.
        if self.web:
            proxy = self.web.focusProxy()
            if proxy:
                proxy.installEventFilter(self)

    def _surface_changed(self):
        if self.web:
            self.web.setVisible(self.session.surface == Surface.WEB)
            if self.session.surface == Surface.WEB:
                self.web.setGeometry(self.audience.centralWidget().geometry())
                self.web.raise_()
        if self.session.surface != Surface.MEDIA:
            self.media.pause()
            self.seek.hide()

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
            if was_fullscreen:
                self.toggle_fullscreen()
            self.audience_screen = screen.name()
            self.session.settings.setValue("audience-screen", self.audience_screen)
            self._place(self.audience, screen)
            if was_fullscreen:
                self.toggle_fullscreen()

    def toggle_fullscreen(self):
        if self.fullscreen:
            for window in (self.presenter, self.audience):
                window.showNormal()
            if self._windowed:
                self.presenter.setGeometry(self._windowed[0])
                self.audience.setGeometry(self._windowed[1])
            self.fullscreen = False
        else:
            self._windowed = (self.presenter.geometry(), self.audience.geometry())
            screens = self.app.screens()
            target = next((s for s in screens if s.name() == self.audience_screen), screens[-1])
            self._place(self.audience, target)
            self.audience.showFullScreen()
            if len(screens) > 1:
                other = next(s for s in screens if s != target)
                self._place(self.presenter, other)
                self.presenter.showFullScreen()
            self.fullscreen = True
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
        if was_fullscreen:
            self.toggle_fullscreen()
        self._place(self.audience, new_audience)
        self._place(self.presenter, old_audience)
        self.audience_screen = new_audience.name()
        self.session.settings.setValue("audience-screen", self.audience_screen)
        if was_fullscreen:
            self.toggle_fullscreen()

    def _screen_removed(self, screen):
        if self.fullscreen:
            self.toggle_fullscreen()
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

    def quit(self):
        if self._closed:
            return
        self._closed = True
        if not self.fullscreen:
            self.session.settings.setValue("geometry/presenter", self.presenter.saveGeometry())
            self.session.settings.setValue("geometry/audience", self.audience.saveGeometry())
        self.session.save()
        self.session.close()
        self.camera.stop()
        self.posters.close()
        self.media.close()
        self.app.quit()


def main():
    parser = argparse.ArgumentParser(description="PageCue — minimalist PDF presenter")
    parser.add_argument("pdf", nargs="?", type=Path)
    parser.add_argument("--page", "-p", type=int, default=None, help="Initial physical page (1-based)")
    parser.add_argument("--duration", "-d", type=float, default=0, help="Talk duration in minutes")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()
    app = Application(sys.argv[:1])
    app.setApplicationName("PageCue")
    app.setOrganizationName("PageCue")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    presenter = Presenter(app)
    presenter.session.clock.duration = max(0, args.duration * 60)
    presenter.show()
    if args.pdf:
        QTimer.singleShot(0, lambda: presenter.open(args.pdf, page=args.page - 1 if args.page else None))
    app.aboutToQuit.connect(presenter.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
