"""Small AppKit presentation integration; all drawing/windows remain Qt-owned."""

import ctypes
import ctypes.util

from PySide6.QtCore import QAbstractNativeEventFilter, Qt


class BrowserIntegration(QAbstractNativeEventFilter):
    """Route browser shortcuts and keep its camera window attached to the audience."""

    def __init__(self, browser):
        super().__init__()
        self.browser = browser
        library = ctypes.CDLL(ctypes.util.find_library("objc"))
        library.sel_registerName.argtypes = [ctypes.c_char_p]
        library.sel_registerName.restype = ctypes.c_void_p
        self.type_selector = library.sel_registerName(b"type")
        self.key_selector = library.sel_registerName(b"keyCode")
        self.window_selector = library.sel_registerName(b"window")
        self.repeat_selector = library.sel_registerName(b"isARepeat")
        self.get_type = ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", library))
        self.get_key = ctypes.CFUNCTYPE(ctypes.c_ushort, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", library))
        self.get_window = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", library))
        self.get_repeat = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", library))
        self.parent_selector = library.sel_registerName(b"parentWindow")
        self.add_child_selector = library.sel_registerName(b"addChildWindow:ordered:")
        self.remove_child_selector = library.sel_registerName(b"removeChildWindow:")
        self.add_child = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)(
            ("objc_msgSend", library))
        self.remove_child = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(
            ("objc_msgSend", library))

    def attach_camera(self):
        child = self.get_window(int(self.browser.camera.winId()), self.window_selector)
        owner = self.get_window(int(self.browser.audience.winId()), self.window_selector)
        if self.get_window(child, self.parent_selector) != owner:
            # Qt's transient-parent hint does not create an AppKit child window.
            # A child stays directly above its owner during activation/restore.
            self.add_child(owner, self.add_child_selector, child, 1)  # NSWindowAbove

    def detach_camera(self):
        child = self.get_window(int(self.browser.camera.winId()), self.window_selector)
        owner = self.get_window(child, self.parent_selector)
        if owner:
            self.remove_child(owner, self.remove_child_selector, child)

    def nativeEventFilter(self, kind, pointer):
        if bytes(kind) not in (b"NSEvent", b"mac_generic_NSEvent") or not self.browser.isVisible():
            return False, 0
        event = int(pointer)
        event_type = self.get_type(event, self.type_selector)
        if event_type not in (10, 11):  # NSEvent key down/up
            return False, 0
        owner = self.get_window(int(self.browser.audience.winId()), self.window_selector)
        if self.get_window(event, self.window_selector) != owner:
            return False, 0
        key = {53: Qt.Key.Key_Escape, 96: Qt.Key.Key_F5}.get(self.get_key(event, self.key_selector))
        if key is None:
            return False, 0
        if event_type == 10 and not self.get_repeat(event, self.repeat_selector):
            self.browser.shortcut.emit(key)
        return True, 0


class PresentationOptions:
    """Temporarily auto-hide the menu/Dock without moving windows into Spaces."""

    def __init__(self):
        library = ctypes.CDLL(ctypes.util.find_library("objc"))
        library.objc_getClass.argtypes = [ctypes.c_char_p]
        library.objc_getClass.restype = ctypes.c_void_p
        library.sel_registerName.argtypes = [ctypes.c_char_p]
        library.sel_registerName.restype = ctypes.c_void_p
        self.selector = library.sel_registerName
        send_object = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", library))
        self.get_options = ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", library))
        self.set_options = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)(("objc_msgSend", library))
        self.application = send_object(library.objc_getClass(b"NSApplication"), self.selector(b"sharedApplication"))
        self.previous = None

    def enter(self):
        if self.previous is not None:
            return
        self.previous = self.get_options(self.application, self.selector(b"presentationOptions"))
        # AppKit forbids pairing HideDock/MenuBar with the respective AutoHide bit.
        options = self.previous
        if not options & (1 << 1):
            options |= 1 << 0  # NSApplicationPresentationAutoHideDock
        if not options & (1 << 3):
            options |= 1 << 2  # NSApplicationPresentationAutoHideMenuBar
        self.set_options(self.application, self.selector(b"setPresentationOptions:"), options)

    def leave(self):
        if self.previous is not None:
            self.set_options(self.application, self.selector(b"setPresentationOptions:"), self.previous)
            self.previous = None
