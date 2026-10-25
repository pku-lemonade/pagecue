"""Audit the files actually included in a native application."""

import plistlib
import re


def check_payload(bundle, platform):
    files = [p for p in bundle.rglob("*") if p.is_file() and not p.is_symlink()]
    libraries = sorted({match.group(1) for path in files
        for match in re.finditer(r"(Qt(?:6)?[A-Za-z0-9]+)(?:\.framework/|\.dll$)", path.as_posix())})
    qml = [p.relative_to(bundle).as_posix() for p in files if "qml" in p.parts]
    if qml:
        raise ValueError(f"Unused QML plugin tree was bundled: {qml[0]}")
    unexpected = [name for name in libraries if re.match(r"Qt6?(Charts|DataVisualization|Graphs|Quick3D|VirtualKeyboard)", name)]
    if unexpected:
        raise ValueError(f"Unrelated Qt libraries were bundled: {unexpected}")
    result = {"qt_libraries": libraries, "qml_plugins": False}
    if platform == "macos":
        from PyInstaller.utils.osx import macosx_version_min
        with (bundle / "Contents/Info.plist").open("rb") as stream:
            advertised = plistlib.load(stream)["LSMinimumSystemVersion"]
        advertised_version = tuple(int(p) for p in advertised.split("."))
        advertised_version = (advertised_version + (0, 0))[:3]
        required = (0, 0, 0)
        count = 0
        higher_targets = []
        for path in files:
            with path.open("rb") as stream:
                magic = stream.read(4)
            if magic not in (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
                continue
            minimum = macosx_version_min(str(path))
            if minimum > advertised_version:
                higher_targets.append({"file": path.relative_to(bundle).as_posix(),
                                       "target": ".".join(map(str, minimum))})
            required = max(required, minimum)
            count += 1
        if not count:
            raise ValueError("No Mach-O binaries found in the Mac application")
        result.update(macos_minimum=advertised, highest_binary_target=".".join(map(str, required)),
                      mach_o_files=count, higher_deployment_targets=higher_targets)
    return result
