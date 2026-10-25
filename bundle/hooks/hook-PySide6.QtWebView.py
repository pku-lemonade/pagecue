"""Bundle the native WebView backend without the optional Chromium backend."""

from pathlib import Path
import sys

from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [(source, target) for source, target in binaries if Path(target).name != "webview"]
plugins = pyside6_library_info.collect_plugins("webview")
if sys.platform == "darwin":
    binaries += [(source, target) for source, target in plugins if Path(source).name == "libqtwebview_darwin.dylib"]
elif sys.platform == "win32":
    root = Path(__file__).resolve().parents[2]
    plugin = root / "build/native-webview/plugins/webview/qtwebview_webview2.dll"
    if not plugin.is_file():
        raise RuntimeError("Build the Windows browser plugin with scripts/build_native_webview.py first")
    binaries.append((str(plugin), str(Path(pyside6_library_info.qt_rel_dir) / "plugins/webview")))
else:
    raise RuntimeError("Native application packages support macOS and Windows")
