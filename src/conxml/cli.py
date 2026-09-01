"""Interfaz de línea de comandos (CLI) del gestor CFDI."""

from __future__ import annotations

import argparse
from pathlib import Path

from conxml.catalog.db import Catalogo
from conxml.catalog.importer import importar_carpeta
from conxml.config import Config
from conxml.export.listado import exportar_listado
from conxml.export.pagos import exportar_pagos
from conxml.sat.estatus import ConfigLote, consultar_lote
from conxml.semana import (
    ConfigSemana,
    detectar_clientes,
    mes_actual,
    mes_anterior,
    procesar_semana,
    ruta_config,
)


def _db_path(args) -> Path:
    return args.db if hasattr(args, "db") and getattr(args, "db", None) else Config().db_path


def _progreso(actual: int, total: int) -> None:
    print(f"\r  [{actual}/{total}]", end="", flush=True)


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="conxml",
        description="Gestor CFDI multi-RFC: importar, estatus SAT y reportes Excel",
    )
    subs = parser.add_subparsers(dest="comando")

    import_p = subs.add_parser("import", help="Importar XMLs de carpeta al catálogo")
    import_p.add_argument("carpeta", type=Path, help="Carpeta raíz con los XMLs")
    import_p.add_argument("cliente", type=str, help="Etiqueta del cliente")
    import_p.add_argument("--db", type=Path, default=None, help="Ruta de la BD SQLite")

    estatus_p = subs.add_parser("estatus", help="Validar estatus SAT en lote")
    estatus_p.add_argument("--cliente", type=str, default=None)
    estatus_p.add_argument("--force", action="store_true")
    estatus_p.add_argument("--delay", type=float, default=2.0)
    estatus_p.add_argument("--db", type=Path, default=None)

    export_p = subs.add_parser("export", help="Generar Excel")
    export_sub = export_p.add_subparsers(dest="formato", required=True)

    listado = export_sub.add_parser("listado", help="Listado general de comprobantes")
    listado.add_argument("destino", type=Path, help="Ruta del Excel de salida")
    listado.add_argument("--cliente", type=str, default=None)
    listado.add_argument("--desde", type=str, default=None, help="YYYY-MM-DD")
    listado.add_argument("--hasta", type=str, default=None, help="YYYY-MM-DD")
    listado.add_argument("--db", type=Path, default=None)

    pagos = export_sub.add_parser("pagos", help="Conciliación de pagos (REP)")
    pagos.add_argument("destino", type=Path, help="Ruta del Excel de salida")
    pagos.add_argument("--cliente", type=str, default=None)
    pagos.add_argument("--db", type=Path, default=None)

    semana_p = subs.add_parser("semana", help="Cola de trabajo semanal por cliente")
    semana_sub = semana_p.add_subparsers(dest="accion", required=True)

    detect = semana_sub.add_parser("detect", help="Detectar clientes y escribir config")
    detect.add_argument("raiz", type=Path, help="Carpeta raíz con la estructura cliente/Emitidas|Recibidas/AAAA/MM")
    detect.add_argument("--config", type=Path, default=None, help="Ruta del JSON de config")

    run = semana_sub.add_parser("run", help="Ejecutar la cola (importar, estatus, exportar)")
    run.add_argument("--config", type=Path, default=None, help="Ruta del JSON de config")
    run.add_argument("--periodo", type=str, default=None, help="AAAA-MM (por defecto el mes anterior)")
    run.add_argument("--delay", type=float, default=None, help="Segundos entre peticiones SAT")
    run.add_argument("--pausa", type=float, default=None, help="Pausa entre clientes")
    run.add_argument("--force", action="store_true", help="Revalidar todo")
    run.add_argument("--db", type=Path, default=None)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = construir_parser()
    args = parser.parse_args(argv)

    if args.comando is None:
        parser.print_help()
        return

    if args.comando == "import":
        with Catalogo(_db_path(args)) as catalogo:
            res = importar_carpeta(catalogo, args.carpeta, args.cliente)
        print(
            f"Procesados: {res.procesados} | Insertados: {res.insertados} | "
            f"Omitidos: {res.omitidos} | Errores: {res.errores}"
        )
        if res.detalle_errores:
            print("Errores:")
            for err in res.detalle_errores[:10]:
                print(f"  {err}")
    elif args.comando == "estatus":
        with Catalogo(_db_path(args)) as catalogo:
            config = ConfigLote(delay_segundos=args.delay)
            res = consultar_lote(
                catalogo, config=config, cliente=args.cliente, force=args.force, progreso=_progreso
            )
        print(
            f"\nConsultados: {res.consultados} | Vigentes: {res.vigentes} | "
            f"Cancelados: {res.cancelados} | No encontrados: {res.no_encontrados} | "
            f"Fallos: {res.fallos}"
        )
        if res.detalle:
            print("Fallos:")
            for fallo in res.detalle[:10]:
                print(f"  {fallo}")
    elif args.comando == "export":
        with Catalogo(_db_path(args)) as catalogo:
            if args.formato == "listado":
                destino = exportar_listado(
                    catalogo, args.destino, cliente=args.cliente, desde=args.desde, hasta=args.hasta
                )
                print(f"Listado exportado a {destino}")
            elif args.formato == "pagos":
                destino = exportar_pagos(catalogo, args.destino, cliente=args.cliente)
                print(f"Conciliación exportada a {destino}")
    elif args.comando == "semana":
        _cmd_semana(args)
    else:
        parser.print_help()


def _cmd_semana(args) -> None:
    config_path = args.config if args.config is not None else ruta_config(Path.cwd())

    if args.accion == "detect":
        clientes = detectar_clientes(args.raiz)
        if not clientes:
            print(f"No se detectaron clientes bajo {args.raiz}")
            return
        config = ConfigSemana(raiz=str(args.raiz), periodo=mes_anterior(), clientes=clientes)
        config.guardar(config_path)
        print(f"Config guardada en {config_path}")
        for etiqueta, info in clientes.items():
            print(f"  {etiqueta}: {', '.join(info['direcciones'])}")
        return

    config = ConfigSemana.cargar(config_path)
    if not config.raiz:
        print(f"No hay config en {config_path}. Usa: conxml semana detect <raiz>")
        return
    if args.periodo:
        config.periodo = args.periodo
    if not config.periodo:
        config.periodo = mes_anterior()
    if args.delay is not None:
        config.delay_segundos = args.delay
    if args.pausa is not None:
        config.pausa_segundos = args.pausa
    if args.force:
        config.forzar_revalidacion = True

    print(f"Periodo: {config.periodo} | Clientes: {', '.join(config.clientes)}")

    def _progreso_semana(etiqueta: str, etapa: str, actual: int, total: int) -> None:
        if not etiqueta:
            print(f"\r  Pausa {actual}/{total}", end="", flush=True)
            return
        if etapa in ("Importando", "Exportando", "Preparando", "Listo"):
            print(f"\r  [{etiqueta}] {etapa}...", end="", flush=True)
        elif etapa == "Validando":
            print(f"\r  [{etiqueta}] Validando {actual}/{total}...", end="", flush=True)

    res = procesar_semana(config, _db_path(args), progreso=_progreso_semana)
    print()
    for r in res.clientes:
        estado = "OK" if not r.notas else "AVISO"
        print(
            f"  [{estado}] {r.etiqueta}: "
            f"insertados {r.insertados}, omitidos {r.omitidos}, "
            f"validados {r.validados} (vigentes {r.vigentes}, cancelados {r.cancelados}), "
            f"fallos {r.fallos_validacion}"
        )
        for nota in r.notas[:3]:
            print(f"      - {nota}")
        if r.anomalias:
            print(f"      - anomalías: {len(r.anomalias)}")
        if r.export_listado:
            print(f"      - listado: {r.export_listado}")
        if r.export_pagos:
            print(f"      - pagos: {r.export_pagos}")
    if res.detenido:
        print("  Cola detenida por el usuario.")


if __name__ == "__main__":
    main()