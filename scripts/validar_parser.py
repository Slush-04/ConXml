"""Valida el parser contra XMLs reales de una carpeta.

Uso:
    python scripts/validar_parser.py [carpeta]

Parsea cada XML (CFDI 4.0 + complemento de pagos), reporta por archivo
y un resumen final con errores y estadísticas de coherencia.
"""

from __future__ import annotations

import sys
from pathlib import Path

from conxml.cfdi import CFDIParseError, parse_comprobante, parse_pagos


def validar(carpeta: Path) -> None:
    archivos = sorted(p for p in carpeta.rglob("*.xml") if "pago" not in p.name.lower())
    archivos += sorted(p for p in carpeta.rglob("*.xml"))
    # dedupe manteniendo el primer orden (facturas + REP mezclados)
    vistos: set[str] = set()
    unicos: list[Path] = []
    for p in archivos:
        if str(p) not in vistos:
            vistos.add(str(p))
            unicos.append(p)

    ok = 0
    errores: list[tuple[Path, str]] = []
    versiones: dict[str | None, int] = {}
    tipos: dict[str, int] = {}
    total_replectos = 0
    pagos_parseados = 0
    doctos_parseados = 0

    for archivo in unicos:
        try:
            c = parse_comprobante(archivo)
            pagos = parse_pagos(c)
            versiones[c.version] = versiones.get(c.version, 0) + 1
            tipos[c.tipo_comprobante] = tipos.get(c.tipo_comprobante, 0) + 1
            n_docs = sum(len(p.doctos_relacionados) for p in pagos)
            if pagos:
                total_replectos += 1
                pagos_parseados += len(pagos)
                doctos_parseados += n_docs
            print(
                f"[OK  ] {archivo.name}: v{c.version} tipo={c.tipo_comprobante} "
                f"uuid={c.uuid} total={c.total} pagos={len(pagos)} docs={n_docs}"
            )
            ok += 1
        except CFDIParseError as exc:
            errores.append((archivo, str(exc)))
            print(f"[ERR ] {archivo.name}: {exc}")
        except Exception as exc:  # noqa: BLE001 — reporte de checkpoint
            errores.append((archivo, f"excepción inesperada: {exc!r}"))
            print(f"[FATAL] {archivo.name}: {exc!r}")

    print("\n===== RESUMEN =====")
    print(f"Archivos procesados: {len(unicos)}  OK: {ok}  Errores: {len(errores)}")
    print(f"Versiones: {versiones}")
    print(f"Tipos: {tipos}")
    print(f"REP detectados: {total_replectos} (pagos: {pagos_parseados}, doctos: {doctos_parseados})")

    if errores:
        print("\n--- Errores por archivo ---")
        for archivo, mensaje in errores:
            print(f"{archivo}: {mensaje}")


if __name__ == "__main__":
    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/muestra")
    if not ruta.is_dir():
        sys.exit(f"La carpeta no existe: {ruta}")
    validar(ruta)