"""Comprueba el acceso manual y que la opción pendiente no envíe solicitudes."""
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


@pytest.mark.parametrize("error", [False, True])
def test_error_navegador_muestra_ruta_manual(monkeypatch, error):
    avisos = []
    def abrir():
        if error:
            raise OSError("Navegador no disponible")
        return False
    monkeypatch.setattr("conxml.ui.pantalla_descargas.abrir_portal_sat", abrir)
    monkeypatch.setattr("conxml.ui.pantalla_descargas.messagebox.showerror", lambda *args, **kw: avisos.append(args))
    PantallaDescargas._abrir_portal(SimpleNamespace())
    assert len(avisos) == 1
    assert descargas.PORTAL_CFDI_URL in avisos[0][1]


def test_pantalla_manual_y_automatica_pendiente(monkeypatch):
    import tkinter as tk
    import customtkinter as ctk

    try:
        raiz = ctk.CTk()
    except tk.TclError:
        pytest.skip("No hay pantalla disponible")
    llamadas = []
    monkeypatch.setattr("conxml.ui.pantalla_descargas.abrir_portal_sat", lambda: llamadas.append("portal") or True)
    app = SimpleNamespace(cliente_actual="CLIENTE_1", navegar=lambda clave: llamadas.append(clave))
    try:
        raiz.geometry("700x500")
        pantalla = PantallaDescargas(raiz, app)
        pantalla.pack(fill="both", expand=True)
        pantalla.al_mostrar()
        pantalla.aplicar_modo_compacto(True, True)
        raiz.update()
        assert pantalla._btn_automatica.cget("state") == "disabled"
        assert "En proceso" in pantalla._btn_automatica.cget("text")
        pantalla._btn_automatica.invoke()
        assert llamadas == []
        pantalla._btn_portal.invoke()
        assert llamadas == ["portal"]
        app.cliente_actual = "CLIENTE_2"
        pantalla.al_mostrar()
        assert "CLIENTE_2" in pantalla._cliente_lbl.cget("text")
        assert int(pantalla._contenedor.pack_info()["padx"]) == 12
    finally:
        raiz.destroy()
