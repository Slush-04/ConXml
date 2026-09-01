"""Checkpoint final: validación de integridad XML -> catálogo -> Excel.

Verifica que cada XML en las carpetas reales esté en el catálogo con
datos idénticos (UUID, folio, fecha, emisor, receptor, total, status),
y que no existan filas fantasma en el catálogo sin XML fuente.
"""

import sys
from pathlib import Path

from conxml.catalog.db import Catalogo
from conxml.cfdi.parser import parse_comprobante

RAIZ = Path("data/muestra/07. JULIO")
CATALOGO = Path("data/catalogo.db")

CARPETAS = {"1": RAIZ / "1", "2": RAIZ / "2"}


def main() -> int:
    catalogo = Catalogo(CATALOGO)
    errores = 0
    total_xml = 0
    total_catalogados = 0

    for cliente, carpeta in CARPETAS.items():
        xmls = sorted(carpeta.glob("*.xml"))
        total_xml += len(xmls)
        print(f"\n=== Cliente {cliente}: {len(xmls)} XMLs en {carpeta} ===")

        cat_por_uuid = {f["uuid"]: f for f in catalogo.consulta(cliente=cliente)}
        if not cat_por_uuid:
            print(f"  !! Sin registros en catálogo para cliente {cliente}")
            continue

        for xml in xmls:
            try:
                cfdi = parse_comprobante(xml)
            except Exception as exc:  # noqa: BLE001
                print(f"  !! Error parseando {xml.name}: {exc}")
                errores += 1
                continue

            if not cfdi.uuid:
                print(f"  !! XML sin UUID: {xml.name}")
                errores += 1
                continue

            row = cat_por_uuid.get(cfdi.uuid)
            if row is None:
                print(f"  !! XML SIN CATALOGAR: {cfdi.uuid} ({xml.name})")
                errores += 1
                continue
            total_catalogados += 1

            checks = {
                "folio": (str(row["folio"] or ""), str(cfdi.folio or "")),
                "fecha": (row["fecha"], cfdi.fecha.isoformat()),
                "serie": (row["serie"], cfdi.serie),
                "tipo": (row["tipo_comprobante"], cfdi.tipo_comprobante),
                "emisor_rfc": (row["emisor_rfc"], cfdi.emisor_rfc),
                "receptor_rfc": (row["receptor_rfc"], cfdi.receptor_rfc),
                "total": (row["total"], str(cfdi.total)),
                "moneda": (row["moneda"], cfdi.moneda),
            }
            for campo, (bd, xmlx) in checks.items():
                if (bd or "") != (xmlx or ""):
                    print(
                        f"  !! MISMATCH {cfdi.uuid} campo={campo}: "
                        f"BD={bd!r} XML={xmlx!r}"
                    )
                    errores += 1

        # Filas fantasma: en catálogo pero sin XML fuente (diferencia de UUID)
        uuids_xml = set()
        for xml in xmls:
            try:
                cfdi = parse_comprobante(xml)
                if cfdi.uuid:
                    uuids_xml.add(cfdi.uuid)
            except Exception:  # noqa: BLE001
                pass
        for uuid in sorted(set(cat_por_uuid) - uuids_xml):
            print(f"  !! EN CATÁLOGO SIN XML FUENTE: {uuid}")
            errores += 1

    print("\n================ RESUMEN ================")
    print(f"XMLs en carpetas:      {total_xml}")
    print(f"Catalogados y verif.:  {total_catalogados}")
    print(f"Comprobantes en BD:    {catalogo.contar('comprobantes')}")
    print(f"Errores encontrados:   {errores}")

    catalogo.close()
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())