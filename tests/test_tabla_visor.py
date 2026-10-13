"""Paginación, selección y copia sin modificar los datos del catálogo."""
import tkinter as tk

import pytest

from conxml.ui.tabla_visor import TablaVisor


@pytest.fixture
def tabla():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(str(exc))
    root.geometry('800x500')
    tabla = TablaVisor(root, ['uuid', 'total'])
    tabla.pack(fill='both', expand=True)
    for i in range(301):
        tabla.insert('', 'end', values=(f'UUID-{i}', i))
    root.update()
    yield tabla
    root.destroy()


def test_paginas_de_150_y_ultima_incompleta(tabla):
    assert len(tabla.sheet.get_sheet_data()) == 150
    tabla.sheet.set_yview(0.5)
    tabla.cambiar_pagina(1)
    tabla.update()
    assert tabla.sheet.MT.yview()[0] == 0
    assert tabla.sheet.get_sheet_data()[0] == ['UUID-150', 150]
    tabla.cambiar_pagina(1)
    tabla.update()
    assert tabla.sheet.get_sheet_data() == [['UUID-300', 300]]
    tabla.cambiar_pagina(1)
    tabla.update()
    assert tabla._pagina == 2
    tabla.delete(*tabla.get_children())
    tabla.update()
    assert tabla._pagina == 0
    assert tabla.sheet.get_sheet_data() == []


def test_copia_celda_y_seleccion_en_segunda_pagina(tabla):
    tabla.cambiar_pagina(1)
    tabla.update()
    tabla.sheet.select_cell(0, 0)
    assert tabla.selection() == (tabla.items_pagina()[0],)
    tabla.sheet.copy()
    assert tabla.clipboard_get().strip() == 'UUID-150'
    assert tabla.item(tabla.selection()[0], 'values') == ('UUID-150', 150)
    tabla.cambiar_pagina(-1)
    tabla.update()
    assert tabla.selection() == ()


def test_orden_global_y_columnas_ocultas(tabla):
    tabla.ordenar(reversed(tabla.get_children()))
    tabla.configure(displaycolumns=['total'])
    tabla.update()
    assert tabla.sheet.get_sheet_data()[0] == ['UUID-300', 300]
    tabla.sheet.select_cell(0, 0)
    tabla.sheet.copy()
    assert tabla.clipboard_get().strip() == '300'
    assert tabla.item(tabla.selection()[0], 'values')[0] == 'UUID-300'
