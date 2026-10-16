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


def test_resumen_aisla_clientes_e_incluye_uuid_compartidos(tmp_path):
    from conxml.cfdi import parse_comprobante

    with Catalogo(tmp_path / "catalogo.db") as cat:
        importar_carpeta(cat, FIXTURES, "A")
        compartido = parse_comprobante(FIXTURES / "ingreso_iva.xml")
        cat.insert_comprobante("B", compartido)
        cat.crear_cliente("VACIO", "Sin XML")
        cat.asignar_estatus(compartido.uuid, "Vigente")
        cat.conn.execute("UPDATE comprobantes SET estatus = '' WHERE tipo_comprobante = 'E'")
        cat.registrar_error("ajeno.xml", "Error de otra importación")
        cat.commit()

        a, b, vacio = (cat.resumen_cliente(c) for c in ("A", "B", "VACIO"))
        assert a["total"] == 8
        assert b["total"] == 1
        assert b["estatus"]["Vigente"] == 1
        assert b["tipos"] == {"I": 1}
        assert b["desde"] == b["hasta"] == compartido.fecha.isoformat()
        assert b["ultima_validacion"]
        assert a["estatus"]["Sin validar"] == 7
        assert sum(a["estatus"].values()) == a["total"]
        assert vacio["total"] == 0
        assert vacio["desde"] is None
        assert vacio["cliente"]["nombre"] == "Sin XML"
        assert "errores" not in b


def test_resumen_solicitudes_solo_pendientes_del_cliente(tmp_path):
    with Catalogo(tmp_path / "catalogo.db") as cat:
        cat.crear_cliente("A", "Cliente A")
        for i, (cliente, estado, recuperado) in enumerate([
            ("A", 1, False), ("A", 2, False), ("A", 3, False),
            ("A", 3, True), ("A", 4, False), ("A", 5, False),
            ("A", 6, False), ("B", 3, False),
        ]):
            cat.guardar_solicitud_descarga(
                cliente=cliente, rfc="XAXX010101000", direccion="Recibidos",
                fecha_inicial="2026-01-01", fecha_final="2026-01-31", tipo_comprobante="",
                id_sat=str(i), cod_estatus="5000", estado=estado, mensaje="", recuperado=recuperado,
            )
        resumen = cat.resumen_cliente("A")
        assert resumen["descargas_pendientes"] == 2
        assert resumen["descargas_listas"] == 1
        assert resumen["total"] == 0
