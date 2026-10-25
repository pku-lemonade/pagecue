"""Trace the probe's own Cocoa queue and dispatch without changing event handling."""

import ctypes
import ctypes.util
import sys

import check_native_web_keys as probe


class DispatchTrace:
    def __init__(self, result):
        import objc
        from AppKit import NSApp
        self.objc = objc
        self.entries = result.setdefault("dispatch_trace", [])
        self.runtime = ctypes.CDLL(ctypes.util.find_library("objc"))
        runtime = self.runtime
        runtime.object_getClass.argtypes = [ctypes.c_void_p]
        runtime.object_getClass.restype = ctypes.c_void_p
        runtime.sel_registerName.argtypes = [ctypes.c_char_p]
        runtime.sel_registerName.restype = ctypes.c_void_p
        runtime.class_getInstanceMethod.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        runtime.class_getInstanceMethod.restype = ctypes.c_void_p
        runtime.method_getImplementation.argtypes = [ctypes.c_void_p]
        runtime.method_getImplementation.restype = ctypes.c_void_p
        runtime.method_setImplementation.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        runtime.method_setImplementation.restype = ctypes.c_void_p
        application_class = runtime.object_getClass(objc.pyobjc_id(NSApp()))
        self.replacements = []
        pointer = ctypes.c_void_p
        send_type = ctypes.CFUNCTYPE(None, pointer, pointer, pointer)
        next_type = ctypes.CFUNCTYPE(pointer, pointer, pointer, ctypes.c_ulong, pointer, pointer, ctypes.c_bool)

        def wrap_send(original):
            def send(receiver, selector, event):
                self.record("send", event)
                original(receiver, selector, event)
            return send

        def wrap_next(original):
            def next_event(receiver, selector, mask, date, mode, dequeue):
                event = original(receiver, selector, mask, date, mode, dequeue)
                self.record("dequeue" if dequeue else "peek", event)
                return event
            return next_event

        for name, signature, wrapper in (
            (b"sendEvent:", send_type, wrap_send),
            (b"nextEventMatchingMask:untilDate:inMode:dequeue:", next_type, wrap_next),
        ):
            method = runtime.class_getInstanceMethod(application_class, runtime.sel_registerName(name))
            original_address = runtime.method_getImplementation(method)
            callback = signature(wrapper(signature(original_address)))
            runtime.method_setImplementation(method, ctypes.cast(callback, pointer))
            self.replacements.append((method, original_address, callback))

    def record(self, stage, pointer):
        if not pointer:
            return
        event = self.objc.objc_object(c_void_p=pointer)
        if int(event.type()) in (10, 11):
            self.entries.append({"stage": stage, "key": int(event.keyCode()),
                "type": int(event.type()), "window": int(event.windowNumber()), "timestamp": event.timestamp()})

    def close(self):
        for method, original, callback in reversed(self.replacements):
            self.runtime.method_setImplementation(method, original)


if sys.platform != "darwin":
    raise SystemExit("This trace is only for the Mac keyboard probe.")

original_init = probe.CocoaKeys.__init__
original_close = probe.CocoaKeys.close


def traced_init(self, window, result):
    original_init(self, window, result)
    self.dispatch_trace = DispatchTrace(result)


def traced_close(self):
    self.dispatch_trace.close()
    original_close(self)


probe.CocoaKeys.__init__ = traced_init
probe.CocoaKeys.close = traced_close

if __name__ == "__main__":
    probe.main()
