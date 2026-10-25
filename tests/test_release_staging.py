import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("stage_preview", Path(__file__).parents[1] / "scripts/stage_preview.py")
staging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(staging)


@pytest.mark.parametrize("change", ["published", "failed", "wrong_commit", "wrong_workflow"])
def test_staging_rejects_published_releases_and_unverified_sources(change):
    run = {"conclusion": "success", "head_branch": "main", "head_sha": "tested-commit",
           "path": ".github/workflows/native.yml"}
    release = {"draft": True, "prerelease": True, "target_commitish": "tested-commit"}
    staging.validate_source(run, release)
    if change == "published":
        release["draft"] = False
    elif change == "failed":
        run["conclusion"] = "failure"
    elif change == "wrong_commit":
        release["target_commitish"] = "different-commit"
    else:
        run["path"] = ".github/workflows/other.yml"
    with pytest.raises(ValueError):
        staging.validate_source(run, release)
