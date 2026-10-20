import subprocess

from packrat.guards import GuardBlock, _run, check_guards, on_battery, on_metered_connection


def test_run_missing_command_returns_none():
    assert _run(["packrat-definitely-missing-binary-xyz"]) is None


def test_run_timeout_returns_none(monkeypatch):
    def slow(*a, **k):
        raise subprocess.TimeoutExpired(cmd=["x"], timeout=5)

    monkeypatch.setattr(subprocess, "run", slow)
    assert _run(["true"]) is None


def test_on_battery_without_tools(monkeypatch):
    monkeypatch.setattr("packrat.guards._run", lambda cmd: None)
    assert on_battery() is False


def test_on_battery_sysfs(monkeypatch):
    def fake_run(cmd):
        if cmd[0] == "cat":
            return "0\n0\n"
        return None

    monkeypatch.setattr("packrat.guards._run", fake_run)
    assert on_battery() is True

    def fake_run_ac(cmd):
        if cmd[0] == "cat":
            return "1\n"
        return None

    monkeypatch.setattr("packrat.guards._run", fake_run_ac)
    assert on_battery() is False


def test_on_battery_upower_dump(monkeypatch):
    def fake_run(cmd):
        if cmd[:1] == ["upower"] and "-d" in cmd:
            return "Device: /org/freedesktop/UPower/devices/battery_BAT0\n    on-battery: yes\n"
        return None

    monkeypatch.setattr("packrat.guards._run", fake_run)
    assert on_battery() is True


def test_on_metered_connection(monkeypatch):
    monkeypatch.setattr(
        "packrat.guards._run",
        lambda cmd: "eth0:yes\nwlan0:no\n" if cmd[0] == "nmcli" else None,
    )
    assert on_metered_connection() is True

    monkeypatch.setattr(
        "packrat.guards._run",
        lambda cmd: "eth0:no\nwlan0:unknown\n" if cmd[0] == "nmcli" else None,
    )
    assert on_metered_connection() is False

    monkeypatch.setattr("packrat.guards._run", lambda cmd: None)
    assert on_metered_connection() is False


def test_check_guards_none_when_disabled(monkeypatch):
    monkeypatch.setattr("packrat.guards.on_battery", lambda: True)
    monkeypatch.setattr("packrat.guards.on_metered_connection", lambda: True)
    assert check_guards(False, False) is None


def test_check_guards_battery(monkeypatch):
    monkeypatch.setattr("packrat.guards.on_battery", lambda: True)
    block = check_guards(True, False)
    assert block is not None
    assert "battery" in str(block)


def test_check_guards_metered(monkeypatch):
    monkeypatch.setattr("packrat.guards.on_battery", lambda: False)
    monkeypatch.setattr("packrat.guards.on_metered_connection", lambda: True)
    block = check_guards(True, True)
    assert block is not None
    assert "metered" in str(block)


def test_guard_block_str():
    assert "battery" in str(GuardBlock("battery", "detail"))
