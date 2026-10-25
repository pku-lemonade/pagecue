# WebView2 shortcut bridge

This patch forwards Escape and F5 from WebView2's `AcceleratorKeyPressed`
callback to the hosting QWebView as queued Qt key events. It is enabled only
when the view's `presenteriyakiShortcuts` dynamic property is true. Ordinary
browser input retains the backend's behavior. Queuing avoids changing windows
inside WebView2's synchronous input callback.

The Windows app uses this plugin. The app builder and native CI build it
from source; the manual browser workflow can compare it with the upstream plugin
by disabling **patched_windows**.
`scripts/build_native_webview.py`
checks the pinned download hashes, applies the patch, and builds just the Windows
plugin with the installed Visual C++ tools. It does not rebuild Qt or Chromium.

To run the keyboard probe locally in PowerShell:

```powershell
uv run python scripts/build_native_webview.py
$env:QT_PLUGIN_PATH = "$PWD/build/native-webview/plugins"
uv run python scripts/check_native_web_keys.py
```

The probe checks ordinary typing, Escape/F5 delivery, and the loaded plugin's
path. It sends synthetic input only while its own test window is foreground.
The plugin uses Qt's private interface and must be rebuilt and retested when
the pinned Qt version changes.

The upstream source is Qt WebView 6.12.0, commit
`5774c23849cdad2bcdf71ad8c8bd6946dcae38f0`. This dependency patch uses the upstream
LGPL-3.0-only licensing option; the corresponding LGPL and GPL texts accompany
it. Windows packages include the complete modified Qt WebView source archive,
this patch, build configuration, pinned source references, license texts and
Microsoft SDK notices under `licenses/dependencies/native-webview`.
`result.json` records the built DLL's SHA-256, which the package audit verifies.
The application remains MIT licensed. To replace the dependency, rebuild it with
this script against compatible Qt libraries and replace
`_internal/PySide6/plugins/webview/qtwebview_webview2.dll` in the installed app.
Use the bundled CMake configuration and pinned SDKs when rebuilding outside
the application checkout: copy the entire `licenses/dependencies/native-webview`
directory to a writable folder, install Python 3.13+, Visual Studio C++ tools,
CMake and 7-Zip, then run `python scripts/build_native_webview.py` from that folder.
It has the same `scripts/` and `bundle/native-webview/` layout as this repository.

Sources and SHA-256 checksums are in `sources.json`. The Qt SDK and Microsoft
WebView2 SDK are build dependencies, not application source. Microsoft's SDK
retains its own license in the downloaded package.
