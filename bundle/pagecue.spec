# Build with: uv run python scripts/build_app.py
from pathlib import Path
import json
import sys
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).parent
version = json.loads((root / "build/bundle-identity.json").read_text())["version"]
datas = collect_data_files("pagecue")
for name in ("pypdf", "cryptography", "packaging"):
    datas += copy_metadata(name)
datas += [(str(root / "LICENSE"), "licenses"),
          (str(root / "docs/DISTRIBUTION.md"), "licenses"),
          (str(root / "build/notices"), "licenses/dependencies"),
          (str(root / "build/bundle-identity.json"), ".")]
a = Analysis([str(root / "bundle/entrypoint.py")], pathex=[str(root / "src")],
    datas=datas, binaries=[], hiddenimports=["PySide6.QtSvg", "PySide6.QtWebEngineWidgets"],
    excludes=["tkinter", "numpy", "scipy", "matplotlib", "IPython", "pytest", "reportlab"],
    noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PageCue", debug=False,
    strip=False, upx=False, console=False,
    icon=str(root / "build/icon.png"),
    entitlements_file=str(root / "bundle/macos-entitlements.plist") if sys.platform == "darwin" else None)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="PageCue")
if sys.platform == "darwin":
    app = BUNDLE(collection, name="PageCue.app", icon=str(root / "build/icon.png"),
        bundle_identifier="org.pku-lemonade.pagecue", version=version,
        info_plist={
            "CFBundleDisplayName": "PageCue", "CFBundleShortVersionString": version,
            "LSMinimumSystemVersion": "14.0", "NSHighResolutionCapable": True,
            "NSCameraUsageDescription": "Show your camera as an optional inset in your presentation.",
            "NSCameraUseContinuityCameraDeviceType": True,
            "CFBundleDocumentTypes": [{"CFBundleTypeName": "PDF presentation", "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate", "LSItemContentTypes": ["com.adobe.pdf"]}],
        })
