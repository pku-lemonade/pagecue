"""Exercise native browser keyboard delivery using only this probe's own windows."""

import argparse
import ctypes
import json
import os
from pathlib import Path
import sys

os.environ["QT_WEBVIEW_PLUGIN"] = "native"
from PySide6.QtCore import QAbstractNativeEventFilter, QTimer
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtWebView import QWebView, QWebViewLoadingInfo, QtWebView


class CocoaKeys(QAbstractNativeEventFilter):
    def __init__(self, window, result):
        super().__init__()
        import objc
        from AppKit import NSApp, NSEvent, NSKeyDown, NSKeyUp
        from Foundation import NSPoint
        self.objc = objc
        self.NSApp, self.NSEvent, self.NSPoint = NSApp, NSEvent, NSPoint
        self.down, self.up = NSKeyDown, NSKeyUp
        self.window, self.result = window, result

    def nativeEventFilter(self, kind, pointer):
        if bytes(kind) != b"mac_generic_NSEvent":
            return False, 0
        event = self.objc.objc_object(c_void_p=int(pointer))
        if event.type() not in (self.down, self.up):
            return False, 0
        native = self.objc.objc_object(c_void_p=int(self.window.winId())).window()
        if event.window() != native:
            return False, 0
        self.result["native_events"].append(int(event.keyCode()))
        command = {53: "escape", 96: "fullscreen"}.get(event.keyCode())
        if command:
            if event.type() == self.down:
                self.result["shortcuts"].append(command)
            return True, 0
        return False, 0

    def send(self, chars, code):
        native = self.objc.objc_object(c_void_p=int(self.window.winId())).window()
        for kind in (self.down, self.up):
            event = self.NSEvent.keyEventWithType_location_modifierFlags_timestamp_windowNumber_context_characters_charactersIgnoringModifiers_isARepeat_keyCode_(
                kind, self.NSPoint(20, 20), 0, 0, native.windowNumber(), None, chars, chars, False, code)
            self.NSApp().postEvent_atStart_(event, False)

    def exercise(self):
        self.send("a", 0)
        QTimer.singleShot(200, lambda: self.send("\uf708", 96))
        QTimer.singleShot(400, lambda: self.send("\x1b", 53))


class WindowsKeys(QAbstractNativeEventFilter):
    def __init__(self, window, result):
        super().__init__()
        from ctypes import wintypes
        self.types = wintypes
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.GetParent.argtypes = [wintypes.HWND]
        self.user32.GetParent.restype = wintypes.HWND
        self.user32.IsChild.argtypes = [wintypes.HWND, wintypes.HWND]
        self.user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.window, self.result = window, result

    def nativeEventFilter(self, kind, pointer):
        if bytes(kind) not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return False, 0
        message = ctypes.cast(int(pointer), ctypes.POINTER(self.types.MSG)).contents
        if message.message not in (0x100, 0x101, 0x102):
            return False, 0
        owner = int(self.window.winId())
        if message.hWnd != owner and not self.user32.IsChild(owner, message.hWnd):
            return False, 0
        self.result["native_events"].append({"key": message.wParam, "message": message.message})
        command = {0x1B: "escape", 0x74: "fullscreen"}.get(message.wParam)
        if command and message.message in (0x100, 0x101):
            if message.message == 0x100:
                self.result["shortcuts"].append(command)
            return True, 0
        return False, 0

    def exercise(self):
        callback_type = ctypes.WINFUNCTYPE(self.types.BOOL, self.types.HWND, self.types.LPARAM)
        children = []
        def child(hwnd, _):
            name = ctypes.create_unicode_buffer(256)
            self.user32.GetClassNameW.argtypes = [self.types.HWND, self.types.LPWSTR, ctypes.c_int]
            self.user32.GetClassNameW(hwnd, name, 256)
            pid = self.types.DWORD()
            self.user32.GetWindowThreadProcessId.argtypes = [self.types.HWND, ctypes.POINTER(self.types.DWORD)]
            thread = self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            children.append({"hwnd": int(hwnd), "class": name.value, "pid": pid.value, "thread": thread})
            return True
        self.user32.EnumChildWindows.argtypes = [self.types.HWND, callback_type, self.types.LPARAM]
        self.user32.EnumChildWindows(int(self.window.winId()), callback_type(child), 0)
        self.result["children"] = children
        target = next(c["hwnd"] for c in children if c["class"] == "Chrome_RenderWidgetHostHWND")
        # Target the embedded renderer, never the system foreground window.
        def send(key, character=None):
            self.user32.PostMessageW(target, 0x100, key, 1)
            if character:
                self.user32.PostMessageW(target, 0x102, ord(character), 1)
            self.user32.PostMessageW(target, 0x101, key, 0xC0000001)
        send(0x41, "a")
        QTimer.singleShot(200, lambda: send(0x74))
        QTimer.singleShot(400, lambda: send(0x1B))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("qa/native-webkeys"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    QtWebView.initialize()
    app = QApplication([])
    app.setApplicationName("PresenteriyakiNativeKeyboardProbe")
    window = QWidget()
    window.resize(600, 400)
    web = QWebView()
    container = QWidget.createWindowContainer(web, window)
    container.setGeometry(0, 0, 600, 400)
    result = {"native_events": [], "shortcuts": [], "passed": False}
    keys = CocoaKeys(window, result) if sys.platform == "darwin" else WindowsKeys(window, result)
    app.installNativeEventFilter(keys)
    done = False

    def finish(error=None):
        nonlocal done
        if done:
            return
        done = True
        if error:
            result["error"] = error
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        app.quit()

    def inspect():
        def received(value):
            result["page"] = json.loads(value)
            result["passed"] = (result["page"]["value"] == "a" and result["page"]["keys"] == ["a"]
                                and result["shortcuts"] == ["fullscreen", "escape"])
            finish(None if result["passed"] else "Browser typing or shortcut interception failed")
        web.runJavaScript('JSON.stringify({value:document.querySelector("input").value,keys:window.keys})', received)

    def exercise():
        try:
            keys.exercise()
        except Exception as error:
            finish(str(error))
            return
        QTimer.singleShot(1000, inspect)

    def loaded(info):
        if info.status() == QWebViewLoadingInfo.LoadStatus.Succeeded:
            web.runJavaScript('document.querySelector("input").focus()', lambda _: QTimer.singleShot(200, exercise))
        elif info.status() == QWebViewLoadingInfo.LoadStatus.Failed:
            finish(info.errorString())

    web.loadingChanged.connect(loaded)
    window.show()
    window.raise_()
    window.activateWindow()
    web.loadHtml('<!doctype html><input autofocus><script>window.keys=[];'
                 'document.addEventListener("keydown",e=>keys.push(e.key));</script>')
    QTimer.singleShot(15000, lambda: finish("Keyboard probe timed out"))
    app.exec()
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
