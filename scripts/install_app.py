"""Install/update/remove an already built PageCue bundle without administrator access.

Uses only Python's standard library. Does not change PDF associations or settings.
"""

import argparse
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

PRODUCT = "org.pku-lemonade.pagecue"


def platform_name():
    if sys.platform == "darwin":
        return "macos"
    if sys.platform == "win32":
        return "windows"
    raise ValueError("Native installation currently targets macOS and Windows")


def default_destination(platform):
    if platform == "macos":
        return Path.home() / "Applications/PageCue.app"
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise ValueError("LOCALAPPDATA is not set; specify --destination")
    return Path(local) / "Programs/PageCue"


def executable(bundle, platform):
    return bundle / ("Contents/MacOS/PageCue" if platform == "macos" else "PageCue.exe")


def identity(bundle, platform):
    # Do not follow an app-directory link when checking ownership for removal.
    if bundle.is_symlink() or not bundle.is_dir():
        raise ValueError(f"Not a PageCue application directory: {bundle}")
    relative = "Contents/Resources/bundle-identity.json" if platform == "macos" else "_internal/bundle-identity.json"
    marker = bundle / relative
    if not marker.resolve().is_relative_to(bundle.resolve()):
        raise ValueError(f"Application identity points outside the bundle: {bundle}")
    try:
        info = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"Missing or invalid PageCue identity: {bundle}") from error
    if not isinstance(info, dict) or info.get("product") != PRODUCT or not isinstance(info.get("version"), str):
        raise ValueError(f"Refusing to modify an unrelated application: {bundle}")
    return info


def validate(bundle, platform):
    info = identity(bundle, platform)
    program = executable(bundle, platform)
    if not program.is_file() or not program.resolve().is_relative_to(bundle.resolve()):
        raise ValueError(f"Missing or invalid application executable: {program}")
    if platform == "macos":
        with (bundle / "Contents/Info.plist").open("rb") as stream:
            plist = plistlib.load(stream)
        if plist.get("CFBundleIdentifier") != PRODUCT or plist.get("CFBundleExecutable") != "PageCue":
            raise ValueError(f"Unexpected macOS bundle identity: {bundle}")
        if plist.get("CFBundleShortVersionString") != info["version"]:
            raise ValueError(f"The bundle version does not match its identity: {bundle}")
        subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(bundle)], check=True)
    return info


def destination_path(value):
    # Resolve the parent only: resolving the final component hides symlink targets.
    path = Path(value).expanduser().absolute()
    if path.name in ("", ".", "..") or path == Path(path.anchor):
        raise ValueError("The destination must name an application directory")
    return path.parent.resolve() / path.name


def install(source, destination, platform):
    source = Path(source).expanduser().absolute()
    destination = destination_path(destination)
    if source.is_symlink():
        raise ValueError("Select the actual source bundle, not a directory symlink")
    source = source.resolve()
    if source == destination or source.is_relative_to(destination) or destination.is_relative_to(source):
        raise ValueError("Source and destination must be separate application directories")
    info = validate(source, platform)
    if destination.exists() or destination.is_symlink():
        identity(destination, platform)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # All renames stay on the destination volume. Keep the old app until the
    # complete staged copy verifies; restore it if the final rename fails.
    temporary = Path(tempfile.mkdtemp(prefix=".pagecue-install-", dir=destination.parent))
    preserve_recovery = False
    try:
        staging = temporary / destination.name
        previous = temporary / "previous"
        shutil.copytree(source, staging, symlinks=True)
        validate(staging, platform)
        if destination.exists():
            destination.rename(previous)
        try:
            staging.rename(destination)
        except OSError:
            if previous.exists():
                try:
                    previous.rename(destination)
                except OSError as error:
                    preserve_recovery = True
                    raise OSError(f"Could not restore the previous app; it is preserved at {previous}") from error
            raise
    finally:
        if not preserve_recovery:
            shutil.rmtree(temporary)
    return info


def uninstall(destination, platform):
    destination = destination_path(destination)
    identity(destination, platform)
    # shutil.rmtree does not follow interior symlinks. Its entire scope is the
    # identified app bundle; preferences and presentation files are elsewhere.
    shutil.rmtree(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, help="Built PageCue.app (Mac) or PageCue directory (Windows)")
    parser.add_argument("--destination", type=Path, help="Override the per-user application location")
    parser.add_argument("--no-shortcut", action="store_true", help="Windows: leave Start Menu shortcuts untouched")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="Verify the installed application without changing it")
    actions.add_argument("--uninstall", action="store_true", help="Remove only the identified PageCue application")
    args = parser.parse_args()
    try:
        platform = platform_name()
        target = destination_path(args.destination or default_destination(platform))
        shortcut = None
        if platform == "windows" and not args.no_shortcut:
            import windows_shortcut
            shortcut = windows_shortcut.default_shortcut()
            windows_shortcut.check_destination(shortcut, executable(target, platform))
        if args.check:
            info = validate(target, platform)
            if shortcut:
                windows_shortcut.verify_shortcut(shortcut, executable(target, platform))
            print(f"Verified PageCue {info['version']}: {target}")
        elif args.uninstall:
            uninstall(target, platform)
            if shortcut:
                windows_shortcut.remove_shortcut(shortcut, executable(target, platform))
            print(f"Removed {target}. Preferences and presentation files were preserved.")
        else:
            if args.source is None:
                parser.error("specify the built application to install")
            info = install(args.source, target, platform)
            if shortcut:
                windows_shortcut.create_shortcut(shortcut, executable(target, platform))
            print(f"Installed PageCue {info['version']}: {target}")
            print(f"Executable: {executable(target, platform)}")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Installation error: {error}\n")


if __name__ == "__main__":
    main()
