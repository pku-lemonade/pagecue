# Experimental WebView2 shortcut bridge

This patch forwards Escape and F5 from WebView2's `AcceleratorKeyPressed`
callback to the hosting QWebView as queued Qt key events. It is enabled only
when the view's `presenteriyakiShortcuts` dynamic property is true. Ordinary
browser input retains the backend's behavior. Queuing avoids changing windows
inside WebView2's synchronous input callback.

The app does not yet use this plugin. The manual native-browser workflow can
build it with **patched_windows** enabled. `scripts/build_native_webview.py`
checks the pinned download hashes, applies the patch, and builds just the Windows
plugin with the installed Visual C++ tools. It does not rebuild Qt or Chromium.

The upstream source is Qt WebView 6.12.0, commit
`5774c23849cdad2bcdf71ad8c8bd6946dcae38f0`. This dependency patch uses the upstream
LGPL-3.0-only licensing option; the corresponding LGPL and GPL texts accompany
it. The build retains the full upstream source archive and the patch. Before
shipping the plugin, include that modified dependency's notices and corresponding
source/rebuild instructions in the distribution. This experiment does not change
the MIT license of Presenteriyaki's original application code.

Sources and SHA-256 checksums are in `sources.json`. The Qt SDK and Microsoft
WebView2 SDK are build dependencies, not application source. Microsoft's SDK
retains its own license in the downloaded package.
