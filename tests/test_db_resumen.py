"""Pruebas de las consultas de resumen del catálogo."""

from pathlib import Path

from conxml.catalog.db import Catalogo
from conxml.catalog.importer import importar_carpeta

FIXTURES = Path(__file__).parent / "fixtures"


def test_clientes_y_conteo_estatus(tmp_path):
    catalogo = Catalogo(tmp_path / "catalogo.db")
    importar_carpeta(catalogo, FIXTURES, "cliente b")

    assert catalogo.clientes() == ["cliente b"]
    assert catalogo.conteo_estatus() == {
        "Vigente": 0,
        "Cancelado": 0,
        "No Encontrado": 0,
        "Sin validar": 8,
    }

    for fila in catalogo.consulta():
        catalogo.conn.execute(
            "UPDATE comprobantes SET estatus = ? WHERE uuid = ?",
            ("Cancelado" if fila["tipo_comprobante"] == "E" else "Vigente", fila["uuid"]),
        )
    catalogo.conn.commit()

    conteo = catalogo.conteo_estatus()
    assert conteo["Vigente"] == 7
    assert conteo["Cancelado"] == 1
    assert conteo["Sin validar"] == 0

    catalogo.close()


def test_conteo_estatus_vacio(tmp_path):
    catalogo = Catalogo(tmp_path / "vacia.db")
    assert catalogo.conteo_estatus() == {
        "Vigente": 0,
        "Cancelado": 0,
        "No Encontrado": 0,
        "Sin validar": 0,
    }
    assert catalogo.clientes() == []
    catalogo.close()