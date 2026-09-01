"""Smoke test de la UI: detecta roturas de importación y valida el arranque.

Construye la ventana completa (``ConXmlApp``) si hay display disponible; en
entornos sin pantalla (CI headless) se salta esa parte sin fallar.
"""

import tkinter as tk


def test_ui_theme_importable():
    from conxml.ui import theme as th

    assert th.configurar_ctk
    assert th.FONDO_TARJETA
    assert th.PRIMARIO
    assert th.RADIO_BORDE
    assert th.SIDEBAR_FONDO
    assert th.SIDEBAR_ACENTO
    assert set(th.TONOS) >= {"verde", "rojo", "ambar", "gris", "azul"}


def test_ui_configurar_ctk():
    from conxml.ui import theme as th

    th.configurar_ctk()


def test_ui_arranca_con_display():
    try:
        import customtkinter as ctk
    except ImportError:
        return  # customtkinter no instalado: no se puede validar el arranque
    try:
        raiz = ctk.CTk()
    except tk.TclError:
        return  # sin display disponible: no se puede validar el arranque
    raiz.withdraw()
    try:
        from conxml.ui.app import ConXmlApp

        ventana = ConXmlApp(raiz)
        raiz.update()
        assert ventana.winfo_exists()
    finally:
        raiz.destroy()