"""Acceso al portal y preferencias de guardado SAT en la interfaz."""
from types import SimpleNamespace

import pytest

from conxml.sat import descargas
from conxml.ui.pantalla_descargas import PantallaDescargas


@pytest.mark.parametrize("resultado", [True, False])
def test_abrir_portal_oficial(monkeypatch, resultado):
    llamadas = []
    def abrir(url, **kwargs):
        llamadas.append((url, kwargs))
        return resultado
    monkeypatch.setattr(descargas.webbrowser, "open", abrir)
    assert descargas.abrir_portal_sat() is resultado
    assert llamadas == [("https://portalcfdi.facturaelectronica.sat.gob.mx/", {"new": 2})]


def test_configuracion_guardado_persiste_y_separa_carpetas(tmp_path, monkeypatch):
    import tkinter as tk
    import customtkinter as ctk
    from conxml.config import Config
    from conxml.ui.pantalla_ajustes import PantallaAjustes
    monkeypatch.setenv("CONXML_DATA_DIR", str(tmp_path / "datos"))
    try:
        raiz = ctk.CTk()
    except tk.TclError:
        pytest.skip("No hay pantalla disponible")
    try:
        app = SimpleNamespace(detalles_visibles=False)
        ajustes = PantallaAjustes(raiz, app)
        ajustes.pack(fill="both", expand=True)
        ajustes._carpeta_sat.set(str(tmp_path / "xml"))
        ajustes._guardar_destino_sat()
        assert Config().carpeta_boveda == tmp_path / "xml"
        ajustes._modo_sat.set("Conservar ZIP sin extraer")
        ajustes._cambiar_modo_sat(ajustes._modo_sat.get())
        ajustes._carpeta_sat.set(str(tmp_path / "zip"))
        ajustes._guardar_destino_sat()
        raiz.update_idletasks()
        assert Config().modo_descarga_sat == "zip"
        assert Config().carpeta_zip_sat == tmp_path / "zip"
        assert Config().carpeta_boveda == tmp_path / "xml"
        ajustes._cargar_destino_sat()
        assert ajustes._carpeta_sat.get() == str(tmp_path / "zip")
    finally:
        raiz.destroy()
