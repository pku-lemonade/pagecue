# Presenteriyaki rename compatibility

The user chose **Presenteriyaki**, combining presenTER and TERiyaki through the
shared “TER”. PageCue was the development name. Version 0.2.0 introduces the name;
the immutable v0.1.0 source tag and its historical evidence still use PageCue.

| Surface | Current name | Compatibility |
|---|---|---|
| Repository | `pku-lemonade/presenteriyaki` | GitHub redirects the old repository URL after the rename |
| Python project/module | `presenteriyaki` | `presenteriyaki` and `pagecue` console commands both start the app |
| macOS application | `Presenteriyaki.app` | Stable bundle identity `org.pku-lemonade.pagecue`; reuse of its notification permission was observed live |
| Windows application | `Presenteriyaki/Presenteriyaki.exe` | `PageCue.exe` is also included for existing shortcuts |
| Default Start Menu link | `Presenteriyaki.lnk` | Existing PageCue links are left intact unless explicitly updating/removing the legacy installation |
| Preferences and app data | Existing PageCue store | Qt's internal application/organization names stay `PageCue`; its display name is `Presenteriyaki` |

No migration copies or deletes presentation files, notes, camera settings or recent
positions. A fixture test writes preferences under the old namespace, opens the
renamed app and checks its page, camera appearance and update preference. The
stable internal identifier is intentional; do not change it in a cosmetic rename.

## Existing installations

The default installer creates `~/Applications/Presenteriyaki.app` on macOS or
`%LOCALAPPDATA%\Programs\Presenteriyaki` on Windows. An existing PageCue application
at the old default location remains available. Both names use the same preferences.
Close the application being updated before replacing its bundle/directory.

For an explicit update of the old location, add `--legacy-pagecue` to the install
command. Windows uses the compatibility launcher so an old PageCue shortcut
continues working. The installer also supports:

```sh
uv run python scripts/install_app.py --legacy-pagecue --check
uv run python scripts/install_app.py --legacy-pagecue --uninstall
```

Add `--destination PATH` for a custom old location. Identity checks, staging and
rollback still apply. At the default destinations, removing the legacy app leaves
the new installation intact. Uninstall leaves shared
preferences and documents intact. Default PDF associations remain unchanged.

Existing checkout directories do not need to move. Original generated fixtures
and historical captures can retain their PageCue labels; their provenance and
checksums remain useful evidence rather than being regenerated for branding.

The renamed Mac application menu displays Presenteriyaki. A renamed test alert
was delivered without another permission prompt, while macOS still labeled the
notification sender PageCue. This cached OS label belongs to the same application
identity. The native click could not be verified before the transient banner
disappeared; that check remains separate from delivery.
