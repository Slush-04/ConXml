import shutil
import sqlite3
from pathlib import Path

import pytest

from conxml.catalog.db import Catalogo
from conxml.catalog.importer import importar_carpeta

FIXTURES = Path(__file__).parent / "fixtures"

XMLS_VALIDOS = [
    "ingreso_iva.xml",
    "ingreso_sin_iva.xml",
    "ingreso_descuento.xml",
    "ingreso_traslados_mult.xml",
    "egreso_nota_credito.xml",
    "pago_rep_basico.xml",
    "pago_rep_multiple.xml",
]


@pytest.fixture()
def catalogo(tmp_path):
    lib = Catalogo(tmp_path / "catalogo.db")
    yield lib
    lib.close()


def _copiar(nombre: str, destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIXTURES / nombre, destino / nombre)


def test_importa_carpeta_con_errores(catalogo, tmp_path):
    carpeta = tmp_path / "cliente1"
    for nombre in XMLS_VALIDOS:
        _copiar(nombre, carpeta)
    (carpeta / "basura.xml").write_text("esto no es xml", encoding="utf-8")

    res = importar_carpeta(catalogo, carpeta, "1")

    assert res.procesados == 8
    assert res.insertados == 7
    assert res.omitidos == 0
    assert res.errores == 1
    assert len(res.detalle_errores) == 1
    assert catalogo.contar("comprobantes") == 7
    assert catalogo.contar("errores") == 1


def test_reimportar_no_duplica(catalogo, tmp_path):
    carpeta = tmp_path / "cliente1"
    _copiar("ingreso_iva.xml", carpeta)

    res1 = importar_carpeta(catalogo, carpeta, "1")
    res2 = importar_carpeta(catalogo, carpeta, "1")

    assert res1.insertados == 1
    assert res2.insertados == 0
    assert res2.omitidos == 1
    assert catalogo.contar("comprobantes") == 1


def test_fallo_al_guardar_pagos_hace_rollback(catalogo, tmp_path, monkeypatch):
    carpeta = tmp_path / "cliente1"
    _copiar("pago_rep_basico.xml", carpeta)

    def fallar(self, comprobante_uuid, pagos):
        raise sqlite3.OperationalError("escritura simulada")

    monkeypatch.setattr(Catalogo, "_insert_pagos", fallar)
    res = importar_carpeta(catalogo, carpeta, "1")

    assert res.errores == 1
    assert catalogo.contar("comprobantes") == 0
    assert catalogo.contar("pagos") == 0

    monkeypatch.undo()
    res2 = importar_carpeta(catalogo, carpeta, "1")
    assert res2.insertados == 1
    assert catalogo.contar("comprobantes") == 1
    assert catalogo.contar("pagos") == 1


def test_pagos_y_doctos_relacionados_guardados(catalogo, tmp_path):
    carpeta = tmp_path / "cliente1"
    _copiar("pago_rep_multiple.xml", carpeta)

    importar_carpeta(catalogo, carpeta, "1")

    assert catalogo.contar("pagos") == 2
    assert catalogo.contar("doctos_relacionados") == 4

    pagos = list(catalogo.consultar_pagos())
    assert len(pagos) == 2
    assert pagos[0]["cliente"] == "1"
    doctos = catalogo.consultar_doctos(pagos[0]["id"])
    assert len(doctos) == 2
    assert doctos[0]["num_parcialidad"] == 1


def test_reimportar_completa_pagos_faltantes(catalogo, tmp_path):
    carpeta = tmp_path / "cliente1"
    _copiar("pago_rep_multiple.xml", carpeta)

    importar_carpeta(catalogo, carpeta, "1")
    base_pagos = catalogo.contar("pagos")
    assert base_pagos == 2

    catalogo.conn.execute("DELETE FROM pagos")
    catalogo.conn.commit()

    importar_carpeta(catalogo, carpeta, "1")
    assert catalogo.contar("pagos") == base_pagos  # backfill idempotente


def test_filtros_por_cliente_y_periodo(catalogo, tmp_path):
    carpeta = tmp_path / "cliente1"
    _copiar("ingreso_iva.xml", carpeta)  # 2024-02-01
    _copiar("pago_rep_basico.xml", carpeta)  # 2024-02-01
    _copiar("ingreso_traslados_mult.xml", carpeta)  # 2024-03-01
    importar_carpeta(catalogo, carpeta, "1")

    febrero = list(catalogo.consulta(cliente="1", desde="2024-02-01", hasta="2024-02-29"))
    assert len(febrero) == 2

    marzo = list(catalogo.consulta(cliente="1", desde="2024-03-01", hasta="2024-03-31"))
    assert len(marzo) == 1
    assert marzo[0]["moneda"] == "USD"

    tipo_p = list(catalogo.consulta(tipo="P"))
    assert len(tipo_p) == 1

    assert len(list(catalogo.consulta(cliente="inexistente"))) == 0


def test_comprobante_sin_timbre_se_registra_como_error(catalogo, tmp_path):
    carpeta = tmp_path / "cliente1"
    carpeta.mkdir(parents=True, exist_ok=True)
    xml_sin_tfd = (
        '<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
        'Version="4.0" Fecha="2024-01-01T00:00:00" SubTotal="0" Total="0" '
        'TipoDeComprobante="I" Exportacion="01" LugarExpedicion="45000">'
        "<cfdi:Emisor Rfc='XAXX010101000'/><cfdi:Receptor Rfc='XAXX010101000'/>"
        "</cfdi:Comprobante>"
    )
    (carpeta / "sin_tfd.xml").write_text(xml_sin_tfd, encoding="utf-8")

    res = importar_carpeta(catalogo, carpeta, "1")

    assert res.errores == 1
    assert res.insertados == 0
    assert "UUID" in res.detalle_errores[0]