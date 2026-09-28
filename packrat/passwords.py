"""Keyring-backed password storage with a base64 fallback file.

The backup password is sensitive: prefer the system keyring (KWallet on
Plasma). When no keyring is available the password is base64-obfuscated
into a user-readable-only file; this hides it from casual viewing but is
NOT encryption, so installing a keyring backend is strongly recommended.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Optional

from .paths import config_dir

log = logging.getLogger(__name__)

_SERVICE = "Packrat Backup"
_USER = "restic-password"


def _keyring_available() -> bool:
    try:
        import keyring  # type: ignore

        keyring.get_keyring()
        return True
    except Exception:
        return False


def _fallback_path():
    return config_dir() / "password.b64"


def _obfuscate(password: str) -> str:
    return base64.b64encode(password.encode("utf-8")).decode("ascii")


def _deobfuscate(token: str) -> str:
    return base64.b64decode(token.encode("ascii")).decode("utf-8")


def store_password(password: str) -> bool:
    """Persist the repository password. Returns True on success."""
    if not password:
        return False
    if _keyring_available():
        try:
            import keyring  # type: ignore

            keyring.set_password(_SERVICE, _USER, password)
            return True
        except Exception as exc:
            log.warning("Keyring write failed (%s); using fallback file", exc)
    try:
        path = _fallback_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_obfuscate(password) + "\n")
        os.chmod(path, 0o600)
        return True
    except OSError as exc:
        log.error("Failed to store password fallback: %s", exc)
        return False


def load_password() -> Optional[str]:
    """Retrieve the stored repository password, if any."""
    if _keyring_available():
        try:
            import keyring  # type: ignore

            value = keyring.get_password(_SERVICE, _USER)
            if value:
                return value
        except Exception as exc:
            log.warning("Keyring read failed (%s)", exc)
    try:
        path = _fallback_path()
        if path.exists():
            token = path.read_text().strip()
            if token:
                return _deobfuscate(token)
    except (OSError, ValueError) as exc:
        log.error("Failed to read password fallback: %s", exc)
    return None


def forget_password() -> None:
    if _keyring_available():
        try:
            import keyring  # type: ignore

            keyring.delete_password(_SERVICE, _USER)
        except Exception:
            pass
    try:
        path = _fallback_path()
        if path.exists():
            path.unlink()
    except OSError:
        pass


def has_stored_password() -> bool:
    return load_password() is not None


def validate_password(password: str) -> str:
    """Return an error message, or an empty string when acceptable."""
    if not password:
        return "Please enter a password."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    return ""
