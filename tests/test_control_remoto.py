"""Aísla Tk en su propio proceso para no recrear intérpretes Tk 9 en macOS."""

from pathlib import Path
import subprocess
import sys


def test_remote_control_windows_in_isolated_application():
    helper = Path(__file__).with_name("_control_remoto_gui.py")
    arguments = [sys.executable, str(helper)]
    if sys.platform == "darwin":
        # Solo esta ejecución: no modifica preferencias ni restaura ventanas del usuario.
        arguments += ["-ApplePersistenceIgnoreState", "YES"]
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
