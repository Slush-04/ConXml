"""Tests de las mejoras (lotes 1-2 y deuda menor)."""

import shutil
from pathlib import Path

import pytest

from conxml.catalog.db import Catalogo
from conxml.catalog.importer import importar_carpeta
from conxml.export.comun import tasa_es
from conxml.export.listado import _base_por_factor, _importes
from conxml.ui.tabla_mixin import FILAS_POR_PAGINA, PaginacionMixin

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def catalogo_pagos(tmp_path):
    lib = Catalogo(tmp_path / "catalogo.db")
    carpeta = tmp_path / "cliente1"
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre in ["ingreso_iva.xml", "pago_rep_basico.xml", "pago_rep_multiple.xml"]:
        shutil.copy2(FIXTURES / nombre, carpeta / nombre)
    importar_carpeta(lib, carpeta, "1")
    yield lib
    lib.close()


def test_doctos_lote_equivale_a_unitarios(catalogo_pagos):
    pagos = list(catalogo_pagos.consultar_pagos())
    assert pagos, "se esperaban pagos en el fixture"
    lote = catalogo_pagos.consultar_doctos_lote([p["id"] for p in pagos])
    for pago in pagos:
        unitarios = catalogo_pagos.consultar_doctos(pago["id"])
        assert [d["uuid_doc"] for d in lote[pago["id"]]] == [
            d["uuid_doc"] for d in unitarios
        ]
    assert catalogo_pagos.consultar_doctos_lote([]) == {}


def test_tasa_cero_detecta_variantes():
    assert tasa_es("0", "0")
    assert tasa_es("0.00", "0")
    assert tasa_es("0.0", "0")
    assert not tasa_es(None, "0")
    assert not tasa_es("", "0")
    traslados = _importes(
        '[{"base": "100", "impuesto": "002", "tipo_factor": "Tasa", '
        '"tasa_o_cuota": "0.00", "importe": "0"}]'
    )
    assert _base_por_factor(traslados, "Tasa") == 100.0


def test_ruta_salida_neutraliza_traversal(tmp_path):
    from conxml.semana import _ruta_salida_segura

    salidas = tmp_path / "salidas"
    ok = _ruta_salida_segura(salidas, "Cliente 1", "listado", "2026-07")
    assert ok.parent == salidas.resolve()
    # Intento de traversal: se sanitiza y queda dentro de salidas
    neutral = _ruta_salida_segura(salidas, "../../evil", "listado", "2026-07")
    assert neutral.parent == salidas.resolve()
    assert ".." not in neutral.name


def test_paginacion_cien_por_pagina():
    assert FILAS_POR_PAGINA == 100

    class FakeTV:
        def __init__(self):
            self.rows = []

        def get_children(self):
            return list(self.rows)

        def delete(self, item):
            self.rows.remove(item)

        def insert(self, *a, **k):
            self.rows.append(k.get("values"))

        def heading(self, c):
            return {"text": c}

        def set(self, item, col):
            return ""

        def column(self, *a, **k):
            pass

        def __getitem__(self, k):
            return "#all" if k == "displaycolumns" else ["a"]

    class Host(PaginacionMixin):
        filas_por_pagina = 100

        def __init__(self):
            self._filas_pagina = [(i,) for i in range(250)]
            self._pagina = 0
            self._tabla = FakeTV()
            self._lbl_pagina = None

    host = Host()
    assert host.total_paginas() == 3
    host.mostrar_pagina(0)
    assert len(host._tabla.rows) == 100
    host.pagina_siguiente()
    assert host._tabla.rows[0] == (100,)
    host.mostrar_pagina(2)
    assert len(host._tabla.rows) == 50
    assert host.texto_pagina().startswith("201-250 de 250")


def test_reintentos_agotan_y_reintentan():
    from conxml.sat import estatus as est
    from conxml.sat.soap import ResultadoEstatus

    llamadas = {"n": 0}

    def _falla_y_luego_ok(**kwargs):
        llamadas["n"] += 1
        if llamadas["n"] < 3:
            raise ConnectionError("corte")
        return ResultadoEstatus(estado="Vigente")

    fila = {"uuid": "x", "emisor_rfc": "A", "receptor_rfc": "B", "total": "1"}
    config = est.ConfigLote(delay_segundos=0, reintentos=2, timeout=1.0)
    monkey = pytest.MonkeyPatch()
    monkey.setattr(est, "consultar", _falla_y_luego_ok)
    monkey.setattr(est.time, "sleep", lambda s: None)
    try:
        res = est._consultar_con_reintentos(fila, config=config, sesion=None)
    finally:
        monkey.undo()
    assert res.estado == "Vigente"
    assert llamadas["n"] == 3

    llamadas["n"] = 0
    monkey = pytest.MonkeyPatch()
    monkey.setattr(
        est, "consultar", lambda **k: (_ for _ in ()).throw(ConnectionError("siempre"))
    )
    monkey.setattr(est.time, "sleep", lambda s: None)
    try:
        with pytest.raises(ConnectionError):
            est._consultar_con_reintentos(
                fila, config=est.ConfigLote(delay_segundos=0, reintentos=1), sesion=None
            )
    finally:
        monkey.undo()
