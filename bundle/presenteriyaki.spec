# Build with: uv run python scripts/build_app.py
from pathlib import Path
import json
import os
import sys
import sysconfig
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).parent
version = json.loads((root / "build/bundle-identity.json").read_text())["version"]
datas = collect_data_files("presenteriyaki")
for name in ("pypdf", "cryptography", "packaging"):
    datas += copy_metadata(name)
datas += [(str(root / "LICENSE"), "licenses"),
          (str(root / "docs/DISTRIBUTION.md"), "licenses"),
          (str(root / "build/notices"), "licenses/dependencies"),
          (str(root / "build/bundle-identity.json"), ".")]
a = Analysis([str(root / "bundle/entrypoint.py")], pathex=[str(root / "src")],
    hookspath=[str(root / "bundle/hooks")],
    datas=datas, binaries=[], hiddenimports=["PySide6.QtSvg", "PySide6.QtWebView"],
    excludes=["tkinter", "numpy", "scipy", "matplotlib", "IPython", "pytest", "reportlab", "PIL",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick"],
    noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Presenteriyaki", debug=False,
    strip=False, upx=False, console=False,
    codesign_identity=os.environ.get("PRESENTERIYAKI_CODESIGN_IDENTITY"),
    icon=str(root / "build/icon.png"),
    entitlements_file=str(root / "bundle/macos-entitlements.plist") if sys.platform == "darwin" else None)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Presenteriyaki")
if sys.platform == "darwin":
    from PySide6._config import __qt_macos_min_deployment_target__
    minimum = max(tuple(map(int, value.split("."))) for value in (
        __qt_macos_min_deployment_target__, sysconfig.get_config_var("MACOSX_DEPLOYMENT_TARGET")))
    app = BUNDLE(collection, name="Presenteriyaki.app", icon=str(root / "build/icon.png"),
        bundle_identifier="org.pku-lemonade.pagecue", version=version,
        info_plist={
            "CFBundleDisplayName": "Presenteriyaki", "CFBundleShortVersionString": version,
            "LSMinimumSystemVersion": ".".join(map(str, minimum)), "NSHighResolutionCapable": True,
            "NSCameraUsageDescription": "Show your camera as an optional inset in your presentation.",
            "NSCameraUseContinuityCameraDeviceType": True,
            "CFBundleDocumentTypes": [{"CFBundleTypeName": "PDF presentation", "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate", "LSItemContentTypes": ["com.adobe.pdf"]}],
        })
