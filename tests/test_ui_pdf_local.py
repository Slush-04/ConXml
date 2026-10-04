from pathlib import Path
import tkinter as tk
import zipfile

import customtkinter as ctk
import pytest

from conxml import estado_local
from conxml.catalog.db import Catalogo
from conxml.catalog.importer import importar_carpeta
from conxml.ui.app import ConXmlApp
from conxml.ui.visor_pdf import VisorPDF
from conxml.export.pdf import generar_pdf

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('CONXML_DATA_DIR', str(tmp_path))
    with Catalogo(tmp_path / 'catalogo.db') as cat:
        cat.crear_cliente('C1', 'Cliente de prueba', 'EKU9003173C9')
        importar_carpeta(cat, FIXTURES, 'C1')
    root = ctk.CTk()
    ventana = ConXmlApp(root, cliente_actual='C1')
    root.update_idletasks()
    yield ventana
    try:
        root.destroy()
    except tk.TclError:
        pass


def test_pdf_lote_respeta_vista_y_seleccion(app, tmp_path, monkeypatch):
    app.navegar('admin40')
    pantalla = app._pantallas['admin40']
    pantalla._filtros['uuid'].insert(0, '426614174000')
    pantalla._aplicar_filtros()
    items = pantalla._tabla.get_children()
    assert len(items) == 1
    pantalla._tabla.selection_set(items[0])
    seleccion = pantalla._documentos_pdf()
    assert len(seleccion) == 1
    assert seleccion[0]['uuid'].endswith('426614174000')
    assert pantalla._documentos_pdf(todos=True) == seleccion
    destino = tmp_path / 'filtrado.zip'
    monkeypatch.setattr('conxml.ui.pantalla_admin.filedialog.asksaveasfilename', lambda **kw: str(destino))
    monkeypatch.setattr(app, 'ejecutar', lambda fn, callback, texto: callback(fn()))
    pantalla._pdf_vista()
    with zipfile.ZipFile(destino) as z:
        assert z.namelist() == ['123E4567-E89B-12D3-A456-426614174000.pdf']


def test_sesion_recupera_cliente_pantalla_filtros_y_opciones(app, tmp_path):
    app.navegar('admin40')
    app._pantallas['admin40']._filtros['rfc'].insert(0, 'EKU')
    assert not app._pantallas['ajustes'].limpiar_al_leer.get()
    app.guardar_sesion()
    datos = estado_local.cargar()
    assert datos['sesion']['pantalla'] == 'admin40'
    assert datos['sesion']['cliente'] == 'C1'
    app.recargar_datos_locales()
    nueva = app.master._conxml_app
    assert nueva.cliente_actual == 'C1'
    assert nueva._clave_pantalla == 'admin40'
    assert nueva._pantallas['admin40']._filtros['rfc'].get() == 'EKU'


def test_vista_previa_local_pagina_y_guarda(app, tmp_path, monkeypatch):
    ruta = generar_pdf(FIXTURES / 'pago_rep_multiple.xml', tmp_path / 'vista.pdf')
    visor = VisorPDF(app, ruta)
    app.master.update_idletasks()
    assert len(visor.doc) > 1
    ancho_original = visor.imagen.winfo_reqwidth()
    visor._cambiar_zoom(.5)
    assert visor.imagen.winfo_reqwidth() > ancho_original
    assert float(visor.canvas.cget('scrollregion').split()[2]) > visor.canvas.winfo_width()
    visor._ajustar_ancho()
    assert visor._zoom == 1.0
    visor._mover(1)
    assert visor.pagina == 1
    destino = tmp_path / 'guardado.pdf'
    monkeypatch.setattr('conxml.ui.visor_pdf.filedialog.asksaveasfilename', lambda **kw: str(destino))
    visor._guardar()
    assert destino.read_bytes() == ruta.read_bytes()
    visor._cerrar()
    assert destino.is_file()
    assert not ruta.exists()


def test_cierre_espera_respaldo_y_guarda_sesion(app, tmp_path):
    app.navegar('nomina')
    app.master.after(50, app._al_cerrar)
    app.master.after(8000, app.master.destroy)
    app.master.mainloop()
    respaldos = list((tmp_path / 'respaldos').glob('auto_*.zip'))
    assert len(respaldos) == 1
    with zipfile.ZipFile(respaldos[0]) as z:
        assert 'catalogo.db' in z.namelist()
        assert 'preferencias.json' in z.namelist()
    assert estado_local.cargar(tmp_path / 'preferencias.json')['sesion']['pantalla'] == 'nomina'


def test_visor_renderizado_alternativo_y_limpieza(app, tmp_path):
    ruta = generar_pdf(FIXTURES / 'ingreso_iva.xml', tmp_path / 'alternativo.pdf')
    visor = VisorPDF(app, ruta)
    temporal = Path(visor._temporales.name)
    visor._mostrar()
    ancho = visor._foto.width()
    visor._cambiar_zoom(.5)
    assert visor._foto.width() > ancho
    assert visor._foto.height() > 0
    visor._cerrar()
    assert not temporal.exists()
    assert not ruta.exists()
