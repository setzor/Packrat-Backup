# Packrat Backup

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
  restore any of them to any folder — or just the individual files and folders
  you need. Repeat visits open instantly thanks to a contents cache, and new
  snapshots are pre-cached in the background after each backup.
- **Stop and clean up** stop a running backup and automatically remove the
  leftover data from interrupted runs.
- **Change detection** Packrat watches how much of your data changed in each
  backup and warns loudly when a run looks like ransomware encryption or an
  accidental mass edit.
- **Verified restores** optionally re-read a sample of the data after each
  backup to prove it restorable, with the result shown in the History page.
- **Backup preview** see how many files the next backup would upload and how
  big it would be, before running it.
- **Backup history** a History page records every backup, restore, verify and
  cleanup run.
- **Retention policy** Déjà Dup-like retention knobs (hourly/daily/weekly/
  monthly/yearly counts) applied via `restic forget --prune`.

## Installing

Grab the latest [release](https://github.com/setzor/Packrat-Backup/releases) —
RPM packages for Fedora and DEB packages for Debian/Ubuntu are built and tested
in CI:

```bash
# Fedora
sudo dnf install ./packrat-0.3.0-1.fc44.x86_64.rpm

# Debian / Ubuntu
sudo apt install ./packrat_0.3.0-1_all.deb
```

The packages depend on `restic` and `python3-pyqt6` (and recommend `rclone`
and `python3-keyring`), so your package manager pulls those in automatically.

## Requirements

- Python 3.9+ with PyQt6
- `restic` (the backup engine)
- `rclone` (only needed for cloud destinations)

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

## Packaging

Packrat ships as both RPM and DEB, built in CI (Fedora 44 and Debian 13
containers) on every push:

- Desktop entry: `org.packrat.Backup.desktop`
- AppStream metadata: `org.packrat.Backup.metainfo.xml`
- RPM spec: `packrat.spec`
- Debian packaging: `debian/`
- Icons: `icons/` (scalable SVG + 128px PNG)

## License

GPL-3.0-or-later see [LICENSE](LICENSE).

---

<p align="center">
  <img src="docs/mascot-options/option-1-kawaii.svg" width="160" alt="Pakkie the Packrat, the Packrat Backup mascot"/>
  <br/>
  <em>Pakkie the Packrat says: keep your treasures safe. 🧺</em>
</p>
