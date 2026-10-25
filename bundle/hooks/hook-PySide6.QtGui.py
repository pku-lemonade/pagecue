"""Use native input methods; do not bundle Qt's separate virtual keyboard."""

from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [(source, target) for source, target in binaries if "qtvirtualkeyboard" not in source.lower()]
