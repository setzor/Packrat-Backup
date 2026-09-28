# Packrat Backup

A KDE Plasma/Qt native backup application with OneDrive/Google Drive support.
Easy to use and schedule, a bit like Déjà Dup.

Packrat wraps the [restic](https://restic.net/) backup engine, so every backup is
**incremental, deduplicated and encrypted end to end**. Cloud destinations are
handled through [rclone](https://rclone.org/), which speaks OneDrive, Google
Drive and many other providers.

## Features

- **Simple by default** — a first-run wizard gets you to protected in four steps
  (folders → destination → password → schedule).
- **Encrypted everywhere** — data is encrypted with a password stored in your
  system keyring (KWallet on Plasma) before it ever leaves the machine.
- **Local or cloud** — back up to any local folder, or to OneDrive/Google Drive
  via any rclone remote.
- **Scheduled** — daily or weekly automatic backups, with a system tray agent
  and a "Back up now" button for the impatient.
- **Restore browser** — list snapshots and restore any of them to any folder.
- **Retention policy** — Déjà Dup-like retention knobs (hourly/daily/weekly/
  monthly/yearly counts) applied via `restic forget --prune`.

## Requirements

- Python 3.9+ with PyQt6 (`pip install PyQt6`)
- `restic` (the backup engine)
- `rclone` (only needed for cloud destinations)

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
rclone config          # choose "onedrive" or "drive" and follow the prompts
```

The remote then shows up in Packrat under **Storage → Cloud storage**.

## How it works

| Layer      | Role                                                            |
| ---------- | --------------------------------------------------------------- |
| `restic`   | Snapshots, deduplication, encryption, restore, prune            |
| `rclone`   | OneDrive/Google Drive (and 40+ other) storage backends           |
| `Packrat`  | Qt UI, first-run wizard, scheduler, tray agent, keyring storage |

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
- Icon: `icons/128x128/apps/org.packrat.Backup.png` (placeholder art for now)

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).
