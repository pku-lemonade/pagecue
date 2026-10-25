"""Keep Qt's linked runtime dependencies without collecting unused QML plugins.

Presenteriyaki uses Widgets, including QWebEngineView, and loads no QML modules.
PyInstaller's default hook collects the entire installed QML plugin tree, which
also pulls unrelated charting and 3D libraries into the application.
"""

from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [(source, target) for source, target in binaries if "qmltooling" not in target]
