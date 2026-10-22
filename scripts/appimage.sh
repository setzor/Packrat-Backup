#!/usr/bin/env bash
# Build a portable Packrat Backup AppImage.
# Bundles the Python interpreter, the packrat package and its Python
# dependencies (PyQt6, keyring) into an AppDir, then uses linuxdeploy to
# deploy native library dependencies and produce the final AppImage.
# restic and rclone are intentionally NOT bundled; they must be installed
# on the host system, matching the DEB/RPM packaging behaviour.
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
BUILD_DIR="${REPO_ROOT}/build/appimage"
APPDIR="${BUILD_DIR}/AppDir"
OUTPUT_DIR="${OUTPUT_DIR:-${REPO_ROOT}/dist}"
APPID="io.github.setzor.PackratBackup"
LINUXDEPLOY_URL="https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage"

export APPIMAGE_EXTRACT_AND_RUN=1

VERSION=$(grep -m1 '^version' "${REPO_ROOT}/pyproject.toml" | sed 's/.*"\(.*\)"/\1/')
echo "Building Packrat Backup ${VERSION} AppImage..."

rm -rf "${BUILD_DIR}"
mkdir -p "${APPDIR}/usr/bin" "${OUTPUT_DIR}"

python3 -m venv "${BUILD_DIR}/venv"
# shellcheck disable=SC1091
source "${BUILD_DIR}/venv/bin/activate"
pip install --upgrade pip
# Install packrat and its dependencies into a clean target dir that is
# copied into the AppDir verbatim.
TARGET_SITE="${BUILD_DIR}/site-packages"
mkdir -p "${TARGET_SITE}"
pip install --target "${TARGET_SITE}" --no-compile "${REPO_ROOT}[keyring]"

PYBIN=$(readlink -f "$(command -v python3)")
PYVER=$("${PYBIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Bundling Python ${PYVER} from ${PYBIN}"

# Copy the interpreter into the AppDir
install -D -m 0755 "${PYBIN}" "${APPDIR}/usr/bin/python3"
shopt -s nullglob
PYLIB=(/usr/lib/x86_64-linux-gnu/libpython${PYVER}*.so.1.0
       /usr/lib*/libpython${PYVER}*.so.1.0)
shopt -u nullglob
for lib in "${PYLIB[@]}"; do
    mkdir -p "${APPDIR}/usr/lib"
    install -m 0755 "${lib}" "${APPDIR}/usr/lib/"
    break
done

# Copy the Python standard library into the AppDir
STDLIB=$("${BUILD_DIR}/venv/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["stdlib"])')
mkdir -p "${APPDIR}/usr/lib/python${PYVER}"
cp -a "${STDLIB}"/. "${APPDIR}/usr/lib/python${PYVER}/"
# A prefix install's stdlib dir can contain its own site-packages
# (e.g. /usr/local/lib/python3.12/site-packages) holding the build host's
# global packages; drop it and install only the app's dependencies below.
rm -rf "${APPDIR}/usr/lib/python${PYVER}/site-packages" 2>/dev/null || true
rm -f "${APPDIR}"/usr/lib/python${PYVER}/lib-dynload/_tkinter*.so 2>/dev/null || true
rm -rf "${APPDIR}"/usr/lib/python${PYVER}/tkinter 2>/dev/null || true

# Copy packrat's dependencies into the AppDir
mkdir -p "${APPDIR}/usr/lib/python${PYVER}/site-packages"
cp -a "${TARGET_SITE}"/. "${APPDIR}/usr/lib/python${PYVER}/site-packages/"
rm -rf "${APPDIR}"/usr/lib/python${PYVER}/site-packages/packrat/__pycache__ 2>/dev/null || true
find "${APPDIR}/usr/lib/python${PYVER}" -maxdepth 1 -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

# Prune PyQt6 modules packrat does not use (only QtCore/QtGui/QtWidgets/
# QtNetwork are imported); unused bindings reference Qt libs that are not
# shipped in the PyQt6 wheel and would break linuxdeploy dependency
# deployment while bloating the image.
PYQT_SITE="${APPDIR}/usr/lib/python${PYVER}/site-packages/PyQt6"
find "${PYQT_SITE}" -maxdepth 1 -name '*.so' ! -name 'QtCore*' ! -name 'QtGui*' \
    ! -name 'QtNetwork*' ! -name 'QtWidgets*' ! -name 'sip*' -exec rm -f {} + 2>/dev/null || true
QT_LIBS="${PYQT_SITE}"/Qt6/lib
if [ -d "${QT_LIBS}" ]; then
    # Prune Qt plugins packrat does not use; keep the platform, image
    # format, icon engine, style and TLS plugins a QtWidgets app needs.
    PLUGINS="${PYQT_SITE}"/Qt6/plugins
    if [ -d "${PLUGINS}" ]; then
        find "${PLUGINS}" -mindepth 1 -maxdepth 1 -type d \
            ! -name platforms ! -name imageformats ! -name iconengines \
            ! -name styles ! -name tls ! -name networkinformation \
            -exec rm -rf {} + 2>/dev/null || true
    fi
    # Compute the transitive closure of Qt6 libs needed by the four
    # PyQt6 bindings packrat imports, plus the platform plugins.
    rm -f "${QT_LIBS}"/libQt6OpenGL* 2>/dev/null || true
    KEEP="libQt6Core libQt6Gui libQt6Widgets libQt6Network libQt6DBus \
libQt6XcbQpa libQt6EglFSDeviceIntegration libQt6EglFsKmsSupport \
libQt6WaylandClient libQt6WlShellIntegration"
    CHANGED=1
    while [ "${CHANGED}" -eq 1 ]; do
        CHANGED=0
        for k in ${KEEP}; do
            f="${QT_LIBS}"/${k}.so.6
            [ -f "${f}" ] || continue
            for dep in $(LD_LIBRARY_PATH="${QT_LIBS}" ldd "${f}" 2>/dev/null | \
                    awk '/libQt6/ {print $1}' | sort -u); do
                base=$(basename "${dep}" .so.6 | sed 's/^lib//')
                case " ${KEEP} " in
                    *" ${base} "*) ;;
                    *) if [ -f "${QT_LIBS}/lib${base}.so.6" ]; then
                           KEEP="${KEEP} ${base}"
                           CHANGED=1
                       fi ;;
                esac
            done
        done
    done
    mkdir -p "${BUILD_DIR}"/qt-keep
    for k in ${KEEP}; do
        mv "${QT_LIBS}"/${k}.so* "${BUILD_DIR}"/qt-keep/ 2>/dev/null || true
    done
    for f in "${QT_LIBS}"/libicudata.so* "${QT_LIBS}"/libicui18n.so* \
             "${QT_LIBS}"/libicuuc.so*; do
        [ -f "$f" ] && mv "$f" "${BUILD_DIR}"/qt-keep/ 2>/dev/null || true
    done
    rm -rf "${QT_LIBS}"
    mv "${BUILD_DIR}"/qt-keep "${QT_LIBS}"
fi

# Entrypoint and desktop integration
cat > "${APPDIR}/usr/bin/packrat" <<'EOF'
#!/usr/bin/env bash
HERE=$(dirname "$(readlink -f "$0")")
export PYTHONHOME="${HERE}/.."
export LD_LIBRARY_PATH="${HERE}/../lib:${LD_LIBRARY_PATH}"
exec "${HERE}/python3" -m packrat "$@"
EOF
sed -i "s/PYVER_PLACEHOLDER/${PYVER}/" "${APPDIR}/usr/bin/packrat"
chmod +x "${APPDIR}/usr/bin/packrat"

cat > "${BUILD_DIR}/packrat.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Packrat Backup
GenericName=Backup Tool
Comment=Keep your files safe with encrypted backups to local folders, OneDrive or Google Drive
Exec=packrat
Icon=${APPID}
Terminal=false
Categories=Utility;FileTools;Archiving;
Keywords=backup;restic;rclone;onedrive;google;drive;plasma;kde;
SingleMainWindow=true
X-KDE-StartupNotify=true
StartupWMClass=packrat
EOF

# AppRun
cat > "${APPDIR}/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE=$(dirname "$(readlink -f "$0")")
export PYTHONHOME="${HERE}/usr"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/packrat" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

install -D -m 0644 "${REPO_ROOT}/icons/128x128/apps/${APPID}.png" \
    "${APPDIR}/usr/share/icons/hicolor/128x128/apps/${APPID}.png"
install -D -m 0644 "${REPO_ROOT}/icons/scalable/apps/${APPID}.svg" \
    "${APPDIR}/usr/share/icons/hicolor/scalable/apps/${APPID}.svg"
install -D -m 0644 "${REPO_ROOT}/${APPID}.desktop" \
    "${APPDIR}/usr/share/applications/${APPID}.desktop"
install -D -m 0644 "${REPO_ROOT}/${APPID}.metainfo.xml" \
    "${APPDIR}/usr/share/metainfo/${APPID}.metainfo.xml"

if [ ! -f "${BUILD_DIR}/linuxdeploy-x86_64.AppImage" ]; then
    echo "Downloading linuxdeploy..."
    curl -fsSL -o "${BUILD_DIR}/linuxdeploy-x86_64.AppImage" "${LINUXDEPLOY_URL}"
    chmod +x "${BUILD_DIR}/linuxdeploy-x86_64.AppImage"
fi

# shellcheck disable=SC2046
pushd "${BUILD_DIR}" >/dev/null
"${BUILD_DIR}/linuxdeploy-x86_64.AppImage" --appdir "${APPDIR}" \
    --desktop-file "${BUILD_DIR}/packrat.desktop" \
    --icon-file "${REPO_ROOT}/icons/scalable/apps/${APPID}.svg" \
    ${LINUXDEPLOY_EXTRA_ARGS:-} \
    --output appimage
popd >/dev/null

OUTPUT="${OUTPUT_DIR}/Packrat-Backup-${VERSION}-x86_64.AppImage"
mv "${BUILD_DIR}"/Packrat_Backup-x86_64.AppImage "${OUTPUT}"
echo "AppImage built: ${OUTPUT}"
