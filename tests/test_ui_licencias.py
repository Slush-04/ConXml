import queue
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from conxml.ui.licencias import LicenseView
from conxml.licencias import LicenseError
from conxml import licensing_client
from conxml.cli import main


@pytest.mark.parametrize('busy,dialog,show', [(True, False, False), (False, True, False), (False, False, True)])
def test_gate_respects_operation_and_existing_dialog(busy, dialog, show):
    view = LicenseView.__new__(LicenseView)
    view.root = Mock()
    view.root._conxml_app = SimpleNamespace(_ocupada=busy)
    view.root.grab_current.return_value = object() if dialog else None
    view.client = Mock()
    view.client.allowed.return_value = False
    view.window = None
    view.events = queue.Queue()
    view.show = Mock()
    view.poll()
    assert view.show.called == show


def test_cli_gate_precedes_any_catalog_write(monkeypatch, tmp_path):
    def deny():
        raise LicenseError('Activación pendiente')
    monkeypatch.setattr(licensing_client, 'require_access', deny)
    destination = tmp_path / 'catalogo.db'
    with pytest.raises(SystemExit) as exc:
        main(['import', str(tmp_path), 'TEST', '--db', str(destination)])
    assert exc.value.code == 2
    assert not destination.exists()


def test_activation_dialog_opens_and_continues_only_after_validation(monkeypatch):
    import tkinter as tk
    import time
    import conxml.ui.licencias as ui
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('sin display')
    client = Mock()
    client.error = 'Activación pendiente'
    client.allowed.return_value = False
    monkeypatch.setattr(ui, 'get_client', lambda: client)
    ready = Mock()
    try:
        view = ui.LicenseView(root, ready)
        root.update_idletasks()
        assert view.window is not None
        ready.assert_not_called()
        view.code.insert(0, 'a' * 43)
        view.submit()
        limit = time.monotonic() + 2
        while view.events.empty() and time.monotonic() < limit:
            time.sleep(.01)
        assert view.code.get() == ''
        client.sync.assert_called_once_with('a' * 43)
        client.allowed.return_value = True
        view.poll()
        assert view.window is None
        ready.assert_called_once()
        view.poll()
        ready.assert_called_once()
    finally:
        root.destroy()


def test_cli_identifies_trial_edition_without_opening_keyring(monkeypatch, capsys):
    from conxml import distribucion
    monkeypatch.setattr(distribucion, 'MODE', 'trial')
    monkeypatch.setattr(licensing_client, 'get_client', Mock(side_effect=AssertionError('No abrir keyring para identificar la edición')))
    main(['licencia', 'edicion'])
    assert capsys.readouterr().out.strip() == 'trial'
