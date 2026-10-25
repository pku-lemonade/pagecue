# Dependency notice snapshots

These files retain upstream attribution metadata and license/copyright texts.
They are copied into native packages and rendered as a local index available
through **Help → Third-party notices**. The inventories include optional,
platform-specific and build-time dependencies; `payload.json` records the Qt
libraries actually packaged.

- Qt module inventories come from release source archives verified against Qt's
  published SHA-256 files. Refresh with `scripts/collect_qt_source_notices.py`.
- WebEngine notices come from its published licensing documentation. The snapshot
  keeps source URLs and HTML hashes. Refresh with `scripts/collect_webengine_notices.py`.
- Cryptography's Rust notices follow its upstream Cargo.lock, with each registry
  archive checked against the lockfile checksum. Refresh with
  `scripts/collect_rust_notices.py`; the snapshot records the source lockfile URL.

Upstream texts retain their licenses. Qt attribution metadata is copyright
The Qt Company Ltd.; applicable Qt license texts are included in the inventories.
The package builder checks the snapshot versions against the installed runtimes.
