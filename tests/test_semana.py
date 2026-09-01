"""Tests de la cola de trabajo semanal (con SAT simulado, sin red)."""

import shutil
from pathlib import Path

from conxml.sat.soap import ResultadoEstatus
from conxml.semana import (
    ConfigSemana,
    carpeta_cliente,
    detectar_clientes,
    meses_disponibles,
    mes_actual,
    mes_anterior,
    periodo_rango,
    procesar_semana,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _estructura(tmp_path):
    """raiz/C1/{Emitidas,Recibidas}/2026/07 y raiz/C2/Emitidas/2026/07."""
    copias = {
        "C1": (["ingreso_iva.xml", "ingreso_sin_iva.xml", "pago_rep_basico.xml"], ["nomina_basica.xml"]),
        "C2": (["egreso_nota_credito.xml"], []),
    }
    base = tmp_path / "raiz"
    for etiqueta, (emitidas, recibidas) in copias.items():
        for direccion, archivos in (("Emitidas", emitidas), ("Recibidas", recibidas)):
            if not archivos:
                continue
            destino = base / etiqueta / direccion / "2026" / "07"
            destino.mkdir(parents=True)
            for nombre in archivos:
                ruta = FIXTURES / nombre
                if nombre == "egreso_nota_credito.xml":
                    texto = ruta.read_text(encoding="utf-8").replace(
                        'Fecha="2024-04-02T16:00:00"', 'Fecha="2026-07-02T16:00:00"'
                    )
                    (destino / nombre).write_text(texto, encoding="utf-8")
                else:
                    shutil.copy(ruta, destino)
    return base


def _sat_vigente(monkeypatch):
    monkeypatch.setattr(
        "conxml.sat.estatus.consultar",
        lambda **kw: ResultadoEstatus(estado="Vigente"),
    )


def test_detectar_clientes_y_meses(tmp_path):
    base = _estructura(tmp_path)
    clientes = detectar_clientes(base)
    assert set(clientes) == {"C1", "C2"}
    assert clientes["C1"]["direcciones"] == ["Emitidas", "Recibidas"]
    assert clientes["C2"]["direcciones"] == ["Emitidas"]
    assert meses_disponibles(base) == ["2026-07"]
    assert detectar_clientes(tmp_path / "inexistente") == {}
    assert meses_disponibles(tmp_path / "inexistente") == []


def test_carpeta_y_periodo(tmp_path):
    base = _estructura(tmp_path)
    carpeta = carpeta_cliente(base, "C1", "2026-07", "Emitidas")
    assert carpeta.is_dir() and carpeta.name == "07"
    assert periodo_rango("2026-02") == ("2026-02-01", "2026-02-28")
    assert periodo_rango("2026-08") == ("2026-08-01", "2026-08-31")
    from datetime import datetime
    hoy = datetime.now()
    esperado_ant = f"{hoy.year - 1}-12" if hoy.month == 1 else f"{hoy.year}-{hoy.month - 1:02d}"
    assert mes_actual() == hoy.strftime("%Y-%m")
    assert mes_anterior() == esperado_ant


def test_config_guardar_cargar(tmp_path):
    ruta = tmp_path / "semana.json"
    cfg = ConfigSemana(
        raiz="C:/xmls", periodo="2026-07", pausa_segundos=30.0,
        clientes={"C1": {"direcciones": ["Emitidas"]}},
    )
    cfg.guardar(ruta)
    cfg2 = ConfigSemana.cargar(ruta)
    assert cfg2.raiz == "C:/xmls"
    assert cfg2.periodo == "2026-07"
    assert cfg2.clientes == {"C1": {"direcciones": ["Emitidas"]}}
    assert ConfigSemana.cargar(tmp_path / "nada.json") == ConfigSemana()


def test_semana_completa(tmp_path, monkeypatch):
    base = _estructura(tmp_path)
    _sat_vigente(monkeypatch)

    cfg = ConfigSemana(
        raiz=base,
        periodo="2026-07",
        direcciones=("Emitidas", "Recibidas"),
        delay_segundos=0.0,
        pausa_segundos=0.0,
        clientes={"C1": {"direcciones": ["Emitidas", "Recibidas"]},
                  "C2": {"direcciones": ["Emitidas"]}},
    )
    etapas = []
    res = procesar_semana(
        cfg, tmp_path / "catalogo.db",
        progreso=lambda c, e, a, t: etapas.append((c, e)),
    )

    assert [c.etiqueta for c in res.clientes] == ["C1", "C2"]
    c1, c2 = res.clientes

    assert c1.insertados == 4
    assert c1.validados == 4
    assert c1.export_listado.is_file()
    assert c1.export_pagos is not None and c1.export_pagos.is_file()
    assert c2.insertados == 1
    assert c2.export_pagos is None
    assert not res.detenido

    marcados = [e for e, _ in etapas]
    assert marcados[0] == "C1"
    assert "Validando" in [e for c, e in etapas]


def test_semana_aisla_cliente_sin_carpeta(tmp_path, monkeypatch):
    base = _estructura(tmp_path)
    _sat_vigente(monkeypatch)
    cfg = ConfigSemana(
        raiz=base, periodo="2026-07", delay_segundos=0.0, pausa_segundos=0.0,
        clientes={"fantasma": {"direcciones": ["Emitidas"]},
                  "C2": {"direcciones": ["Emitidas"]}},
    )
    res = procesar_semana(cfg, tmp_path / "catalogo.db")
    fantasma, c2 = res.clientes
    assert not fantasma.insertados and fantasma.notas
    assert c2.insertados == 1
    assert c2.export_listado.is_file()


def test_semana_detener_entre_clientes(tmp_path, monkeypatch):
    base = _estructura(tmp_path)
    _sat_vigente(monkeypatch)
    cfg = ConfigSemana(
        raiz=base, periodo="2026-07", delay_segundos=0.0, pausa_segundos=0.0,
        clientes={"C1": {"direcciones": ["Emitidas"]},
                  "C2": {"direcciones": ["Emitidas"]}},
    )
    parar = {"valor": False}

    def detener():
        if parar["valor"]:
            return True
        parar["valor"] = True
        return False

    res = procesar_semana(cfg, tmp_path / "catalogo.db", debe_detenerse=detener)
    assert res.detenido
    assert len(res.clientes) == 1
    assert res.clientes[0].etiqueta == "C1"


def test_semana_sin_clientes(tmp_path):
    res = procesar_semana(ConfigSemana(periodo="2026-07"), tmp_path / "c.db")
    assert res.clientes == []
    assert not res.detenido