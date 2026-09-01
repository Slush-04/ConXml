from datetime import datetime
from decimal import Decimal
from pathlib import Path

from conxml.cfdi import parse_comprobante
from conxml.cfdi.nomina import Nomina, parse_nomina

FIXTURES = Path(__file__).parent / "fixtures"


def _nomina() -> Nomina:
    c = parse_comprobante(FIXTURES / "nomina_basica.xml")
    assert c.tipo_comprobante == "N"
    nomina = parse_nomina(c)
    assert nomina is not None
    return nomina


def test_factura_normal_no_trae_nomina():
    c = parse_comprobante(FIXTURES / "ingreso_iva.xml")
    assert parse_nomina(c) is None


def test_nomina_lee_encabezado():
    nomina = _nomina()
    assert nomina.tipo_nomina == "O"
    assert nomina.fecha_pago == datetime(2026, 7, 15)
    assert nomina.fecha_inicial_pago == datetime(2026, 7, 1)
    assert nomina.fecha_final_pago == datetime(2026, 7, 15)
    assert nomina.num_dias_pagados == Decimal("15.000")
    assert nomina.total_percepciones == Decimal("5434.44")
    assert nomina.total_deducciones == Decimal("198.42")
    assert nomina.total_otros_pagos == Decimal("0.00")


def test_nomina_lee_emisor_y_receptor():
    nomina = _nomina()
    assert nomina.registro_patronal == "A1023608108"
    assert nomina.curp == "GAGE670721HYNMRR00"
    assert nomina.num_empleado == "07"
    assert nomina.puesto == "Auxiliar de mantenimiento"
    assert nomina.periodicidad_pago == "04"
    assert nomina.salario_base_cot_apor == Decimal("335.30")
    assert nomina.salario_diario_integrado == Decimal("315.04")


def test_nomina_percepciones_con_totales():
    nomina = _nomina()
    assert nomina.total_sueldos == Decimal("5434.44")
    assert nomina.total_gravado == Decimal("4961.88")
    assert nomina.total_exento == Decimal("472.56")
    assert len(nomina.percepciones) == 2


def test_nomina_percepcion_simple():
    sueldo = _nomina().percepciones[0]
    assert sueldo.tipo_percepcion == "001"
    assert sueldo.clave == "001"
    assert sueldo.concepto == "Sueldo"
    assert sueldo.importe_gravado == Decimal("4725.60")
    assert sueldo.importe_exento == Decimal("0.00")
    assert sueldo.horas_extra is None


def test_nomina_percepcion_con_horas_extra():
    horas = _nomina().percepciones[1]
    assert horas.tipo_percepcion == "019"
    assert horas.concepto == "Horas extras"
    assert horas.importe_gravado == Decimal("236.28")
    assert horas.importe_exento == Decimal("472.56")
    assert horas.horas_extra is not None
    assert horas.horas_extra.dias == 2
    assert horas.horas_extra.tipo_horas == "01"
    assert horas.horas_extra.horas_extra == Decimal("9")
    assert horas.horas_extra.importe_pagado == Decimal("708.84")


def test_nomina_deducciones():
    nomina = _nomina()
    assert nomina.total_impuestos_retenidos == Decimal("98.42")
    assert len(nomina.deducciones) == 2

    isr = nomina.deducciones[0]
    assert isr.tipo_deduccion == "002"
    assert isr.clave == "045"
    assert isr.concepto == "ISR"
    assert isr.importe == Decimal("98.42")

    imss = nomina.deducciones[1]
    assert imss.tipo_deduccion == "001"
    assert imss.concepto == "IMSS"
    assert imss.importe == Decimal("100.00")


def test_exportar_nomina(tmp_path):
    from conxml.catalog.db import Catalogo
    from conxml.catalog.importer import importar_carpeta
    from conxml.export.nomina import exportar_nomina

    db_path = tmp_path / "test.db"
    excel_path = tmp_path / "nomina.xlsx"

    with Catalogo(db_path) as cat:
        importar_carpeta(cat, FIXTURES, "ClienteNomina")
        salida = exportar_nomina(cat, excel_path)
        assert salida.is_file()
        assert salida.stat().st_size > 0