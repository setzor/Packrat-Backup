import stat
import textwrap

from packrat.restic import Restic


def _fake_restable(tmp_path, body):
    path = tmp_path / "fake-restic"
    path.write_text(textwrap.dedent(body).lstrip())
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def test_restic_run_preserves_flags_and_sets_password_env(tmp_path, monkeypatch):
    binary = _fake_restable(
        tmp_path,
        """
        #!/bin/sh
        echo "ARGS: $@"
        echo "RESTIC_PASSWORD: $RESTIC_PASSWORD"
        """,
    )
    monkeypatch.setenv("PACKRAT_RESTIC_BINARY", binary)
    ok, stdout, _ = Restic.run(
        ["--repo", "rclone:myremote:packrat-backups", "cat", "config"],
        timeout=10,
        password="s3cret",
    )
    assert ok is True
    assert "ARGS: --repo rclone:myremote:packrat-backups cat config" in stdout
    assert "RESTIC_PASSWORD: s3cret" in stdout


def test_restic_run_without_password_clears_inherited_env(tmp_path, monkeypatch):
    binary = _fake_restable(
        tmp_path,
        """
        #!/bin/sh
        echo "RESTIC_PASSWORD: ${RESTIC_PASSWORD:-unset}"
        """,
    )
    monkeypatch.setenv("PACKRAT_RESTIC_BINARY", binary)
    monkeypatch.setenv("RESTIC_PASSWORD", "leaked-from-parent")
    ok, stdout, _ = Restic.run(["cat", "config"], timeout=10)
    assert ok is True
    assert "RESTIC_PASSWORD: unset" in stdout
