"""Gestos de Tk 9 sobre páginas, sin desplazar a la vez las tablas interiores."""
import tkinter as tk
from types import SimpleNamespace

import customtkinter as ctk
import pytest

from conxml.ui.scroll import PaginaDesplazable
from conxml.ui.tabla_visor import TablaVisor


@pytest.fixture
def raiz():
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip('Sin display')
    if not root.tk.call('info', 'commands', 'tk::PreciseScrollDeltas'):
        root.destroy()
        pytest.skip('Tk anterior al soporte de TouchpadScroll')
    root.geometry('700x420')
    yield root
    root.destroy()


def delta(x=0, y=0):
    return (x << 16) | (y & 0xffff)


def test_configuracion_responde_al_trackpad_sobre_sus_controles(raiz, tmp_path, monkeypatch):
    from conxml.ui.pantalla_ajustes import PantallaAjustes
    monkeypatch.setenv('CONXML_DATA_DIR', str(tmp_path))
    pantalla = PantallaAjustes(raiz, SimpleNamespace(detalles_visibles=False))
    pantalla.pack(fill='both', expand=True)
    raiz.update()
    canvas = pantalla._contenedor._parent_canvas
    assert canvas.yview()[1] < 1
    pantalla.lbl_db_path.event_generate('<TouchpadScroll>', delta=delta(y=-96))
    raiz.update()
    assert canvas.yview()[0] > 0
    pantalla.lbl_db_path.event_generate('<TouchpadScroll>', delta=delta(y=96))
    raiz.update()
    assert canvas.yview()[0] == 0
    pantalla.lbl_db_path.event_generate('<TouchpadScroll>', delta=delta(x=-96))
    raiz.update()
    assert canvas.yview()[0] == 0


def test_trackpad_en_tabla_no_mueve_pagina(raiz):
    pagina = PaginaDesplazable(raiz)
    pagina.pack(fill='both', expand=True)
    tabla = TablaVisor(pagina, ['dato'])
    tabla.configure(height=180)
    tabla.grid_propagate(False)
    tabla.pack(fill='x')
    ctk.CTkFrame(pagina, height=1200).pack(fill='x')
    for i in range(150):
        tabla.insert('', 'end', values=(i,))
    raiz.update()
    assert pagina._parent_canvas.yview()[1] < 1
    tabla.sheet.MT.event_generate('<TouchpadScroll>', delta=delta(y=-96))
    raiz.update()
    assert tabla.sheet.MT.yview()[0] > 0
    assert pagina._parent_canvas.yview()[0] == 0


def test_movimientos_pequenos_del_trackpad_se_acumulan(raiz):
    pagina = PaginaDesplazable(raiz)
    pagina.pack(fill='both', expand=True)
    etiqueta = ctk.CTkLabel(pagina, text='Contenido de la página')
    etiqueta.pack()
    ctk.CTkFrame(pagina, height=1200).pack(fill='x')
    raiz.update()
    incremento = int(float(pagina._parent_canvas.cget('yscrollincrement'))) or 1
    for _ in range(incremento - 1):
        etiqueta.event_generate('<TouchpadScroll>', delta=delta(y=-1))
        raiz.update()
        assert pagina._parent_canvas.yview()[0] == 0
    etiqueta.event_generate('<TouchpadScroll>', delta=delta(y=-1))
    raiz.update()
    assert pagina._parent_canvas.yview()[0] > 0


def test_destruir_pagina_retira_solo_su_binding(raiz):
    primera = PaginaDesplazable(raiz)
    segunda = PaginaDesplazable(raiz)
    primera_id = primera._binding_touchpad[1]
    segunda_id = segunda._binding_touchpad[1]
    primera.destroy()
    bindings = raiz.bind('<TouchpadScroll>')
    assert primera_id not in bindings
    assert segunda_id in bindings
    segunda.destroy()
    assert segunda_id not in raiz.bind('<TouchpadScroll>')
