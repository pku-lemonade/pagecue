"""Native web content hosted in the audience window."""

import os
from pathlib import Path
import sys

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect, Qt, Signal
from PySide6.QtWidgets import QWidget
from PySide6.QtWebView import QWebView, QWebViewLoadingInfo, QWebViewSettings, QtWebView

from .canvas import WebCameraOverlay


SHORTCUTS = (Qt.Key.Key_Escape, Qt.Key.Key_F5)


def initialize():
    """Select native plugins before constructing QApplication."""
    os.environ["QT_WEBVIEW_PLUGIN"] = "native"
    if sys.platform == "win32" and not getattr(sys, "frozen", False):
        plugins = Path(__file__).resolve().parents[2] / "build/native-webview/plugins"
        if plugins.is_dir():
            QCoreApplication.addLibraryPath(str(plugins))
    QtWebView.initialize()


class Browser(QWidget):
    loadFinished = Signal(bool)
    shortcut = Signal(int)

    def __init__(self, canvas, parent):
        super().__init__(parent)
        self.canvas = canvas
        self.audience = parent
        self._zoom = 1.0
        self._closed = False
        self.native = QWebView()
        self.native.setProperty("presenteriyakiShortcuts", True)
        self.native.settings().setAttribute(QWebViewSettings.WebAttribute.AllowFileAccess, True)
        if sys.platform == "darwin":
            self.native.settings().setAttribute(QWebViewSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self.container = QWidget.createWindowContainer(self.native, self)
        self.setFocusProxy(self.container)
        self.native.installEventFilter(self)
        self.container.installEventFilter(self)
        self.native.loadingChanged.connect(self._loaded)
        self.camera = WebCameraOverlay(canvas, parent)
        camera_type = Qt.WindowType.Window if sys.platform == "darwin" else Qt.WindowType.Tool
        self.camera.setWindowFlags(camera_type | Qt.WindowType.FramelessWindowHint |
                                   Qt.WindowType.WindowTransparentForInput | Qt.WindowType.WindowDoesNotAcceptFocus |
                                   Qt.WindowType.NoDropShadowWindowHint)
        self.camera.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.camera.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        parent.installEventFilter(self)
        self.native_keys = None
        if sys.platform == "darwin":
            from .macos import BrowserKeys
            self.native_keys = BrowserKeys(self)
            QCoreApplication.instance().installNativeEventFilter(self.native_keys)
        self.hide()

    def load(self, url):
        self.native.setUrl(url)

    def page(self):
        return self.native

    def zoomFactor(self):
        return self._zoom

    def setZoomFactor(self, factor):
        self._zoom = factor
        self._apply_zoom()

    def _apply_zoom(self):
        # Preserve any zoom the document itself supplied. A navigation gets a
        # fresh document and therefore a fresh baseline.
        self.native.runJavaScript(f"""(() => {{
            const root = document.documentElement;
            if (!root) return;
            if (window.__presenteriyakiBaseZoom === undefined)
                window.__presenteriyakiBaseZoom = parseFloat(getComputedStyle(root).zoom) || 1;
            root.style.zoom = window.__presenteriyakiBaseZoom * {self._zoom};
        }})()""", lambda _: None)

    def _loaded(self, info):
        if self._closed:
            return
        if info.status() == QWebViewLoadingInfo.LoadStatus.Succeeded:
            self._apply_zoom()
            self.loadFinished.emit(True)
        elif info.status() == QWebViewLoadingInfo.LoadStatus.Failed:
            self.loadFinished.emit(False)

    def update_camera(self):
        if self._closed:
            return
        visible = (self.isVisible() and self.audience.isVisible() and
                   not self.audience.isMinimized() and self.canvas.camera_image is not None)
        # Cocoa does not update a transient window's level when its owner enters
        # our borderless fullscreen mode. Keep both windows at the same level.
        if sys.platform == "darwin":
            self.camera.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,
                                      bool(self.audience.windowFlags() & Qt.WindowType.WindowStaysOnTopHint))
        showing = visible and self.camera.isHidden()
        self.camera.setGeometry(QRect(self.mapToGlobal(QPoint(0, 0)), self.size()))
        self.camera.setVisible(visible)
        if visible:
            if showing:
                self.camera.raise_()
            self.camera.update()

    def eventFilter(self, watched, event):
        if self._closed:
            return False
        if watched is self.audience and event.type() in (
            QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.Hide,
            QEvent.Type.WindowStateChange, QEvent.Type.WinIdChange, QEvent.Type.ZOrderChange,
            QEvent.Type.WindowActivate,
        ):
            self.update_camera()
            if event.type() in (QEvent.Type.ZOrderChange, QEvent.Type.WindowActivate) and self.camera.isVisible():
                self.camera.raise_()
        if (watched is self.native or watched is self.container) and event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            if self.isVisible() and event.key() in SHORTCUTS:
                if event.type() == QEvent.Type.KeyPress and not event.isAutoRepeat():
                    self.shortcut.emit(event.key())
                event.accept()
                return True
        return False

    def keyPressEvent(self, event):
        if event.key() in SHORTCUTS:
            if not event.isAutoRepeat():
                self.shortcut.emit(event.key())
            event.accept()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.container.setGeometry(self.rect())
        self.update_camera()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_camera()

    def hideEvent(self, event):
        self.camera.hide()
        super().hideEvent(event)

    def shutdown(self):
        self._closed = True
        if self.native_keys is not None:
            QCoreApplication.instance().removeNativeEventFilter(self.native_keys)
            self.native_keys = None
        self.native.stop()
        self.camera.close()
