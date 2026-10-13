"""Verifica reflujo real al cambiar DPI, contenido y ancho disponible."""
import subprocess
import sys

import pytest


@pytest.mark.parametrize('escala', [1.0, 1.25, 1.5, 2.0])
def test_barra_refluye_sin_recortes_y_actualiza_textos(escala):
    codigo = '''
import customtkinter as ctk
from conxml.ui.widgets import BarraAdaptable, texto_adaptable
ctk.set_widget_scaling(SCALE)
ctk.set_window_scaling(SCALE)
raiz = ctk.CTk()
try:
    raiz.geometry('500x450')
    barra = BarraAdaptable(raiz)
    barra.pack(fill='x')
    controles = [barra.agregar(ctk.CTkLabel(barra, text='Acción', width=120)) for _ in range(3)]
    raiz.update()
    assert len({c.winfo_y() for c in controles}) == 1
    raiz.geometry('270x450')
    raiz.update()
    assert len({c.winfo_y() for c in controles}) > 1
    for c in controles:
        assert c.winfo_x() + c.winfo_width() <= barra.winfo_width() + 2
        assert c.winfo_y() + c.winfo_height() <= barra.winfo_height() + 2
    raiz.geometry('500x450')
    raiz.update()
    controles[0].configure(text='Una acción con una descripción mucho más larga')
    raiz.update()
    assert controles[1].winfo_y() > controles[0].winfo_y() or controles[1].winfo_x() >= controles[0].winfo_width()
    # El helper se instala después de que el panel ya tiene su tamaño final.
    panel = ctk.CTkFrame(raiz, width=250, height=120)
    panel.pack()
    panel.pack_propagate(False)
    raiz.update()
    etiqueta = ctk.CTkLabel(panel, text='Una descripción larga ' * 8, wraplength=900)
    etiqueta.pack(fill='x')
    raiz.update()
    texto_adaptable(etiqueta, panel, margen=16)
    raiz.update()
    assert 225 <= etiqueta.cget('wraplength') <= 236
finally:
    raiz.destroy()
'''.replace('SCALE', repr(escala))
    resultado = subprocess.run([sys.executable, '-c', codigo], capture_output=True, text=True, timeout=30)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_destruir_componentes_cancela_callbacks_pendientes():
    codigo = '''
import customtkinter as ctk
from conxml.ui.widgets import BarraAdaptable, texto_adaptable
raiz = ctk.CTk()
try:
    barra = BarraAdaptable(raiz)
    barra.agregar(ctk.CTkLabel(barra, text='Temporal'))
    pendiente = barra._reparto_pendiente
    barra.destroy()
    assert pendiente not in raiz.tk.call('after', 'info')
    panel = ctk.CTkFrame(raiz)
    etiqueta = ctk.CTkLabel(panel, text='Temporal')
    antes = set(raiz.tk.call('after', 'info'))
    texto_adaptable(etiqueta, panel)
    nuevos = set(raiz.tk.call('after', 'info')) - antes
    assert nuevos
    etiqueta.destroy()
    assert not nuevos.intersection(raiz.tk.call('after', 'info'))
    raiz.update_idletasks()
finally:
    raiz.destroy()
'''
    resultado = subprocess.run([sys.executable, '-c', codigo], capture_output=True, text=True, timeout=30)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert 'invalid command name' not in resultado.stderr, resultado.stderr


def test_visor_pdf_conserva_acciones_en_dialogo_estrecho(tmp_path, monkeypatch):
    import tkinter as tk
    import customtkinter as ctk
    from reportlab.pdfgen import canvas
    from conxml.ui import responsive as resp
    from conxml.ui.visor_pdf import VisorPDF
    from conxml.ui.widgets import BarraAdaptable

    ruta = tmp_path / 'prueba.pdf'
    documento = canvas.Canvas(str(ruta))
    documento.drawString(40, 700, 'Prueba de pantalla estrecha')
    documento.save()
    try:
        raiz = ctk.CTk()
    except tk.TclError:
        pytest.skip('Sin display disponible')
    visor = None
    try:
        raiz.geometry('500x450')
        raiz.update_idletasks()
        monkeypatch.setattr(resp, 'area_util', lambda _: (0, 0, 420, 640))
        visor = VisorPDF(raiz, ruta)
        # Windows aplica el mapeo del Toplevel mediante eventos; las tareas
        # idle por sí solas pueden dejar controles con geometría provisional.
        import time
        limite = time.monotonic() + 3
        while not visor.winfo_viewable() and time.monotonic() < limite:
            raiz.update()
            time.sleep(0.01)
        raiz.update()
        assert visor.winfo_viewable()
        barras = [h for h in visor.winfo_children() if isinstance(h, BarraAdaptable)]
        assert len(barras) == 2
        assert len({h.winfo_y() for h in barras[0]._elementos}) > 1
        for barra in barras:
            for control in barra._elementos:
                assert control.winfo_x() + control.winfo_width() <= barra.winfo_width() + 2
                assert control.winfo_y() + control.winfo_height() <= barra.winfo_height() + 2
    finally:
        if visor is not None:
            visor._cerrar()
        raiz.destroy()
