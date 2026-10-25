"""Exercise native browser keyboard delivery using only this probe's own windows."""

import argparse
import ctypes
import json
import os
from pathlib import Path
import sys

os.environ["QT_WEBVIEW_PLUGIN"] = "native"
from PySide6.QtCore import QAbstractNativeEventFilter, QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtWebView import QWebView, QWebViewLoadingInfo, QtWebView


class ProbeWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.cocoa_keys = None

    def nativeEvent(self, kind, pointer):
        if self.cocoa_keys is not None:
            return self.cocoa_keys.handle_event("window:" + bytes(kind).decode(), pointer)
        return False, 0


class CocoaKeys(QAbstractNativeEventFilter):
    def __init__(self, window, result):
        super().__init__()
        from importlib.metadata import version
        import objc
        from AppKit import NSApp, NSEvent, NSKeyDown, NSKeyUp
        from Foundation import NSPoint, NSProcessInfo
        self.objc = objc
        self.NSApp, self.NSEvent, self.NSPoint = NSApp, NSEvent, NSPoint
        self.process_info = NSProcessInfo.processInfo()
        self.down, self.up = NSKeyDown, NSKeyUp
        self.window, self.result = window, result
        result["pyobjc"] = version("pyobjc-framework-Cocoa")

    def close(self):
        self.window.cocoa_keys = None
        QApplication.instance().removeNativeEventFilter(self)

    def nativeEventFilter(self, kind, pointer):
        # QCocoaEventDispatcher uses NSEvent for its queued/manual path;
        # QNSApplication uses mac_generic_NSEvent from sendEvent:.
        if bytes(kind) not in (b"NSEvent", b"mac_generic_NSEvent"):
            return False, 0
        return self.handle_event(bytes(kind).decode(), pointer)

    def handle_event(self, path, pointer):
        event = self.objc.objc_object(c_void_p=int(pointer))
        if event.type() not in (self.down, self.up):
            return False, 0
        native = self.objc.objc_object(c_void_p=int(self.window.winId())).window()
        self.result["native_events"].append({"key": int(event.keyCode()), "type": int(event.type()),
            "window": int(event.windowNumber()), "owner": int(native.windowNumber()),
            "path": path})
        if event.window() != native:
            return False, 0
        command = {53: "escape", 96: "fullscreen"}.get(event.keyCode())
        if command:
            if event.type() == self.down:
                self.result["shortcuts"].append(command)
            return True, 0
        return False, 0

    def send(self, chars, code):
        native = self.objc.objc_object(c_void_p=int(self.window.winId())).window()
        def post(kind):
            event = self.NSEvent.keyEventWithType_location_modifierFlags_timestamp_windowNumber_context_characters_charactersIgnoringModifiers_isARepeat_keyCode_(
                kind, self.NSPoint(20, 20), 0, self.process_info.systemUptime(),
                native.windowNumber(), None, chars, chars, False, code)
            self.result.setdefault("posted_events", []).append({"key": code, "type": int(kind),
                "window": int(event.windowNumber()), "timestamp": event.timestamp()})
            self.NSApp().postEvent_atStart_(event, False)
        post(self.down)
        QTimer.singleShot(30, lambda: post(self.up))

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
        self.user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
        self.user32.GetForegroundWindow.restype = wintypes.HWND
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
        class KeyboardInput(ctypes.Structure):
            _fields_ = [("vk", self.types.WORD), ("scan", self.types.WORD),
                        ("flags", self.types.DWORD), ("time", self.types.DWORD), ("extra", ctypes.c_size_t)]
        class MouseInput(ctypes.Structure):
            _fields_ = [("dx", self.types.LONG), ("dy", self.types.LONG), ("data", self.types.DWORD),
                        ("flags", self.types.DWORD), ("time", self.types.DWORD), ("extra", ctypes.c_size_t)]
        class InputData(ctypes.Union):
            _fields_ = [("keyboard", KeyboardInput), ("mouse", MouseInput)]
        class Input(ctypes.Structure):
            _fields_ = [("type", self.types.DWORD), ("data", InputData)]
        self.user32.SendInput.argtypes = [self.types.UINT, ctypes.POINTER(Input), ctypes.c_int]
        owner = int(self.window.winId())
        self.user32.SetForegroundWindow.argtypes = [self.types.HWND]
        self.user32.SetForegroundWindow(owner)
        if self.user32.GetForegroundWindow() != owner:
            raise RuntimeError("Probe is not foreground; no input sent")
        point = self.types.POINT(20, 18)
        self.user32.ClientToScreen.argtypes = [self.types.HWND, ctypes.POINTER(self.types.POINT)]
        self.user32.ClientToScreen(owner, ctypes.byref(point))
        self.user32.SetCursorPos(point.x, point.y)
        clicks = (Input * 2)(Input(0, InputData(mouse=MouseInput(0, 0, 0, 2, 0, 0))),
                             Input(0, InputData(mouse=MouseInput(0, 0, 0, 4, 0, 0))))
        if self.user32.SendInput(2, clicks, ctypes.sizeof(Input)) != 2:
            raise RuntimeError(f"Probe input focus failed: {ctypes.get_last_error()}")

        def send(key, character=None):
            # Synthetic input is confined to the probe on a disposable CI desktop.
            if self.user32.GetForegroundWindow() != int(self.window.winId()):
                self.result["input_error"] = "Probe lost foreground focus; no input sent"
                return
            scan = self.user32.MapVirtualKeyW(key, 0)
            events = (Input * 2)(Input(1, InputData(keyboard=KeyboardInput(key, scan, 0, 0, 0))),
                                 Input(1, InputData(keyboard=KeyboardInput(key, scan, 2, 0, 0))))
            if self.user32.SendInput(2, events, ctypes.sizeof(Input)) != 2:
                self.result["input_error"] = f"SendInput failed: {ctypes.get_last_error()}"
        QTimer.singleShot(200, lambda: send(0x41))
        QTimer.singleShot(400, lambda: send(0x74))
        QTimer.singleShot(600, lambda: send(0x1B))


class QtKeys(QObject):
    def __init__(self, result):
        super().__init__()
        self.result = result

    def eventFilter(self, watched, event):
        if event.type() not in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            return False
        self.result["qt_events"].append({"key": event.key(), "type": int(event.type()),
                                        "target": watched.metaObject().className()})
        command = {Qt.Key.Key_Escape: "escape", Qt.Key.Key_F5: "fullscreen"}.get(event.key())
        if command:
            if event.type() == QEvent.Type.KeyPress:
                self.result["shortcuts"].append(command)
            event.accept()
            return True
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("qa/native-webkeys"))
    parser.add_argument("--cycles", type=int, default=5)
    args = parser.parse_args()
    if args.cycles < 1:
        parser.error("--cycles must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    QtWebView.initialize()
    app = QApplication([])
    app.setApplicationName("PresenteriyakiNativeKeyboardProbe")
    window = ProbeWindow()
    window.probe_output = args.output
    window.resize(600, 400)
    web = QWebView()
    web.setProperty("presenteriyakiShortcuts", True)
    container = QWidget.createWindowContainer(web, window)
    container.setGeometry(0, 0, 600, 400)
    result = {"native_events": [], "qt_events": [], "shortcuts": [], "passed": False}
    keys = CocoaKeys(window, result) if sys.platform == "darwin" else WindowsKeys(window, result)
    if sys.platform == "darwin":
        window.cocoa_keys = keys
    app.installNativeEventFilter(keys)
    done = False

    def finish(error=None):
        nonlocal done
        if done:
            return
        done = True
        if error:
            result["error"] = error
        if sys.platform == "win32":
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32")
            kernel.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            kernel.GetModuleHandleW.restype = wintypes.HMODULE
            kernel.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
            name = ctypes.create_unicode_buffer(32768)
            module = kernel.GetModuleHandleW("qtwebview_webview2.dll")
            if module:
                kernel.GetModuleFileNameW(module, name, len(name))
                result["plugin_path"] = name.value
        (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        app.quit()

    def inspect():
        def received(value):
            result["page"] = json.loads(value)
            cycle = result.get("cycles_passed", 0) + 1
            okay = (result["page"]["value"] == "a" * cycle and result["page"]["keys"] == ["a"] * cycle
                    and result["shortcuts"] == ["fullscreen", "escape"] * cycle)
            if not okay:
                finish("Browser typing or shortcut interception failed")
                return
            result["cycles_passed"] = cycle
            if cycle < args.cycles:
                QTimer.singleShot(100, exercise)
            else:
                result["passed"] = True
                finish()
        web.runJavaScript('JSON.stringify({value:document.querySelector("input").value,keys:window.keys,'
                          'focused:document.hasFocus(),active:document.activeElement.tagName})', received)

    def exercise():
        try:
            keys.exercise()
        except Exception as error:
            finish(str(error))
            return
        QTimer.singleShot(1000, inspect)

    def loaded(info):
        if info.status() == QWebViewLoadingInfo.LoadStatus.Succeeded:
            result["loads"] = result.get("loads", 0) + 1
            if result["loads"] > 1:
                return
            web.runJavaScript('document.querySelector("input").focus()', lambda _: QTimer.singleShot(200, exercise))
        elif info.status() == QWebViewLoadingInfo.LoadStatus.Failed:
            finish(info.errorString())

    web.loadingChanged.connect(loaded)
    window.show()
    window.raise_()
    window.activateWindow()
    qt_keys = QtKeys(result)
    for target in (window, window.windowHandle(), web, container):
        target.installEventFilter(qt_keys)
    web.loadHtml('<!doctype html><input autofocus><script>window.keys=[];'
                 'document.addEventListener("keydown",e=>keys.push(e.key));</script>')
    QTimer.singleShot(10000 + args.cycles * 2000, lambda: finish("Keyboard probe timed out"))
    app.exec()
    if sys.platform == "darwin":
        keys.close()
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
