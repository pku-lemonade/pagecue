import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import tarfile

import pytest


def script(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_webengine_snapshot_preserves_notice_text_without_scripts(tmp_path):
    module = script("collect_webengine_notices")
    index = "<title>Qt WebEngine 6.140.0</title><a href='qtwebengine-3rdparty-fixture.html'>Fixture</a>"
    detail = ("<title>Fixture | Qt WebEngine 6.140.0</title><h1>Fixture &amp; friends</h1>"
              "<div class='descr'><p>Copyright: original fixture authors.</p>"
              "<pre>Original license text.\nA &amp; B &lt; C. &amp;quot;License&amp;quot;</pre>"
              "<script>unwanted_script()</script></div>")
    (tmp_path / "index.html").write_text(index)
    (tmp_path / "qtwebengine-3rdparty-fixture.html").write_text(detail)
    result = module.collect("https://example.invalid/index.html", "6.140.0", tmp_path)
    assert result["components"][0]["attribution"]["Name"] == "Fixture & friends"
    text = result["texts"]["qtwebengine-3rdparty-fixture.txt"]
    assert "Copyright: original fixture authors." in text and "A & B < C." in text
    assert "unwanted_script" not in text
    assert '"License"' in text and "&quot;" not in text
    assert result["index_sha256"] == hashlib.sha256(index.encode()).hexdigest()


@pytest.mark.parametrize("valid_checksum", [True, False])
def test_crate_notice_collection_checks_lockfile_integrity(tmp_path, valid_checksum):
    module = script("collect_rust_notices")
    cache = tmp_path / "cache"
    cache.mkdir()
    archive = cache / "original-fixture-1.0.0.crate"
    license_text = b"Copyright: original fixture authors. Original test terms."
    with tarfile.open(archive, "w:gz") as output:
        info = tarfile.TarInfo("original-fixture-1.0.0/LICENSE")
        info.size = len(license_text)
        output.addfile(info, BytesIO(license_text))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest() if valid_checksum else "0" * 64
    lock = tmp_path / "Cargo.lock"
    lock.write_text('version = 4\n[[package]]\nname = "original-fixture"\nversion = "1.0.0"\n'
                    'source = "registry+https://github.com/rust-lang/crates.io-index"\n'
                    f'checksum = "{digest}"\n')
    if not valid_checksum:
        with pytest.raises(ValueError, match="Cargo checksum mismatch"):
            module.collect(lock, cache)
        return
    result = module.collect(lock, cache)
    assert result["crates"][0]["texts"]["LICENSE"] == license_text.decode()


def test_notice_html_escapes_upstream_text_and_links_local_pages(tmp_path):
    module = script("render_notices")
    folder = tmp_path / "components"
    folder.mkdir()
    notice = {"module": "fixture", "version": "1", "source_url": "https://example.invalid/source",
              "scope": "Original fixture", "components": [{"attribution": {"Name": "A & B", "Copyright": "<script>"},
              "text_files": ["LICENSE"]}], "texts": {"LICENSE": "Original terms: A < B & C."}}
    (folder / "fixture.json").write_text(json.dumps(notice))
    module.render(tmp_path)
    page = (folder / "fixture.html").read_text()
    assert "&lt;script&gt;" in page and "<script>" not in page
    assert "A &lt; B &amp; C." in page
    assert "components/fixture.html" in (tmp_path / "index.html").read_text()
