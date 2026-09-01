"""Tests de la CLI: parsing de argumentos y comando semana."""

import shutil
from pathlib import Path

import pytest

from conxml.cli import construir_parser, main

FIXTURES = Path(__file__).parent / "fixtures"


def test_parser_import():
    p = construir_parser()
    args = p.parse_args(["import", "carpeta", "1"])
    assert args.comando == "import"
    assert args.carpeta.name == "carpeta"
    assert args.cliente == "1"


def test_parser_estatus_opciones():
    p = construir_parser()
    args = p.parse_args(["estatus", "--cliente", "2", "--force", "--delay", "1.0"])
    assert args.comando == "estatus"
    assert args.cliente == "2"
    assert args.force is True
    assert args.delay == 1.0


def test_parser_export_listado_con_periodo():
    p = construir_parser()
    args = p.parse_args(
        ["export", "listado", "salida.xlsx", "--cliente", "1", "--desde", "2026-07-01", "--hasta", "2026-07-31"]
    )
    assert args.formato == "listado"
    assert args.cliente == "1"
    assert args.desde == "2026-07-01"


def test_parser_export_pagos():
    p = construir_parser()
    args = p.parse_args(["export", "pagos", "pagos.xlsx", "--cliente", "2"])
    assert args.formato == "pagos"
    assert args.cliente == "2"


def test_parser_semana_detect():
    p = construir_parser()
    args = p.parse_args(["semana", "detect", "raiz"])
    assert args.accion == "detect"
    assert args.raiz.name == "raiz"


def test_parser_semana_run_opciones():
    p = construir_parser()
    args = p.parse_args(["semana", "run", "--periodo", "2026-07", "--delay", "1.5", "--pausa", "10", "--force"])
    assert args.accion == "run"
    assert args.periodo == "2026-07"
    assert args.delay == 1.5
    assert args.pausa == 10.0
    assert args.force is True


def _estructura(tmp_path):
    base = tmp_path / "raiz"
    for etiqueta, archivos in (("C1", ["ingreso_iva.xml", "pago_rep_basico.xml"]), ("C2", ["ingreso_sin_iva.xml"])):
        destino = base / etiqueta / "Emitidas" / "2026" / "07"
        destino.mkdir(parents=True)
        for nombre in archivos:
            shutil.copy(FIXTURES / nombre, destino)
    return base


def test_semana_detect_y_run(tmp_path, monkeypatch, capsys):
    from conxml.sat.soap import ResultadoEstatus

    monkeypatch.setattr(
        "conxml.sat.estatus.consultar",
        lambda **kw: ResultadoEstatus(estado="Vigente"),
    )
    base = _estructura(tmp_path)
    config = tmp_path / "semana.json"
    main(["semana", "detect", str(base), "--config", str(config)])
    assert config.is_file()
    assert "C1" in config.read_text(encoding="utf-8")

    main(
        [
            "semana", "run", "--config", str(config),
            "--periodo", "2026-07", "--delay", "0", "--pausa", "0",
            "--db", str(tmp_path / "c.db"),
        ]
    )
    out = capsys.readouterr().out
    assert "C1" in out
    assert "C2" in out
    assert (tmp_path / "c.db").is_file()


def test_main_sin_comando_muestra_ayuda(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    for sub in ("import", "estatus", "export", "semana"):
        assert sub in out