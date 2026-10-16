"""Calendarios, ejecución sin GUI, archivo temporal y registro del sistema."""
import io
import json
import plistlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from conxml import estado_local
from conxml.catalog.db import Catalogo
from conxml.config import Config
from conxml.sat.archivo_solicitudes import conservar_paquete, exportar_paquetes, limpiar_vencidas, paquetes_locales
from conxml.sat.descarga_masiva import ErrorDescargaSAT, RespuestaSAT
from conxml.sat.periodicas import ejecutar_pendientes, guardar_plan, ocurrencia, plan_predeterminado, proximas, validar_plan

ZONA = ZoneInfo('America/Merida')


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setenv('CONXML_DATA_DIR', str(tmp_path))
    config = Config()
    with Catalogo(config.db_path) as cat:
        cat.crear_cliente('C1', 'Cliente', 'EKU9003173C9')
    return config


def plan_activo():
    plan = plan_predeterminado()
    plan.update(activo=True, desde='2026-10-13T00:00:00+00:00', direccion='Emitidos')
    return plan


def test_horarios_independientes_y_proximas_fechas():
    plan = plan_activo()
    viernes = datetime(2026, 10, 16, 16, tzinfo=ZONA)
    lunes = datetime(2026, 10, 19, 8, tzinfo=ZONA)
    assert ocurrencia(plan, 'solicitar', viernes - timedelta(minutes=1)) is None
    assert ocurrencia(plan, 'solicitar', viernes) == viernes
    assert ocurrencia(plan, 'revisar', viernes) is None
    assert proximas(plan, 'solicitar', datetime(2026, 10, 13, tzinfo=ZONA)) == viernes
    assert proximas(plan, 'revisar', viernes) == lunes
    plan['solicitar']['cada'] = 2
    assert ocurrencia(plan, 'solicitar', viernes + timedelta(weeks=1)) == viernes
    assert ocurrencia(plan, 'solicitar', viernes + timedelta(weeks=2)) == viernes + timedelta(weeks=2)


def test_intervalo_diario_hora_y_zona_validada():
    plan = plan_activo()
    plan['solicitar'].update(frecuencia='Diario', cada=2, hora='04:15')
    momento = datetime(2026, 10, 14, 4, 15, tzinfo=ZONA)
    assert ocurrencia(plan, 'solicitar', momento) == momento
    plan['solicitar']['hora'] = '25:00'
    with pytest.raises(ValueError): validar_plan(plan)


def test_guardar_no_reinicia_calendario_si_no_cambia(config):
    plan = plan_activo()
    guardar_plan(config, 'C1', plan)
    primero = estado_local.cargar()['sat_periodico']['C1']['desde']
    guardar_plan(config, 'C1', plan)
    assert estado_local.cargar()['sat_periodico']['C1']['desde'] == primero
    assert 'password' not in json.dumps(estado_local.cargar())


def paquete_xml():
    import zipfile
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archivo:
        archivo.writestr('factura.xml', (Path(__file__).parent / 'fixtures/ingreso_iva.xml').read_bytes())
    return stream.getvalue()


def test_ejecutor_solicita_revisa_organiza_y_no_duplica(config):
    estado_local.guardar({'sat_periodico': {'C1': plan_activo()}, 'descargas_sat': {'modo': 'zip'}})
    solicitudes, revisiones, descargas = [], [], []
    class SAT:
        def __init__(self, fiel): pass
        def solicitar(self, filtro):
            solicitudes.append(filtro)
            return RespuestaSAT(id_solicitud='SOL-1', cod_estatus='5000', mensaje='Aceptada')
        def verificar(self, rfc, solicitud):
            revisiones.append(solicitud)
            return RespuestaSAT(estado=3, cod_estatus='5000', paquetes=['P1'], numero_cfdis=1)
        def descargar_paquete(self, rfc, paquete):
            descargas.append(paquete)
            return paquete_xml()
        def cerrar(self): pass
    firma = lambda *args: SimpleNamespace(rfc='EKU9003173C9')
    viernes = datetime(2026, 10, 16, 16, tzinfo=ZONA)
    assert ejecutar_pendientes(config, viernes, firma=firma, fabrica_sat=SAT)[0]['estado'] == 'completada'
    assert len(solicitudes) == 1
    assert solicitudes[0].fecha_inicial.isoformat() == '2026-10-09'
    assert solicitudes[0].fecha_final.isoformat() == '2026-10-15'
    assert ejecutar_pendientes(config, viernes, firma=firma, fabrica_sat=SAT) == []
    assert revisiones == []
    lunes = datetime(2026, 10, 19, 8, tzinfo=ZONA)
    resultado = ejecutar_pendientes(config, lunes, firma=firma, fabrica_sat=SAT)
    assert resultado[0]['tarea'] == 'revisar'
    assert resultado[0]['estado'] == 'completada'
    assert revisiones == ['SOL-1'] and descargas == ['P1']
    with Catalogo(config.db_path) as cat:
        assert cat.obtener_solicitud_descarga('SOL-1')['recuperado'] == 1
        assert cat.contar('comprobantes') == 1
    assert list(config.carpeta_boveda.rglob('*.xml'))
    assert len(paquetes_locales(config, 'C1', 'SOL-1')) == 1
    assert ejecutar_pendientes(config, lunes, firma=firma, fabrica_sat=SAT) == []


def test_envio_incierto_no_se_repite_automaticamente(config):
    estado_local.guardar({'sat_periodico': {'C1': plan_activo()}})
    sat = Mock()
    sat.solicitar.side_effect = ErrorDescargaSAT('Conexión interrumpida')
    fabrica = lambda _: sat
    momento = datetime(2026, 10, 16, 16, tzinfo=ZONA)
    primero = ejecutar_pendientes(config, momento, firma=lambda *a: object(), fabrica_sat=fabrica)
    assert primero[0]['estado'] == 'error'
    assert ejecutar_pendientes(config, momento + timedelta(minutes=1), firma=lambda *a: object(), fabrica_sat=fabrica) == []
    sat.solicitar.assert_called_once()


def test_retencion_desde_creacion_y_conserva_boveda(config, tmp_path):
    ahora = datetime(2026, 10, 19, 8)
    with Catalogo(config.db_path) as cat:
        for solicitud in ('VIEJA', 'NUEVA'):
            cat.guardar_solicitud_descarga(cliente='C1', rfc='EKU9003173C9', direccion='Emitidos', fecha_inicial='2020-01-01',
                fecha_final='2020-01-02', tipo_comprobante='', id_sat=solicitud, cod_estatus='5000', estado=3, mensaje='Lista')
        cat.conn.execute('UPDATE solicitudes_descarga SET creada_en=? WHERE id_sat=?', ((ahora - timedelta(days=14)).isoformat(), 'VIEJA'))
        cat.conn.execute('UPDATE solicitudes_descarga SET creada_en=? WHERE id_sat=?', ((ahora - timedelta(days=13)).isoformat(), 'NUEVA'))
        cat.commit()
    for solicitud in ('VIEJA', 'NUEVA'):
        conservar_paquete(paquete_xml(), config, 'C1', solicitud, 'P1')
    config.carpeta_boveda.mkdir(parents=True)
    archivo = config.carpeta_boveda / 'permanente.xml'; archivo.write_text('conservar')
    assert limpiar_vencidas(config, config.db_path, ahora) == 1
    assert not paquetes_locales(config, 'C1', 'VIEJA')
    assert paquetes_locales(config, 'C1', 'NUEVA')
    assert archivo.read_text() == 'conservar'
    destino = tmp_path / 'salida.zip'
    exportar_paquetes(paquetes_locales(config, 'C1', 'NUEVA'), destino)
    assert destino.read_bytes() == paquete_xml()
    exportar_paquetes(paquetes_locales(config, 'C1', 'NUEVA'), tmp_path / 'xml', xml=True)
    assert list((tmp_path / 'xml').rglob('*.xml'))


def test_programador_mac_sin_secretos(config, tmp_path, monkeypatch):
    import conxml.sat.programador_sistema as sistema
    monkeypatch.setattr(sistema.sys, 'platform', 'darwin')
    monkeypatch.setattr(sistema.os, 'getuid', lambda: 501, raising=False)
    monkeypatch.setattr(sistema.Path, 'home', lambda: tmp_path / 'home')
    ejecutar = Mock(); monkeypatch.setattr(sistema, '_ejecutar', ejecutar)
    sistema.instalar(config)
    ruta = next((tmp_path / 'home/Library/LaunchAgents').glob('*.plist'))
    datos = plistlib.loads(ruta.read_bytes())
    assert datos['StartInterval'] == 60 and datos['RunAtLoad']
    assert str(config.base) in datos['ProgramArguments']
    assert 'password' not in ruta.read_text()
    assert ejecutar.call_args.args[0] == ['launchctl', 'bootstrap', 'gui/501', str(ruta)]
    sistema.desinstalar(config)
    assert not ruta.exists()


def test_bloqueo_excluye_otro_ejecutor(config):
    from conxml.sat.periodicas import bloqueo
    with bloqueo(config) as primero:
        assert primero
        with bloqueo(config) as segundo:
            assert not segundo


def test_seguimiento_manual_respeta_dia_de_revision_periodica(config):
    estado_local.guardar({'sat_periodico': {'C1': plan_activo()}})
    sat = Mock(); sat.solicitar.return_value = RespuestaSAT(id_solicitud='SOL-P',cod_estatus='5000')
    ejecutar_pendientes(config, datetime(2026,10,16,16,tzinfo=ZONA), firma=lambda *a:object(), fabrica_sat=lambda _:sat)
    with Catalogo(config.db_path) as cat:
        assert len(cat.solicitudes_descarga_pendientes({'EKU9003173C9'})) == 1
        assert cat.solicitudes_descarga_pendientes({'EKU9003173C9'}, incluir_periodicas=False) == []


def test_seleccion_sat_es_fila_e_icono_accion(tmp_path, monkeypatch):
    import tkinter as tk
    import customtkinter as ctk
    from conxml.ui.pantalla_descargas import PantallaDescargas
    monkeypatch.setenv('CONXML_DATA_DIR', str(tmp_path))
    try:
        root=ctk.CTk()
    except tk.TclError:
        pytest.skip('Sin display')
    try:
        root.geometry('1100x800')
        app=SimpleNamespace(cliente_actual='C1',_ocupada=False)
        pantalla=PantallaDescargas(root,app);pantalla.pack(fill='both',expand=True)
        pantalla._renderizar_historial([dict(id_sat='SOL',fecha_inicial='2026-10-01',fecha_final='2026-10-10',
            direccion='Emitidos',estado=3,numero_cfdis=2,mensaje='Lista',cod_estatus='5000')])
        root.update()
        tabla=pantalla._tabla
        tabla._seleccionar_fila(SimpleNamespace(widget=tabla.sheet.MT,x=20,y=10))
        root.update()
        assert tabla.selection()==('SOL',)
        assert tabla.sheet.get_selected_rows()=={0}
        assert tabla.sheet.get_selected_cells()==set()
        assert tabla.sheet.MT.xview()==(0.0,1.0)
        assert len(tabla.sheet.MT.find_withtag('conxml_bajar'))==1
        llamadas=[];pantalla._bajar=llamadas.append
        x=(tabla.sheet.MT.col_positions[6]+tabla.sheet.MT.col_positions[7])/2
        pantalla._clic_bajar(SimpleNamespace(widget=tabla.sheet.MT,x=x,y=10))
        assert llamadas==['SOL']
    finally:
        root.destroy()
