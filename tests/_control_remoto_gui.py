import tkinter as tk
import customtkinter as ctk
from types import SimpleNamespace
from uuid import uuid4

import pytest

from conxml.ui.control_remoto import RemoteControlView


@pytest.fixture(scope="module")
def application():
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("Sin pantalla disponible")
    root.report_callback_exception = lambda *args: pytest.fail(str(args))
    # CTk difiere el primer mapeo en Windows. La vista de control ignora por
    # diseño una raíz withdrawn; probarla después de mostrar la aplicación.
    root.deiconify()
    root.update()
    assert root.state() != 'withdrawn'
    yield root
    root.destroy()


@pytest.fixture
def window(application):
    # La aplicación real conserva una única raíz CTk y crea avisos Toplevel.
    if hasattr(application, "_conxml_app"):
        del application._conxml_app
    yield application
    for child in application.winfo_children():
        if isinstance(child, tk.Toplevel):
            child.destroy()


def test_lock_waits_for_work_to_finish_and_unlock_releases_access(window):
    window._conxml_app = SimpleNamespace(_ocupada=True)
    view = RemoteControlView(window, lambda ids: None)
    assert view.sync(True) is False
    assert view.lock_window is None
    window._conxml_app._ocupada = False
    assert view.sync(True) is True
    assert view.lock_window.winfo_exists()
    assert window.grab_current() is view.lock_window
    assert view.sync(False) is True
    assert view.lock_window is None
    assert window.grab_current() is None


def test_message_is_only_confirmed_when_dismissed_and_can_be_read_while_locked(window):
    acknowledgements = []
    view = RemoteControlView(window, lambda ids: acknowledgements.extend(ids))
    identifier = str(uuid4())
    view.queue_messages([{"id": identifier, "text": "Aviso de prueba"}])
    assert view.sync(True)
    assert view.message_window.winfo_exists()
    assert acknowledgements == []
    view._dismiss_messages()
    assert acknowledgements == [identifier]
    assert view.message_window is None
    assert window.grab_current() is view.lock_window


def test_an_existing_dialog_is_not_interrupted_by_remote_lock(window):
    dialog = tk.Toplevel(window)
    dialog.grab_set()
    view = RemoteControlView(window, lambda ids: None)
    assert view.sync(True) is False
    assert view.lock_window is None
    dialog.destroy()
    assert view.sync(True) is True


def test_unlock_can_arrive_while_a_message_is_still_open(window):
    view = RemoteControlView(window, lambda ids: None)
    view.queue_messages([{"id": str(uuid4()), "text": "Mensaje de prueba"}])
    assert view.sync(True)
    assert view.sync(False)
    assert view.lock_window is None
    assert view.message_window.winfo_exists()
    view._dismiss_messages()
    assert window.grab_current() is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
