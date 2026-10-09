"""Tests del lote de estatus con el cliente SOAP simulado (sin red)."""

import shutil
from pathlib import Path

import pytest

from conxml.catalog.db import Catalogo
from conxml.catalog.importer import importar_carpeta
from conxml.sat.estatus import ConfigLote, consultar_lote
from conxml.sat.soap import ResultadoEstatus

FIXTURES = Path(__file__).parent / "fixtures"


def _poblada(tmp_path):
    catalogo = Catalogo(tmp_path / "catalogo.db")
    importar_carpeta(catalogo, FIXTURES, "1")
    return catalogo


def test_lote_guarda_cache_y_no_reconsulta(monkeypatch, tmp_path):
    catalogo = _poblada(tmp_path)
    uuids = {f["uuid"] for f in catalogo.consulta()}
    estados = {}
    for item in catalogo.consulta():
        estados[item["uuid"]] = ResultadoEstatus(
            estado="Cancelado" if item["tipo_comprobante"] == "E" else "Vigente"
        )
    llamadas: list[str] = []

    def fake_con_registro(**kwargs):
        llamadas.append(kwargs["uuid"])
        return estados[kwargs["uuid"]]

    monkeypatch.setattr("conxml.sat.estatus.consultar", fake_con_registro)

    config = ConfigLote(delay_segundos=0)
    res1 = consultar_lote(catalogo, config=config)

    assert res1.consultados == len(uuids)
    assert res1.vigentes == 7  # 6 fixtures de ingreso/traslado/REP + 1 nómina
    assert res1.cancelados == 1  # egreso
    assert len(llamadas) == len(uuids)

    sin_estatus = list(catalogo.consulta(sin_estatus=True))
    assert sin_estatus == []

    ll_antes = len(llamadas)
    res2 = consultar_lote(catalogo, config=config)
    assert res2.consultados == 0
    assert len(llamadas) == ll_antes  # no re-consulta la caché

    res_force = consultar_lote(catalogo, config=config, force=True)
    assert res_force.consultados == len(uuids)


def test_lote_fallos_no_marcan_y_se_reintentan(monkeypatch, tmp_path):
    catalogo = _poblada(tmp_path)
    estados = {
        f["uuid"]: ResultadoEstatus(estado="Vigente")
        for f in catalogo.consulta()
    }
    llamadas: list[str] = []

    def fake(**kwargs):
        llamadas.append(kwargs["uuid"])
        if kwargs["uuid"] == "F0E1D2C3-B4A5-4698-7C6D-5E4F3A2B1C0D":
            raise RuntimeError("red caída")
        return estados[kwargs["uuid"]]

    monkeypatch.setattr("conxml.sat.estatus.consultar", fake)

    res = consultar_lote(catalogo, config=ConfigLote(delay_segundos=0))
    assert res.fallos == 1
    assert res.consultados == 7

    pendientes = list(catalogo.consulta(sin_estatus=True))
    assert len(pendientes) == 1
    assert pendientes[0]["uuid"] == "F0E1D2C3-B4A5-4698-7C6D-5E4F3A2B1C0D"


def test_estado_no_final_no_envenena_la_cache(monkeypatch, tmp_path):
    catalogo = _poblada(tmp_path)
    total = sum(1 for _ in catalogo.consulta())

    def fake(**kwargs):
        return ResultadoEstatus(estado="Desconocido")

    monkeypatch.setattr("conxml.sat.estatus.consultar", fake)

    res = consultar_lote(catalogo, config=ConfigLote(delay_segundos=0))
    assert res.consultados == total
    assert res.desconocidos == total
    assert res.fallos == 0

    pendientes = list(catalogo.consulta(sin_estatus=True))
    assert len(pendientes) == total  # nada se marcó como estado final


def test_lote_solo_cliente_seleccionado(tmp_path, monkeypatch):
    # conjuntos disjuntos para que cada cliente tenga UUIDs propios
    grupo1 = ["ingreso_iva.xml", "ingreso_sin_iva.xml", "ingreso_descuento.xml"]
    grupo2 = [
        "ingreso_traslados_mult.xml",
        "egreso_nota_credito.xml",
        "pago_rep_basico.xml",
        "pago_rep_multiple.xml",
    ]
    catalogo = Catalogo(tmp_path / "catalogo.db")

    def importar_grupo(nombre_carpeta: str, archivos: list[str], cliente: str) -> None:
        carpeta = tmp_path / nombre_carpeta
        carpeta.mkdir(parents=True, exist_ok=True)
        for archivo in archivos:
            shutil.copy2(FIXTURES / archivo, carpeta / archivo)
        importar_carpeta(catalogo, carpeta, cliente)

    importar_grupo("c1", grupo1, "1")
    importar_grupo("c2", grupo2, "2")

    def fake(**kwargs):
        return ResultadoEstatus(estado="Vigente")

    monkeypatch.setattr("conxml.sat.estatus.consultar", fake)

    res = consultar_lote(catalogo, config=ConfigLote(delay_segundos=0), cliente="2")
    assert res.consultados == 4
    pendientes_cliente1 = list(catalogo.consulta(cliente="1", sin_estatus=True))
    assert len(pendientes_cliente1) == 3  # el cliente 1 no fue tocado

def test_validacion_paralela_acotada_con_cache_y_progreso(tmp_path, monkeypatch):
    import threading
    catalogo = _poblada(tmp_path)
    barrera = threading.Barrier(3, timeout=4)
    lock = threading.Lock()
    sesiones = {}
    llamadas = []
    propietario = threading.get_ident()
    asignar = catalogo.asignar_estatus

    def guardar(*args, **kwargs):
        assert threading.get_ident() == propietario
        return asignar(*args, **kwargs)

    def fake(**kwargs):
        hilo = threading.get_ident()
        with lock:
            anteriores = sesiones.setdefault(hilo, set())
            anteriores.add(id(kwargs['session']))
            llamadas.append(kwargs['uuid'])
            primero = len(llamadas) <= 3
        if primero:
            barrera.wait()
        return ResultadoEstatus(estado='Vigente')

    monkeypatch.setattr(catalogo, 'asignar_estatus', guardar)
    monkeypatch.setattr('conxml.sat.estatus.consultar', fake)
    progreso = []
    resultado = consultar_lote(catalogo, ConfigLote(delay_segundos=0, trabajadores=3, reintentos=0),
                               progreso=lambda i, n: progreso.append((i, n)))
    assert resultado.fallos == 0
    assert resultado.consultados == len(llamadas) == 8
    assert len(sesiones) == 3
    assert len(set.union(*sesiones.values())) == 3
    assert all(len(ids) == 1 for ids in sesiones.values())
    assert progreso == [(i, 8) for i in range(1, 9)]
    assert not list(catalogo.consulta(sin_estatus=True))
    assert consultar_lote(catalogo, ConfigLote(delay_segundos=0, trabajadores=3)).consultados == 0
    catalogo.close()


def test_validacion_restringida_a_uuids_y_conjunto_vacio(tmp_path, monkeypatch):
    catalogo = _poblada(tmp_path)
    uuids = {fila['uuid'] for fila in catalogo.consulta(tipo='N')}
    llamadas = []

    def fake(**kwargs):
        llamadas.append(kwargs['uuid'])
        return ResultadoEstatus(estado='Vigente')

    monkeypatch.setattr('conxml.sat.estatus.consultar', fake)
    config = ConfigLote(delay_segundos=0, trabajadores=3)
    assert consultar_lote(catalogo, config, uuids=set()).consultados == 0
    assert consultar_lote(catalogo, config, uuids=uuids).consultados == len(uuids)
    assert set(llamadas) == uuids
    assert all(fila['tipo_comprobante'] != 'N' for fila in catalogo.consulta(sin_estatus=True))
    catalogo.close()


def test_fallo_paralelo_no_impide_guardar_otros_resultados(tmp_path, monkeypatch):
    catalogo = _poblada(tmp_path)
    pendiente = next(iter(catalogo.consulta()))['uuid']

    def fake(**kwargs):
        if kwargs['uuid'] == pendiente:
            raise RuntimeError('Servicio no disponible')
        return ResultadoEstatus(estado='Vigente')

    monkeypatch.setattr('conxml.sat.estatus.consultar', fake)
    resultado = consultar_lote(catalogo, ConfigLote(delay_segundos=0, trabajadores=3, reintentos=0))
    assert resultado.consultados == 7 and resultado.fallos == 1
    assert [fila['uuid'] for fila in catalogo.consulta(sin_estatus=True)] == [pendiente]
    catalogo.close()


def test_reintento_respeta_espera_del_servicio(monkeypatch):
    import requests
    from conxml.sat.estatus import _consultar_con_reintentos
    llamadas = []
    esperas = []

    def fake(**kwargs):
        llamadas.append(kwargs)
        if len(llamadas) == 1:
            respuesta = requests.Response()
            respuesta.status_code = 429
            respuesta.headers['Retry-After'] = '5'
            raise requests.HTTPError(response=respuesta)
        return ResultadoEstatus(estado='Vigente')

    monkeypatch.setattr('conxml.sat.estatus.consultar', fake)
    monkeypatch.setattr('conxml.sat.estatus.time.sleep', esperas.append)
    with requests.Session() as sesion:
        estado = _consultar_con_reintentos(
            {'uuid': 'test', 'emisor_rfc': '', 'receptor_rfc': '', 'total': '0'},
            ConfigLote(delay_segundos=0.3), sesion)
    assert estado.es_vigente and esperas == [5]
