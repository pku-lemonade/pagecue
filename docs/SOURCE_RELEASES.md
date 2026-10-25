# Source versions and update checks

PageCue currently distributes source and an agent-oriented build/install runbook.
Versioned Git tags provide reproducible source checkpoints. They do not imply a
public binary release, completed hardware acceptance or notarization. The current
0.x application remains a development preview; consult FEATURES.md for coverage.

The update checker first asks GitHub for the latest non-prerelease release. If
GitHub returns 404 because no release exists, it reads the repository's 100 most
recent source tags and chooses the highest recognizable version. Prerelease/dev
tags and unrelated experiment tags are ignored. Source updates link to the
canonical versioned tree in this repository. Network/rate-limit errors remain
visible and do not masquerade as an up-to-date result. Closing PageCue cancels
both the initial request and any pending source-tag lookup.

Source tags are listed at <https://github.com/pku-lemonade/pagecue/tags>.
To install a particular published version, clone with `git clone --branch TAG
https://github.com/pku-lemonade/pagecue.git`, substituting the published tag name,
then follow README.md and AGENTS.md in that checkout.

## Maintainer procedure

1. Keep the versions in `pyproject.toml` and `src/pagecue/__init__.py` consistent.
2. Commit the exact source checkpoint and require the native CI workflow to pass
   on Windows x64, Mac arm64 and Mac Intel, including packaged execution.
3. Create an annotated `vVERSION` tag on that verified commit and push that tag.
   Do not move or replace a published version tag.
4. Verify the public tags API and the real Qt update checker for both an older
   version and the current version. Record the tag's target commit and CI run.
5. Future packaged releases additionally need the public-binary notice/source and
   signing checks in DISTRIBUTION.md. A source tag does not waive those checks.

The first planned checkpoint is `v0.1.0`; publication and its live-channel result
will be recorded after native CI verifies the source-tag updater.
