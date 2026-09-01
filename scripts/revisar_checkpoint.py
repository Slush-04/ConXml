"""Revisión rápida del contenido del catálogo para el checkpoint final."""

from conxml.catalog.db import Catalogo

c = Catalogo("data/catalogo.db")

print("=== ESTATUS DEL CATÁLOGO ===")
for est in c.conn.execute(
    "SELECT estatus, COUNT(*) FROM comprobantes GROUP BY estatus"
).fetchall():
    print(" ", est)

for cliente in ("1", "2"):
    filas = list(c.consulta(cliente=cliente))
    total = sum(float(f["total"]) for f in filas if f["total"])
    print(f"\n=== LISTADO CLIENTE {cliente} ({len(filas)} filas, total {total:,.2f}) ===")
    for f in filas:
        rec = f["receptor_nombre"] or f["receptor_rfc"]
        est = f["estatus"] or "SIN ESTATUS"
        print(
            f"  {f['folio'] or '-':>6} {f['fecha'][:10]} "
            f"{f['tipo_comprobante']} {f['serie'] or '-':<5} {f['emisor_rfc']}"
            f" -> {rec:<38} tot={f['total'] or 0:>10} [{est}]"
        )

print("\n=== PAGOS (conciliación) ===")
for pago in c.consultar_pagos():
    print(f"  Pago uuid={pago['comprobante_uuid']} fecha={pago['fecha_pago']} "
          f"monto={pago['monto']} cliente={pago['cliente']}")
    for doc in c.consultar_doctos(pago["id"]):
        fac = c.conn.execute(
            "SELECT estatus FROM comprobantes WHERE uuid=?", (doc["uuid_doc"],)
        ).fetchone()
        print(f"    Docto {doc['uuid_doc']} parcialidad={doc['num_parcialidad']} "
              f"sald_ant={doc['imp_saldo_ant']} pagado={doc['imp_pagado']} "
              f"insoluto={doc['imp_saldo_insoluto']} estatus_factura={fac[0] if fac else 'NO EN CATÁLOGO'}")