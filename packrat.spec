Name:           packrat
Version:        0.3.0
Release:        1%{?dist}
Summary:        A KDE Plasma/Qt native backup application with OneDrive/Google Drive support
Packager:       setzor <setzor@users.noreply.github.com>
Group:          Applications/System

License:        GPL-3.0-or-later
URL:            https://github.com/setzor/Packrat-Backup
Source0:        https://github.com/setzor/Packrat-Backup/archive/refs/tags/v%{version}/%{name}-%{version}.tar.gz
BuildArch:      x86_64
%define debug_package %{nil}

BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-setuptools
BuildRequires:  desktop-file-utils
BuildRequires:  libappstream-glib

Requires:       python3-pyqt6
Requires:       restic
Recommends:     rclone
Recommends:     python3-keyring

%description
Packrat Backup is a friendly, Qt-native backup application for the KDE
Plasma desktop, in the spirit of Deja Dup. It wraps the restic engine so
every backup is deduplicated, incremental and encrypted end to end.

Backups can be stored in a local folder or on OneDrive and Google Drive
through rclone. A built-in scheduler runs backups daily or weekly, and
a system tray agent keeps an eye on things in the background.


%prep
%autosetup -n Packrat-Backup-%{version}


%build
%pyproject_wheel


%install
%pyproject_install

# Desktop file
install -D -m 0644 io.github.setzor.PackratBackup.desktop \
    %{buildroot}%{_datadir}/applications/io.github.setzor.PackratBackup.desktop

# AppStream metainfo
install -D -m 0644 io.github.setzor.PackratBackup.metainfo.xml \
    %{buildroot}%{_metainfodir}/io.github.setzor.PackratBackup.metainfo.xml

# Icon (mascot SVG from the About page, named after the app id)
install -D -m 0644 packrat/assets/packrat-mascot.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/io.github.setzor.PackratBackup.svg


%check
desktop-file-validate %{buildroot}%{_datadir}/applications/io.github.setzor.PackratBackup.desktop
appstream-util validate-relax %{buildroot}%{_metainfodir}/io.github.setzor.PackratBackup.metainfo.xml


%files
%license LICENSE
%doc README.md
%{python3_sitelib}/packrat/
%{python3_sitelib}/packrat-%{version}.dist-info/
%{_bindir}/packrat
%{_datadir}/applications/io.github.setzor.PackratBackup.desktop
%{_metainfodir}/io.github.setzor.PackratBackup.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/io.github.setzor.PackratBackup.svg


%changelog
* Sat Oct 10 2026 Packrat Backup contributors <noreply@github.com> - 0.3.0-1
- Add snapshot contents cache: repeat and pre-cached snapshot browsing is instant (issue #81)
- Add background pre-caching of new snapshot contents after each backup, with a Preferences toggle
- Add a Refresh button to the snapshot browser to re-list from the destination
- Add stop for running backups with automatic cleanup of interrupted runs (issue #63)
- Add scheduled auto-prune, rclone backend tuning and restic v2 repositories (issue #64)
- Add live progress during backup estimates and while listing snapshot contents
- Add Debian packaging with a DEB CI workflow
- Fix snapshot listings routed to the wrong browser dialog or cache entry
- Fix stale-lock integrity checks with unlock-and-retry
- Fix partial backups (exit 3) reported as failures despite a saved snapshot
- Fix nanosecond snapshot timestamps breaking Python 3.10
- Fix cloud progress showing disk-speed-based ETAs
- Fix rclone serve restic failing on unknown --dir-cache-time flag
* Sun Oct 04 2026 Packrat Backup contributors <noreply@github.com> - 0.2.0-1
- Add change detection: warn when a backup shows mass-change patterns (issue #29 stage 1)
- Add Overview "Change check" tile, red badge and urgent notification on suspicious runs
- Add change detection on/off and threshold settings to Preferences
- Add per-file and per-folder restore from the snapshot browser (issue #16)
- Add backup preview with dry-run size estimate (issue #19)
- Add verified restores: post-backup restorability proof (issue #28)
- Show which snapshots were verified on the History page
- Fix Overview progress bar flickering between spinner and percent during backups
- Fix rclone repository probing attempting init with an invalid location (issue #43)
- Fix weekly catch-up missing schedules after absences longer than 8 days (issue #44)
- Fix settings lists not round-tripping entries containing commas (issue #45)

* Thu Oct 01 2026 Packrat Backup contributors <noreply@github.com> - 0.1.2-1
- Guard all-zero retention policy so prune can never delete every snapshot
- Wire restic QProcess errorOccurred so a failed launch no longer leaves the UI stuck
- Add backup history page and persistent schedule pause setting
- Add retention policy UI on Schedule page with auto-prune after backups
- Cache Restore page snapshots per refresh interval
- Fix page order mismatch in nav stack and spurious save during Preferences load
- Fix Clean Up button not resetting after cleanup finishes
* Mon Sep 28 2026 Packrat Backup contributors <noreply@github.com> - 0.1.1-1
- Fix Restore page Refresh crash when a restic operation is already running
- Catch restic errors during first-run wizard repository init
- Use Pakkie mascot for the tray icon and set an explicit window icon
- Fix RPM metadata: python3-pyqt6 dependency, Packager, SPDX license

* Mon Sep 28 2026 Packrat Backup contributors <noreply@github.com> - 0.1.0-1
- Initial RPM package
