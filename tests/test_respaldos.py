import json
from pathlib import Path
import zipfile

import pytest

from conxml.catalog.db import Catalogo
from conxml.cfdi.parser import parse_comprobante
from conxml import estado_local
from conxml.respaldos import crear_respaldo, restaurar_respaldo, respaldo_automatico

FIXTURES = Path(__file__).parent / 'fixtures'


def preparar(base):
    with Catalogo(base / 'catalogo.db') as cat:
        cat.crear_cliente('C1', 'Cliente de prueba', 'EKU9003173C9')
        c = parse_comprobante(FIXTURES / 'ingreso_iva.xml')
        cat.insert_comprobante('C1', c)
    estado_local.guardar({'sesion': {'cliente': 'C1', 'pantalla': 'admin40'}, 'limpiar_al_leer': False}, base / 'preferencias.json')
    return c.uuid


def test_respaldo_autocontenido_restaura_xml_externo_y_sesion(tmp_path):
    base = tmp_path / 'original'
    uuid = preparar(base)
    (base / 'privada.key').write_text('no respaldar')
    (base / 'configuraciones').mkdir()
    (base / 'configuraciones' / 'columnas_cfdi.json').write_text('{"ocultas": ["ruta"]}')
    resultado = crear_respaldo(base, tmp_path / 'respaldo.zip')
    assert resultado.faltantes == []
    with zipfile.ZipFile(resultado.ruta) as z:
        assert 'privada.key' not in z.namelist()
    destino = tmp_path / 'recuperado'
    destino.mkdir()
    (destino / 'anterior.txt').write_text('conservar')
    previa = restaurar_respaldo(resultado.ruta, destino)
    assert (previa / 'anterior.txt').read_text() == 'conservar'
    assert estado_local.cargar(destino / 'preferencias.json')['sesion']['cliente'] == 'C1'
    with Catalogo(destino / 'catalogo.db') as cat:
        fila = dict(next(cat.consulta()))
        assert fila['uuid'] == uuid
        assert Path(fila['ruta']).is_relative_to(destino)
        assert Path(fila['ruta']).read_bytes() == (FIXTURES / 'ingreso_iva.xml').read_bytes()
        assert cat.obtener_cliente('C1')['nombre'] == 'Cliente de prueba'


def test_corrupto_no_toca_datos_actuales(tmp_path):
    base = tmp_path / 'datos'
    preparar(base)
    zip_original = crear_respaldo(base, tmp_path / 'bueno.zip').ruta
    with zipfile.ZipFile(zip_original) as z, zipfile.ZipFile(tmp_path / 'malo.zip', 'w') as malo:
        for n in z.namelist():
            malo.writestr(n, b'corrupto' if n == 'preferencias.json' else z.read(n))
    antes = (base / 'preferencias.json').read_bytes()
    with pytest.raises(ValueError, match='dañado'):
        restaurar_respaldo(tmp_path / 'malo.zip', base)
    assert (base / 'preferencias.json').read_bytes() == antes


def test_rechaza_rutas_fuera_del_respaldo(tmp_path):
    archivo = tmp_path / 'traversal.zip'
    with zipfile.ZipFile(archivo, 'w') as z:
        z.writestr('manifest.json', '{}')
        z.writestr('../fuera.txt', 'malicioso')
    with pytest.raises(ValueError, match='ruta'):
        restaurar_respaldo(archivo, tmp_path / 'datos')
    assert not (tmp_path / 'fuera.txt').exists()


def test_incluye_wal_y_registra_xml_faltante(tmp_path):
    base = tmp_path / 'datos'
    uuid = preparar(base)
    with Catalogo(base / 'catalogo.db') as cat:
        cat.conn.execute('UPDATE comprobantes SET ruta=? WHERE uuid=?', (str(tmp_path / 'ausente.xml'), uuid))
        cat.conn.commit()
        resultado = crear_respaldo(base)
    assert len(resultado.faltantes) == 1
    with zipfile.ZipFile(resultado.ruta) as z:
        manifest = json.loads(z.read('manifest.json'))
        assert manifest['xml_faltantes'] == resultado.faltantes
    restaurar_respaldo(resultado.ruta, tmp_path / 'restaurado')
    with Catalogo(tmp_path / 'restaurado' / 'catalogo.db') as cat:
        assert cat.contar('comprobantes') == 1


def test_retencion_no_borra_manuales_ni_anida_respaldos(tmp_path):
    preparar(tmp_path)
    manual = crear_respaldo(tmp_path, tmp_path / 'respaldos' / 'manual.zip').ruta
    for _ in range(3):
        ultimo = respaldo_automatico(tmp_path, conservar=2)
    assert manual.is_file()
    assert len(list((tmp_path / 'respaldos').glob('auto_*.zip'))) == 2
    with zipfile.ZipFile(ultimo.ruta) as z:
        assert not any(n.startswith('respaldos/') for n in z.namelist())


def test_preferencias_se_combinan_y_recuperan_sesion(tmp_path):
    ruta = tmp_path / 'preferencias.json'
    estado_local.guardar({'ocultar_instrucciones_boveda': True}, ruta)
    estado_local.guardar({'sesion': {'cliente': 'C1'}}, ruta)
    assert estado_local.cargar(ruta) == {'ocultar_instrucciones_boveda': True, 'sesion': {'cliente': 'C1'}}
