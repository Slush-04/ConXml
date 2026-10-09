"""Primera apertura: persistencia, fallos y limpieza del reproductor."""
from types import SimpleNamespace

import pytest

from conxml import estado_local
from conxml.ui import introduccion as intro


class Raiz:
    def __init__(self):
        self._introduccion = None
        self.oculta = False
        self.callbacks = []
        self.cancelados = []

    def bind(self, *args, **kwargs):
        return "binding"

    def unbind(self, *args):
        pass

    def after(self, tiempo, callback):
        self.callbacks.append(callback)
        return "timer"

    def after_cancel(self, identificador):
        self.cancelados.append(identificador)

    def withdraw(self):
        self.oculta = True

    def deiconify(self):
        self.oculta = False


@pytest.fixture
def perfil(tmp_path, monkeypatch):
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path))
    return tmp_path


def test_primera_apertura_inicia_sin_bloquear_y_omitir_no_pierde_sesion(perfil, monkeypatch):
    estado_local.guardar({"sesion": {"cliente": "C1"}, "limpiar_al_leer": False})
    proceso = SimpleNamespace(poll=lambda: None)
    monkeypatch.setattr(intro, "_comando", lambda: ["reproductor", "intro.mp4"])
    monkeypatch.setattr(intro.subprocess, "Popen", lambda *a, **kw: proceso)
    root, continuaciones = Raiz(), []
    intro.primera_apertura(root, lambda: continuaciones.append(True))
    assert root.oculta and not continuaciones
    assert intro.CLAVE_VISTA not in estado_local.cargar()
    proceso.poll = lambda: 0  # Omitir, cerrar o Comenzar.
    root.callbacks.pop(0)()
    assert not root.oculta and continuaciones == [True]
    datos = estado_local.cargar()
    assert datos[intro.CLAVE_VISTA] is True
    assert datos["sesion"] == {"cliente": "C1"}
    assert datos["limpiar_al_leer"] is False
    intro.primera_apertura(root, lambda: continuaciones.append(True))
    assert continuaciones == [True, True]
    assert not root._introduccion


@pytest.mark.parametrize("codigo", [2, -15])
def test_error_de_reproduccion_recupera_inicio_y_no_marca_vista(perfil, codigo):
    root, continuaciones = Raiz(), []
    root.withdraw()
    reproductor = intro.ReproductorIntroduccion(
        root, SimpleNamespace(poll=lambda: codigo), lambda: continuaciones.append(True), True)
    reproductor.comprobar()
    reproductor.comprobar()
    assert not root.oculta
    assert continuaciones == [True]
    assert intro.CLAVE_VISTA not in estado_local.cargar()


@pytest.mark.parametrize("no_disponible", [True, False])
def test_no_hay_reproductor_o_no_puede_arrancar_programa_continua(perfil, monkeypatch, no_disponible):
    monkeypatch.setattr(intro, "_comando", lambda: None if no_disponible else ["reproductor"])
    def fallar(*args, **kwargs):
        raise OSError("No se pudo abrir")
    monkeypatch.setattr(intro.subprocess, "Popen", fallar)
    root, continuaciones = Raiz(), []
    intro.primera_apertura(root, lambda: continuaciones.append(True))
    assert not root.oculta
    assert continuaciones == [True]
    assert intro.CLAVE_VISTA not in estado_local.cargar()


def test_cerrar_raiz_detiene_musica_y_no_confunde_destruccion_de_hijos(perfil):
    root, terminaciones = Raiz(), []
    proceso = SimpleNamespace(poll=lambda: None, terminate=lambda: terminaciones.append(True))
    reproductor = intro.ReproductorIntroduccion(root, proceso, lambda: None, True)
    reproductor.comprobar()
    reproductor._al_destruir(SimpleNamespace(widget=object()))
    assert not terminaciones
    reproductor._al_destruir(SimpleNamespace(widget=root))
    assert terminaciones == [True]
    assert root.cancelados == ["timer"]
    assert intro.CLAVE_VISTA not in estado_local.cargar()


def test_repetir_desde_ayuda_no_reescribe_preferencias(perfil):
    estado_local.guardar({intro.CLAVE_VISTA: True, "sesion": {"cliente": "C1"}})
    root, callbacks = Raiz(), []
    reproductor = intro.ReproductorIntroduccion(
        root, SimpleNamespace(poll=lambda: 0), lambda: callbacks.append(True), False)
    reproductor.comprobar()
    assert callbacks == [True]
    assert estado_local.cargar() == {intro.CLAVE_VISTA: True, "sesion": {"cliente": "C1"}}


def test_video_empaquetado_es_local_y_comando_mac_no_depende_de_red(monkeypatch, tmp_path):
    monkeypatch.setattr(intro.sys, "platform", "darwin")
    monkeypatch.setattr(intro.sys, "frozen", True, raising=False)
    monkeypatch.setattr(intro.sys, "_MEIPASS", str(tmp_path), raising=False)
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "introduccion.mp4").write_bytes(b"video")
    (assets / "conxml-intro-player").touch()
    assert intro._comando() == [str(assets / "conxml-intro-player"), str(assets / "introduccion.mp4")]


def test_windows_usa_script_local_sta_y_rutas_con_espacios(monkeypatch, tmp_path):
    monkeypatch.setattr(intro.sys, "platform", "win32")
    monkeypatch.setattr(intro.sys, "frozen", True, raising=False)
    monkeypatch.setattr(intro.sys, "_MEIPASS", str(tmp_path), raising=False)
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "introduccion.mp4").touch()
    (assets / "Introduccion.ps1").touch()
    windows = tmp_path / "Sistema con espacios"
    ps = windows / "System32/WindowsPowerShell/v1.0/powershell.exe"
    ps.parent.mkdir(parents=True)
    ps.touch()
    monkeypatch.setenv("SystemRoot", str(windows))
    comando = intro._comando()
    assert comando[0] == str(ps)
    assert "-STA" in comando
    assert comando[-1] == str(assets / "introduccion.mp4")
    assert comando[comando.index("-File") + 1] == str(assets / "Introduccion.ps1")


def test_ayuda_abre_reproductor_desde_boton(perfil):
    # Aislar los callbacks globales de Tk/CTk de las demás pruebas de ventanas.
    import subprocess
    import sys

    codigo = """
from types import SimpleNamespace
import tkinter as tk
import customtkinter as ctk
from conxml.ui import app as modulo
try:
    raiz = ctk.CTk()
except tk.TclError:
    raise SystemExit(77)
llamadas = []
modulo.mostrar_introduccion = lambda parent: llamadas.append(parent) or True
try:
    modulo.ConXmlApp.mostrar_ayuda(SimpleNamespace(master=raiz))
    ventana = next(w for w in raiz.winfo_children() if isinstance(w, ctk.CTkToplevel))
    boton = next(w for w in ventana.winfo_children() if isinstance(w, ctk.CTkButton))
    assert boton.cget('text') == 'Ver introducción'
    boton.invoke()
    assert llamadas == [raiz]
    assert not ventana.winfo_exists()
finally:
    raiz.destroy()
"""
    resultado = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, timeout=30)
    if resultado.returncode == 77:
        pytest.skip("Sin pantalla disponible")
    assert resultado.returncode == 0, resultado.stderr
