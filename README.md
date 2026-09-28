# Packrat Backup

> [!CAUTION]
> **This is a personal project, built for my own use.**
> It is provided as-is, with **no warranty of any kind**, express or implied.
> There is **no guarantee of data safety, integrity or recoverability**. Backup
> software can fail silently, and a backup you have not tested restoring is not
> a backup. **Use at your own risk** always verify your restores, and keep an
> independent copy of anything irreplaceable. You alone are responsible for any
> data loss or damage that may result from using this software.

A KDE Plasma/Qt native backup application with OneDrive/Google Drive support.
Easy to use and schedule, kinda bit like Déjà Dup, but Qt-er ;-)

Packrat wraps the [restic](https://restic.net/) backup engine, so every backup is
**incremental, deduplicated and encrypted end to end**. Cloud destinations are
handled through [rclone](https://rclone.org/), which speaks OneDrive, Google
Drive and many other providers.

## Features

- **Simple by default** a first-run wizard gets you to protected in four steps
  (folders → destination → password → schedule).
- **Encrypted everywhere** data is encrypted with a password stored in your
  system keyring (KWallet on Plasma) before it ever leaves the machine.
- **Local or cloud** back up to any local folder, or to OneDrive/Google Drive
  via any rclone remote.
- **Scheduled** daily or weekly automatic backups, with a system tray agent
  and a "Back up now" button for the impatient.
- **Restore browser** list snapshots (with the folders each one contains) and
  restore any of them to any folder.
- **Retention policy** Déjà Dup-like retention knobs (hourly/daily/weekly/
  monthly/yearly counts) applied via `restic forget --prune`.

## Requirements

- Python 3.9+ with PyQt6 (`pip install PyQt6`)
- `restic` (the backup engine)
- `rclone` (only needed for cloud destinations)

On Fedora:

```bash
sudo dnf install restic rclone python3-pyqt6 python3-keyring
```

On Debian/Ubuntu or KDE neon:

```bash
sudo apt install restic rclone python3-pyqt6 python3-keyring
```

## Running from source

```bash
pip install -e .
packrat            # or: python -m packrat
packrat --tray     # start minimised in the system tray
```

## Setting up OneDrive or Google Drive

Packrat relies on rclone remotes for cloud storage. Create one once:

```bash
rclone config       # choose "onedrive" or "drive" and follow the prompts
```

The remote then shows up in Packrat under **Storage → Cloud storage** (the
"Set up cloud storage…" button opens this wizard in a terminal for you).

## How it works

| Layer     | Role                                                   |
| --------- | ------------------------------------------------------ |
| `restic`  | Snapshots, deduplication, encryption, restore, prune  |
| `rclone`  | OneDrive/Google Drive (and 40+ other) storage backends |
| `Packrat` | Qt UI, first-run wizard, scheduler, tray agent, keyring storage |

Backups run as `restic backup --json` in a `QProcess`; progress is parsed from
restic's JSON status stream and shown live in the window and tray tooltip. The
repository password is passed to restic via its environment, never on the
command line.

## Development

```bash
pip install -e .[dev]
pytest              # unit + integration tests (restic/rclone optional)
ruff check packrat tests
```

The test-suite runs headless (`QT_QPA_PLATFORM=offscreen`) and will exercise a
real restic init/backup/restore roundtrip when restic is installed.

## Packaging bits

- Desktop entry: `org.packrat.Backup.desktop`
- AppStream metadata: `org.packrat.Backup.metainfo.xml`
- Icons: `icons/` (scalable SVG + 128px PNG)

## License

GPL-3.0-or-later see [LICENSE](LICENSE).

---

<p align="center">
  <img src="docs/mascot-options/option-1-kawaii.svg" width="160" alt="Pakkie the Packrat, the Packrat Backup mascot"/>
  <br/>
  <em>Pakkie the Packrat says: keep your treasures safe. 🧺</em>
</p>
