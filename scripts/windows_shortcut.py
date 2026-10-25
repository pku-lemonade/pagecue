"""Per-user Windows shell links, without changing associations or script policy."""

import ctypes
import os
from pathlib import Path
import tempfile
import uuid

DESCRIPTION = "PageCue PDF presenter (org.pku-lemonade.pagecue)"


def default_shortcut():
    roaming = os.environ.get("APPDATA")
    if not roaming:
        raise ValueError("APPDATA is not set; use --no-shortcut for a portable installation")
    return Path(roaming) / "Microsoft/Windows/Start Menu/Programs/PageCue.lnk"


def _shell_link(path, target=None):
    """Use IShellLinkW/IPersistFile directly; all path arguments are UTF-16.

    Vtable indices follow the Windows SDK's IShellLinkW and IPersistFile ABI.
    No third-party COM package, interpreter process or shell quoting is involved.
    """
    if os.name != "nt":
        raise OSError("Windows shell links require Windows")
    class GUID(ctypes.Structure):
        _fields_ = [("data1", ctypes.c_uint32), ("data2", ctypes.c_uint16),
                    ("data3", ctypes.c_uint16), ("data4", ctypes.c_ubyte * 8)]
    def guid(value):
        return GUID.from_buffer_copy(uuid.UUID(value).bytes_le)
    def check(result):
        if result < 0:
            raise OSError(f"Windows shell-link operation failed (HRESULT 0x{result & 0xffffffff:08x})")
    def method(pointer, slot, *types):
        table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *types)(table[slot])
    ole = ctypes.WinDLL("ole32")
    ole.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    ole.CoInitializeEx.restype = ctypes.c_long
    ole.CoCreateInstance.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p, ctypes.c_uint32,
                                    ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
    ole.CoCreateInstance.restype = ctypes.c_long
    status = ole.CoInitializeEx(None, 2)  # COINIT_APARTMENTTHREADED
    if status != -2147417850:  # RPC_E_CHANGED_MODE: an existing apartment is usable
        check(status)
    link, persist = ctypes.c_void_p(), ctypes.c_void_p()
    try:
        clsid = guid("00021401-0000-0000-c000-000000000046")
        interface = guid("000214f9-0000-0000-c000-000000000046")
        check(ole.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(interface), ctypes.byref(link)))
        persistence = guid("0000010b-0000-0000-c000-000000000046")
        check(method(link, 0, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))(
            link, ctypes.byref(persistence), ctypes.byref(persist)))
        if target is not None:
            for slot, value in ((20, str(target)), (7, DESCRIPTION), (9, str(target.parent)), (11, "")):
                check(method(link, slot, ctypes.c_wchar_p)(link, value))
            check(method(link, 17, ctypes.c_wchar_p, ctypes.c_int)(link, str(target), 0))
            check(method(persist, 6, ctypes.c_wchar_p, ctypes.c_int)(persist, str(path), 1))
        else:
            check(method(persist, 5, ctypes.c_wchar_p, ctypes.c_uint32)(persist, str(path), 0))
        result = {}
        for key, slot in (("target", 3), ("description", 6), ("arguments", 10)):
            buffer = ctypes.create_unicode_buffer(4096)
            if key == "target":
                check(method(link, slot, ctypes.c_wchar_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)(
                    link, buffer, len(buffer), None, 4))  # SLGP_RAWPATH; do not resolve/search
            else:
                check(method(link, slot, ctypes.c_wchar_p, ctypes.c_int)(link, buffer, len(buffer)))
            result[key] = buffer.value
        return result
    finally:
        for pointer in (persist, link):
            if pointer.value:
                method(pointer, 2)(pointer)  # IUnknown::Release
        if status >= 0:
            ole.CoUninitialize()


def verify_shortcut(path, target):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Not a PageCue shortcut: {path}")
    info = _shell_link(path)
    if (os.path.normcase(info["target"]) != os.path.normcase(str(target))
            or info["arguments"] or info["description"] != DESCRIPTION):
        raise ValueError(f"Refusing to replace an unrelated shortcut: {path}")


def check_destination(path, target):
    if path.exists() or path.is_symlink():
        verify_shortcut(path, target)


def create_shortcut(path, target):
    check_destination(path, target)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".pagecue-link-", dir=path.parent) as temporary:
        staged = Path(temporary) / "PageCue.lnk"
        _shell_link(staged, target)
        verify_shortcut(staged, target)
        os.replace(staged, path)


def remove_shortcut(path, target):
    if path.exists() or path.is_symlink():
        verify_shortcut(path, target)
        path.unlink()
