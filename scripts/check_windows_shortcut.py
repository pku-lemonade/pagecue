"""Exercise real Windows shell links early in CI, before building the full app."""

from pathlib import Path
import tempfile

from windows_shortcut import create_shortcut, remove_shortcut, verify_shortcut
import windows_shortcut


def main():
    with tempfile.TemporaryDirectory(prefix="presenteriyaki-快捷方式 with spaces-") as directory:
        root = Path(directory)
        target = root / "讲稿 $ (test).exe"
        target.write_bytes(b"Original inert shortcut target fixture; never executed.")
        shortcut = root / "菜单/Presenteriyaki.lnk"
        create_shortcut(shortcut, target)
        verify_shortcut(shortcut, target)
        create_shortcut(shortcut, target)
        try:
            create_shortcut(shortcut, root / "unrelated.exe")
        except ValueError:
            verify_shortcut(shortcut, target)
        else:
            raise AssertionError("Replaced an unrelated shortcut")
        remove_shortcut(shortcut, target)
        assert not shortcut.exists() and target.exists()
        legacy = root / "菜单/PageCue.lnk"
        windows_shortcut.DESCRIPTION = windows_shortcut.LEGACY_DESCRIPTION
        try:
            create_shortcut(legacy, target)
        finally:
            windows_shortcut.DESCRIPTION = "Presenteriyaki PDF presenter (org.pku-lemonade.pagecue)"
        replacement = root / "Presenteriyaki.exe"
        replacement.write_bytes(b"Original inert replacement fixture; never executed.")
        create_shortcut(legacy, replacement, previous_target=target)
        verify_shortcut(legacy, replacement)
        remove_shortcut(legacy, replacement)
        assert not legacy.exists()
    print("Windows Unicode shortcut create/read/update/refusal/removal passed")


if __name__ == "__main__":
    main()
