import importlib.util
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location("source_notices", Path(__file__).parents[1] / "scripts/collect_qt_source_notices.py")
notices = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notices)


@pytest.mark.parametrize("include_license", [True, False])
def test_archive_preserves_copyright_and_resolves_referenced_and_standard_licenses(tmp_path, include_license):
    archive = tmp_path / "original-fixture.tar.xz"
    files = {
        "LICENSES/MIT.txt": "Original test license text",
        "src/component/COPYRIGHT": "Copyright: original fixture authors",
        "src/component/qt_attribution.json": json.dumps([
            {"Id": "explicit", "LicenseFile": "../SHARED-LICENSE", "CopyrightFile": "COPYRIGHT"},
            {"Id": "standard", "LicenseId": "MIT", "Copyright": "Original fixture authors"},
        ]),
    }
    if include_license:
        files["src/SHARED-LICENSE"] = "Original shared-license fixture"
    with tarfile.open(archive, "w:xz") as output:
        for name, value in files.items():
            data = value.encode()
            member = tarfile.TarInfo("fixture/" + name)
            member.size = len(data)
            output.addfile(member, BytesIO(data))
    if not include_license:
        with pytest.raises(ValueError, match="Missing referenced notice text"):
            notices.collect(archive, "fixture", "1")
        return
    result = notices.collect(archive, "fixture", "1")
    assert result["texts"]["src/SHARED-LICENSE"] == files["src/SHARED-LICENSE"]
    assert result["texts"]["src/component/COPYRIGHT"] == files["src/component/COPYRIGHT"]
    assert result["components"][1]["text_files"] == ["LICENSES/MIT.txt"]
    assert result["components"][1]["attribution"]["Copyright"] == "Original fixture authors"


@pytest.mark.parametrize("valid_hash", [True, False])
def test_external_standard_license_keeps_source_and_rejects_changed_text(tmp_path, valid_hash):
    archive = tmp_path / "standard-fixture.tar.xz"
    metadata = json.dumps({"Id": "fixture", "LicenseId": "MIT", "Copyright": "Fixture author"}).encode()
    with tarfile.open(archive, "w:xz") as output:
        member = tarfile.TarInfo("fixture/src/qt_attribution.json")
        member.size = len(metadata)
        output.addfile(member, BytesIO(metadata))
    text = "Original license fixture"
    source = {"text": text, "url": "https://example.invalid/MIT.txt",
              "sha256": hashlib.sha256(text.encode()).hexdigest() if valid_hash else "0" * 64}
    standard = {"LICENSES/MIT.txt": source}
    if not valid_hash:
        with pytest.raises(ValueError, match="hash mismatch"):
            notices.collect(archive, "fixture", "1", standard)
        return
    result = notices.collect(archive, "fixture", "1", standard)
    assert result["texts"]["LICENSES/MIT.txt"] == text
    assert result["external_text_sources"]["LICENSES/MIT.txt"]["url"] == source["url"]
