# Presenteriyaki

A minimalist PDF presentation app for macOS and Windows.

Show slides on one screen while keeping speaker notes, the next slide and a
timer on the other. Use a single screen to rehearse.

![Presenter window with slides, notes, timer and thumbnails](docs/images/presenter.png)

## Features

- Presenter and audience windows with fullscreen and display switching
- Speaker notes, slide thumbnails and a presentation timer
- Drawing, whiteboard, laser pointer and spotlight
- Video, audio and LaTeX animations
- Optional camera overlay and web content

## Install

Presenteriyaki runs as a standalone app; Python is included.

- **macOS:** download the [Apple Silicon](https://github.com/pku-lemonade/presenteriyaki/releases/download/v0.4.0/Presenteriyaki-0.4.0-macos-arm64.dmg)
  or [Intel](https://github.com/pku-lemonade/presenteriyaki/releases/download/v0.4.0/Presenteriyaki-0.4.0-macos-x86_64.dmg)
  disk image and drag Presenteriyaki to Applications.
- **Windows:** run the [x64 installer](https://github.com/pku-lemonade/presenteriyaki/releases/download/v0.4.0/Presenteriyaki-0.4.0-windows-x64-setup.exe),
  then open Presenteriyaki from Start. Setup downloads Microsoft WebView2 if
  needed, so an internet connection may be required during installation.

These are **unsigned preview builds**. On macOS, after the first blocked launch,
choose **System Settings → Privacy & Security → Open Anyway**.
Windows may show a SmartScreen warning with **More info → Run anyway**.
Quit the app before updating an existing installation.

See [release notes and checksums](https://github.com/pku-lemonade/presenteriyaki/releases/tag/v0.4.0).
Developers can [build from source](CONTRIBUTING.md#build-the-app).

## Getting started

Open Presenteriyaki and drop in a PDF, or choose **File → Open PDF**. Use the arrow
keys to change slides, **F5** for fullscreen and **?** for keyboard help.

See the [user guide](docs/USER_GUIDE.md) for notes, drawing and media controls.

## Development

Built with Python and Qt/PySide. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup,
testing and packaging.

## License

[MIT](LICENSE). Bundled dependencies retain their own licenses; see the
[distribution notes](docs/DISTRIBUTION.md).
