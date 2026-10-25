# Source versions and update checks

Presenteriyaki (formerly PageCue) distributes source and an agent-oriented build/install runbook.
Versioned Git tags provide reproducible source checkpoints. They do not imply a
public binary release, completed hardware acceptance or notarization. The current
0.x application remains a development preview; consult FEATURES.md for coverage.

The update checker first asks GitHub for the latest non-prerelease release. If
GitHub returns 404 because no release exists, it reads the repository's 100 most
recent source tags and chooses the highest recognizable version. Prerelease/dev
tags and unrelated experiment tags are ignored. Source updates link to the
canonical versioned tree in this repository. Network/rate-limit errors remain
visible and do not masquerade as an up-to-date result. Closing Presenteriyaki cancels
both the initial request and any pending source-tag lookup.

Source tags are listed at <https://github.com/pku-lemonade/presenteriyaki/tags>.
To install a particular published version, clone with `git clone --branch TAG
https://github.com/pku-lemonade/presenteriyaki.git`, substituting the published tag name,
then follow README.md and AGENTS.md in that checkout.

## Maintainer procedure

1. Keep the versions in `pyproject.toml` and `src/presenteriyaki/__init__.py` consistent.
2. Commit the exact source checkpoint and require the native CI workflow to pass
   on Windows x64, Mac arm64 and Mac Intel, including packaged execution.
3. Create an annotated `vVERSION` tag on that verified commit and push that tag.
   Do not move or replace a published version tag.
4. Verify the public tags API and the real Qt update checker for both an older
   version and the current version. Record the tag's target commit and CI run.
5. Future packaged releases additionally need the public-binary notice/source and
   signing checks in DISTRIBUTION.md. A source tag does not waive those checks.

## Published checkpoints

### Presenteriyaki v0.2.0

[`v0.2.0`](https://github.com/pku-lemonade/presenteriyaki/tree/v0.2.0) is the first
Presenteriyaki source preview, at `0003fa8ea97b51688bfdee6eb4151a60fdd6d045`.
[CI run 40196504437](https://github.com/pku-lemonade/presenteriyaki/actions/runs/40196504437)
passes 97 tests, 16 native interaction checks, and packaged execution plus
install/update/removal on Windows x64 and both Mac architectures. Its annotated
tag object is `080e620efc95f0c3be1f327b34032f513fe7a2f0`.

The live Qt checker finds 0.2.0 through both the current repository endpoint and
the old PageCue endpoint's redirect. It reports an update for installed 0.1.0 and
no newer version for 0.2.0. All results link to the canonical Presenteriyaki tag.
Transport evidence is under `qa/presenteriyaki-source-release-live.json`.
This publishes source only; the remaining acceptance gates are in
COMPLETION_AUDIT.md. Existing PageCue preferences, command aliases and the earlier
immutable tag are retained.

### Earlier PageCue v0.1.0

[`v0.1.0`](https://github.com/pku-lemonade/presenteriyaki/tree/v0.1.0) is a development
source preview at commit `8a5138aa3d48deae4844bcb4b5698fcc1fd60a90`.
[CI run 40183195653](https://github.com/pku-lemonade/presenteriyaki/actions/runs/40183195653)
passed 85 tests, six native interaction checks and packaged execution on all three
targets. The annotated tag object is `b0d435564d5bae457918e4a10f3954261036c908`.

The live Qt checker followed GitHub's missing-release response to the public tag
list and found 0.1.0. With an older installed-version value (0.0.0), it reported an
update; with 0.1.0, it reported no newer version. Both results linked to the
canonical tagged source tree. Local transport evidence is under
`qa/source-release-live/result.json`. This verifies the source update channel;
actual OS notification delivery remains a separate acceptance item.
