import pytest

from conxml import startup


def test_run_gui_propagates_successful_exit_without_startup_error(monkeypatch):
    dialogs = []
    monkeypatch.setattr(startup.messagebox, "showerror", lambda *args, **kwargs: dialogs.append(args))

    def exit_normally():
        raise SystemExit(0)

    with pytest.raises(SystemExit) as result:
        startup.run_gui(exit_normally)

    assert result.value.code == 0
    assert dialogs == []


def test_run_gui_still_reports_unexpected_exception(monkeypatch, tmp_path):
    dialogs = []
    monkeypatch.setenv("CONXML_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(startup.messagebox, "showerror", lambda *args, **kwargs: dialogs.append(args))

    def fail_to_start():
        raise RuntimeError("fallo real de arranque")

    with pytest.raises(RuntimeError, match="fallo real"):
        startup.run_gui(fail_to_start)

    assert len(dialogs) == 1
    assert "startup.log" in dialogs[0][1]
    assert (tmp_path / "startup.log").is_file()
