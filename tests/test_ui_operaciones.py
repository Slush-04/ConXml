"""Actualización visible, operaciones identificables y carga externa en visores."""
from pathlib import Path
import threading
import time
import tkinter as tk

import customtkinter as ctk
import pytest

from conxml.catalog.db import Catalogo
from conxml.ui.app import ConXmlApp


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('CONXML_DATA_DIR', str(tmp_path))
    monkeypatch.setattr('conxml.ui.actualizaciones.Actualizaciones.check', lambda *a, **k: None)
    with Catalogo(tmp_path / 'catalogo.db') as cat:
        cat.crear_cliente('C1', 'Cliente prueba', 'EKU9003173C9')
    try:
        root = ctk.CTk()
    except tk.TclError as exc:
        pytest.skip(str(exc))
    ventana = ConXmlApp(root, cliente_actual='C1')
    root.geometry('1100x700')
    root.update()
    yield ventana
    try:
        root.destroy()
    except tk.TclError:
        pass


def esperar(app, condicion):
    limite = time.monotonic() + 5
    while not condicion() and time.monotonic() < limite:
        app.master.update()
        time.sleep(.01)
    assert condicion()


def test_actualizacion_visible_con_menu_expandido_y_ruta_larga(app):
    app.master.update()
    boton = app.actualizaciones.button
    assert not hasattr(app, "_lbl_db_ruta")
    assert app._lbl_cliente.cget("text") == "Cliente prueba"
    assert boton.winfo_viewable()
    assert boton.winfo_rooty() + boton.winfo_height() <= app.master.winfo_rooty() + app.master.winfo_height()
    assert boton.winfo_rooty() < app._lbl_version.winfo_rooty()
    assert app._zona_nav._parent_canvas.winfo_height() > 50


def test_operacion_visible_al_navegar_y_cierre_al_terminar(app, monkeypatch):
    liberar = threading.Event()
    avisos = []
    monkeypatch.setattr('conxml.ui.app.messagebox.askyesno', lambda titulo, texto, **k: avisos.append(texto) or True)
    cerrado = []
    monkeypatch.setattr(app, '_cerrar_con_respaldo', lambda r: cerrado.append(True))
    # Evitar respaldo real y mantener la ventana para verificar la intención de cierre.
    monkeypatch.setattr(app, 'guardar_sesion', lambda: None)
    monkeypatch.setattr('conxml.ui.app.estado_local.cargar', lambda: {'respaldo_al_cerrar': False})
    original_destroy = app.master.destroy
    monkeypatch.setattr(app.master, 'destroy', lambda: cerrado.append(True))
    try:
        app.ejecutar(lambda: liberar.wait(3), lambda r: None, 'Importando carpeta externa')
        app.navegar('pagos')
        app.master.update()
        assert app._estado_operacion.winfo_viewable()
        assert 'Importando carpeta externa' in app._texto_operacion.cget('text')
        app._al_cerrar()
        assert 'Importando carpeta externa' in avisos[0]
        assert app._cierre_solicitado
        assert not cerrado
        liberar.set()
        esperar(app, lambda: bool(cerrado))
        assert not app._ocupada
    finally:
        liberar.set()
        monkeypatch.setattr(app.master, 'destroy', original_destroy)


def test_callback_fallido_no_interrumpe_siguientes_operaciones(app, monkeypatch):
    errores = []
    monkeypatch.setattr('conxml.ui.app.messagebox.showerror', lambda *a, **k: errores.append(a))
    def fallo(_):
        raise ValueError('resultado de prueba')
    app.ejecutar(lambda: 1, fallo, 'Primera operación')
    esperar(app, lambda: bool(errores))
    resultado = []
    app.ejecutar(lambda: 2, resultado.append, 'Segunda operación')
    esperar(app, lambda: resultado == [2])
    assert not app._ocupada
    assert not app._estado_operacion.winfo_ismapped()


def test_carpeta_externa_mayusculas_refresca_todos_los_visores(app, tmp_path):
    import shutil
    carpeta = tmp_path / 'externa'
    carpeta.mkdir()
    for nombre in ['ingreso_iva.xml', 'pago_rep_basico.xml', 'nomina_basica.xml']:
        shutil.copy2(Path(__file__).parent / 'fixtures' / nombre, carpeta / nombre.upper())
    boveda = app._pantallas['boveda']
    boveda._origen.set(str(carpeta))
    boveda._origen_externo = True
    boveda._actualizar_lista()
    assert len(boveda._archivos_actuales) == 3
    for clave in ['admin40', 'pagos', 'nomina']:
        visor = app._pantallas[clave]
        visor._filtros['uuid'].insert(0, 'NO-EXISTE')
    resultado = boveda._run_carga(boveda._archivos_actuales, False, 'C1')
    assert resultado.insertados == 3
    boveda._presentar_carga(resultado)
    for clave in ['admin40', 'pagos', 'nomina']:
        visor = app._pantallas[clave]
        assert visor._cliente_cargado == 'C1'
        assert visor._tabla.get_children(), clave
        assert not visor._hay_busqueda_activa()


def test_error_importacion_se_muestra_sin_ocultar_xml_validos(app, tmp_path, monkeypatch):
    import shutil
    carpeta = tmp_path / 'mixta'
    carpeta.mkdir()
    shutil.copy2(Path(__file__).parent / 'fixtures' / 'ingreso_iva.xml', carpeta / 'factura.xml')
    (carpeta / 'incorrecto.xml').write_text('<archivo/>')
    avisos = []
    monkeypatch.setattr('conxml.ui.pantalla_boveda.messagebox.showwarning', lambda titulo, texto, **k: avisos.append(texto))
    boveda = app._pantallas['boveda']
    resultado = boveda._run_carga([carpeta], False, 'C1')
    boveda._presentar_carga(resultado)
    assert resultado.insertados == 1 and resultado.errores == 1
    assert 'incorrecto.xml' in avisos[0]
    assert app._pantallas['admin40']._tabla.get_children()


def test_carga_externa_de_xml_previamente_importados_en_otro_cliente(app, tmp_path):
    with Catalogo(app.db_path) as cat:
        from conxml.catalog.importer import importar_carpeta as importar
        importar(cat, Path(__file__).parent / 'fixtures', 'Otro')
    boveda = app._pantallas['boveda']
    resultado = boveda._run_carga([Path(__file__).parent / 'fixtures'], False, 'C1')
    assert resultado.asociados > 0
    boveda._presentar_carga(resultado)
    for clave in ['admin40', 'pagos', 'nomina']:
        app.navegar(clave)
        app.master.update()
        assert app._pantallas[clave]._tabla.get_children(), clave


def test_todas_las_tablas_comparten_diseno_y_historial_conserva_solicitud(app):
    from conxml.ui.tabla_visor import TablaVisor
    for clave in ['clientes', 'boveda', 'descargas', 'admin40', 'pagos', 'nomina']:
        assert isinstance(app._pantallas[clave]._tabla, TablaVisor), clave
    pantalla = app._pantallas['descargas']
    fila = dict(id_sat='SOL-1', fecha_inicial='2026-10-01', fecha_final='2026-10-13',
                estado=1, direccion='Recibidos', numero_cfdis=2, mensaje='', cod_estatus='5000')
    pantalla._renderizar_historial([fila])
    pantalla._tabla.selection_set('SOL-1')
    pantalla._renderizar_historial([fila])
    assert pantalla._tabla.selection() == ('SOL-1',)
    assert pantalla._tabla.item('SOL-1', 'values')[0] == 'SOL-1'
