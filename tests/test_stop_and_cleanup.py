def test_close_event_survives_handler_exception(qapp, monkeypatch, tmp_path):
    """A failing close handler must not crash the app (SEGV report, #63 era)."""
    from packrat.main import MainWindow
    from packrat.settings import Settings

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    settings = Settings()
    settings.first_run_done = True
    settings.folders = [str(tmp_path)]
    settings.backend_cfg.local_path = str(tmp_path / "backups")
    window = MainWindow(settings)

    def explode():
        raise RuntimeError("boom in close path")

    monkeypatch.setattr(window, "_handle_close", explode)
    accepted = []
    event = type(
        "FakeEvent", (), {"accept": lambda s: accepted.append(True), "ignore": lambda s: None}
    )()
    try:
        window.closeEvent(event)
        assert accepted == [True]
    finally:
        window.tray.hide()
        window.close()


def test_close_event_normal_paths(qapp, tmp_path):
    from packrat.main import MainWindow
    from packrat.settings import Settings

    monkey_env = tmp_path / "config"
    import os

    os.environ["XDG_CONFIG_HOME"] = str(monkey_env)
    settings = Settings()
    settings.first_run_done = True
    settings.folders = [str(tmp_path)]
    settings.backend_cfg.local_path = str(tmp_path / "backups")
    window = MainWindow(settings)
    ignored = []
    event = type("E", (), {"accept": lambda s: None, "ignore": lambda s: ignored.append(True)})()
    settings.close_to_tray = True
    window.closeEvent(event)
    assert ignored == [True]
    settings.close_to_tray = False
    accepted = []
    event2 = type("E", (), {"accept": lambda s: accepted.append(True), "ignore": lambda s: None})()
    window.closeEvent(event2)
    assert accepted == [True]
    window.tray.hide()
