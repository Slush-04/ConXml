"""El formulario SAT conserva su distribución con escalado DPI y poco ancho."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from conxml.ui import responsive as resp
from conxml.ui.pantalla_descargas import PantallaDescargas


@pytest.mark.parametrize("escala", [1, 1.25, 1.5, 2])
def test_formulario_usa_ancho_logico_y_restaura_columnas(monkeypatch, escala):
    pantalla = SimpleNamespace(
        _formulario=Mock(), _panel_cred=Mock(), _panel_solicitud=Mock(),
        _separador_formulario=Mock(), _modo_formulario_apilado=None,
    )
    monkeypatch.setattr(resp, "escalado_widget", lambda widget: escala)
    PantallaDescargas._acomodar_formulario(pantalla, int(900 * escala))
    assert pantalla._modo_formulario_apilado is True
    assert pantalla._panel_solicitud.grid_configure.call_args.kwargs["row"] == 1
    PantallaDescargas._acomodar_formulario(pantalla, int(1150 * escala))
    assert pantalla._modo_formulario_apilado is False
    assert pantalla._panel_solicitud.grid_configure.call_args.kwargs["column"] == 2


def test_acciones_firma_caben_en_panel_estrecho():
    import tkinter as tk
    import customtkinter as ctk

    try:
        raiz = ctk.CTk()
    except tk.TclError:
        pytest.skip("No hay pantalla disponible")
    try:
        raiz.geometry("680x740")
        pantalla = PantallaDescargas(raiz, SimpleNamespace())
        pantalla.pack(fill="both", expand=True)
        raiz.update()
        assert pantalla._modo_formulario_apilado is True
        acciones = pantalla._btn_guardar_firma.master
        # Reducir directamente el panel comprueba el salto de fila sin depender
        # de los mínimos de la ventana principal de la aplicación.
        acciones.grid_remove()
        acciones.configure(width=320)
        acciones.place(x=0, y=0)
        raiz.update()
        botones = [pantalla._btn_guardar_firma, pantalla._btn_quitar_firma, pantalla._btn_seguimiento]
        assert len({boton.winfo_y() for boton in botones}) > 1
        for boton in botones:
            assert boton.winfo_x() >= 0
            assert boton.winfo_x() + boton.winfo_width() <= acciones.winfo_width() + 1
            assert boton.winfo_y() + boton.winfo_height() <= acciones.winfo_height() + 1
    finally:
        raiz.destroy()
