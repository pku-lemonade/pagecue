"""Exercise real Windows shell links early in CI, before building the full app."""

from pathlib import Path
import tempfile

from windows_shortcut import create_shortcut, remove_shortcut, verify_shortcut


def main():
    with tempfile.TemporaryDirectory(prefix="pagecue-快捷方式 with spaces-") as directory:
        root = Path(directory)
        target = root / "讲稿 $ (test).exe"
        target.write_bytes(b"Original inert shortcut target fixture; never executed.")
        shortcut = root / "菜单/PageCue.lnk"
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
    print("Windows Unicode shortcut create/read/update/refusal/removal passed")


if __name__ == "__main__":
    main()
