import hashlib
import json
from pathlib import Path


def test_committed_fixtures_match_original_sources_and_generator():
    root = Path(__file__).parents[1]
    manifest = json.loads((root / "tests/fixtures/generated/manifest.json").read_text())
    for relative, expected in manifest["sha256"].items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected, (
            f"Changed fixture input/output {relative}; run scripts/generate_fixtures.py")
