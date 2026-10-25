"""Small AppKit presentation integration; all drawing/windows remain Qt-owned."""

import ctypes
import ctypes.util


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
