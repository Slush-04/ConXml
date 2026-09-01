from datetime import datetime
from decimal import Decimal
from pathlib import Path

from conxml.cfdi import parse_comprobante
from conxml.cfdi.pagos import parse_pagos

FIXTURES = Path(__file__).parent / "fixtures"


def test_rep_standalone_basico():
    c = parse_comprobante(FIXTURES / "pago_rep_basico.xml")
    assert c.tipo_comprobante == "P"
    assert c.total == Decimal(0)

    pagos = parse_pagos(c)
    assert len(pagos) == 1

    pago = pagos[0]
    assert pago.fecha == datetime(2024, 2, 1, 10, 0, 0)
    assert pago.forma_pago == "03"
    assert pago.moneda == "MXN"
    assert pago.monto == Decimal("1160.00")
    assert pago.num_operacion == "TRF-88412"
    assert pago.tipo_cambio is None

    assert len(pago.doctos_relacionados) == 1
    doc = pago.doctos_relacionados[0]
    assert doc.uuid == "123E4567-E89B-12D3-A456-426614174000"
    assert doc.serie == "A"
    assert doc.folio == "124"
    assert doc.moneda == "MXN"
    assert doc.num_parcialidad == 1
    assert doc.imp_saldo_ant == Decimal("1160.00")
    assert doc.imp_pagado == Decimal("1160.00")
    assert doc.imp_saldo_insoluto == Decimal("0.00")


def test_rep_con_multiples_pagos_y_parcialidades():
    c = parse_comprobante(FIXTURES / "pago_rep_multiple.xml")
    pagos = parse_pagos(c)
    assert len(pagos) == 2

    pago_usd = pagos[0]
    assert pago_usd.moneda == "USD"
    assert pago_usd.tipo_cambio == Decimal("17.5000")
    assert pago_usd.monto == Decimal("300.00")
    assert pago_usd.rfc_emisor_cta_ord == "BBVA901234"
    assert pago_usd.cta_ordenante == "012180041100009999"
    assert len(pago_usd.doctos_relacionados) == 2
    assert [d.num_parcialidad for d in pago_usd.doctos_relacionados] == [1, 2]
    assert [d.imp_saldo_insoluto for d in pago_usd.doctos_relacionados] == [
        Decimal("300.00"),
        Decimal("200.00"),
    ]

    pago_mxn = pagos[1]
    assert pago_mxn.monto == Decimal("20000.00")
    assert pago_mxn.num_operacion is None
    assert len(pago_mxn.doctos_relacionados) == 2
    assert pago_mxn.doctos_relacionados[1].uuid == "5A6B7C8D-9E0F-4A1B-8C2D-3E4F5A6B7C8D"
    assert pago_mxn.doctos_relacionados[1].imp_saldo_insoluto == Decimal("0.00")


def test_factura_normal_no_trae_pagos():
    c = parse_comprobante(FIXTURES / "ingreso_iva.xml")
    assert parse_pagos(c) == []