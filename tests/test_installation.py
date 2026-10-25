"""Exercise destructive installer boundaries and update rollback in temporary paths."""

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("install_app", Path(__file__).parents[1] / "scripts/install_app.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def bundle(path, version="0.1.0", legacy=False):
    (path / "_internal").mkdir(parents=True)
    (path / "_internal/bundle-identity.json").write_text(json.dumps({"product": installer.PRODUCT, "version": version}))
    (path / ("PageCue.exe" if legacy else "Presenteriyaki.exe")).write_bytes(b"original synthetic executable")
    return path


def test_new_named_install_preserves_and_can_update_legacy_bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    old_path = installer.default_destination("windows", legacy=True)
    new_path = installer.default_destination("windows")
    assert old_path.name == "PageCue" and new_path.name == "Presenteriyaki"
    old = bundle(old_path, legacy=True)
    previous = (old / "PageCue.exe").read_bytes()
    source = bundle(tmp_path / "renamed-source", "0.2.0")
    (source / "PageCue.exe").write_bytes(b"compatibility launcher")
    installer.install(source, new_path, "windows")
    assert installer.validate(old, "windows")["version"] == "0.1.0"
    assert (old / "PageCue.exe").read_bytes() == previous
    assert installer.executable(new_path, "windows").name == "Presenteriyaki.exe"
    assert installer.executable(new_path, "windows", legacy=True).name == "PageCue.exe"
    # An explicit update of the old location also retains the old executable path.
    installer.install(source, old_path, "windows")
    assert installer.validate(old, "windows")["version"] == "0.2.0"
    assert (old / "PageCue.exe").read_bytes() == b"compatibility launcher"
    installer.uninstall(old_path, "windows")
    assert installer.validate(new_path, "windows")["version"] == "0.2.0"


def test_install_update_remove_preserves_unrelated_files(tmp_path):
    source = bundle(tmp_path / "build")
    target = tmp_path / "应用程序 with spaces/Presenteriyaki"
    slides = tmp_path / "talk.pdf"
    slides.write_bytes(b"keep my slides")
    installer.install(source, target, "windows")
    assert installer.validate(target, "windows")["version"] == "0.1.0"
    # Updating replaces the whole old payload, including obsolete libraries.
    (target / "_internal/obsolete.dll").write_bytes(b"old")
    replacement = bundle(tmp_path / "new-build", "0.2.0")
    installer.install(replacement, target, "windows")
    assert installer.identity(target, "windows")["version"] == "0.2.0"
    assert not (target / "_internal/obsolete.dll").exists()
    installer.uninstall(target, "windows")
    assert not target.exists()
    assert slides.read_bytes() == b"keep my slides"
    assert source.exists() and replacement.exists()


def test_installer_refuses_unknown_destination_and_links(tmp_path):
    source = bundle(tmp_path / "build")
    target = tmp_path / "OtherApp"
    target.mkdir()
    (target / "keep").write_text("existing user app")
    with pytest.raises(ValueError):
        installer.install(source, target, "windows")
    with pytest.raises(ValueError):
        installer.uninstall(target, "windows")
    assert (target / "keep").read_text() == "existing user app"
    link = tmp_path / "link"
    try:
        link.symlink_to(source, target_is_directory=True)
    except OSError:
        pytest.skip("Creating directory symlinks is unavailable on this host")
    with pytest.raises(ValueError):
        installer.uninstall(link, "windows")
    with pytest.raises(ValueError):
        installer.install(source, link, "windows")
    assert source.exists()


def test_failed_update_restores_previous_application(tmp_path, monkeypatch):
    source = bundle(tmp_path / "build", "0.2.0")
    target = bundle(tmp_path / "installed", "0.1.0")
    original = Path.rename
    def failed_commit(path, destination):
        if path.name == target.name and path.parent.name.startswith(".presenteriyaki-install-"):
            raise PermissionError("simulated running executable/rename failure")
        return original(path, destination)
    monkeypatch.setattr(Path, "rename", failed_commit)
    with pytest.raises(PermissionError):
        installer.install(source, target, "windows")
    assert installer.validate(target, "windows")["version"] == "0.1.0"


def test_invalid_source_and_nested_destination_preserve_install(tmp_path):
    source = bundle(tmp_path / "build")
    target = bundle(tmp_path / "installed")
    (source / "Presenteriyaki.exe").unlink()
    with pytest.raises(ValueError):
        installer.install(source, target, "windows")
    assert installer.validate(target, "windows")["version"] == "0.1.0"
    with pytest.raises(ValueError):
        installer.install(target, target / "nested", "windows")


def test_failed_rollback_leaves_recoverable_old_app(tmp_path, monkeypatch):
    source = bundle(tmp_path / "build", "0.2.0")
    target = bundle(tmp_path / "installed", "0.1.0")
    original = Path.rename
    def failed_commit_and_restore(path, destination):
        if path.parent.name.startswith(".presenteriyaki-install-"):
            raise PermissionError("simulated destination locked")
        return original(path, destination)
    monkeypatch.setattr(Path, "rename", failed_commit_and_restore)
    with pytest.raises(OSError, match="preserved at"):
        installer.install(source, target, "windows")
    backups = list(tmp_path.glob(".presenteriyaki-install-*/previous"))
    assert len(backups) == 1
    assert installer.validate(backups[0], "windows")["version"] == "0.1.0"
