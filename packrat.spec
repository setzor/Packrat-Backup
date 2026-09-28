Name:           packrat
Version:        0.1.0
Release:        1%{?dist}
Summary:        A KDE Plasma/Qt native backup application with OneDrive/Google Drive support

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

Requires:       python3-qt6
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
install -D -m 0644 org.packrat.Backup.desktop \
    %{buildroot}%{_datadir}/applications/org.packrat.Backup.desktop

# AppStream metainfo
install -D -m 0644 org.packrat.Backup.metainfo.xml \
    %{buildroot}%{_metainfodir}/org.packrat.Backup.metainfo.xml

# Icon (mascot SVG from the About page, named after the app id)
install -D -m 0644 packrat/assets/packrat-mascot.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/org.packrat.Backup.svg


%check
desktop-file-validate %{buildroot}%{_datadir}/applications/org.packrat.Backup.desktop
appstream-util validate-relax %{buildroot}%{_metainfodir}/org.packrat.Backup.metainfo.xml


%files
%license LICENSE
%doc README.md
%{python3_sitelib}/packrat/
%{python3_sitelib}/packrat-%{version}.dist-info/
%{_bindir}/packrat
%{_datadir}/applications/org.packrat.Backup.desktop
%{_metainfodir}/org.packrat.Backup.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/org.packrat.Backup.svg


%changelog
* Mon Sep 28 2026 Packrat Backup contributors <noreply@github.com> - 0.1.0-1
- Initial RPM package
