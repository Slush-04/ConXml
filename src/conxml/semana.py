"""Cola de trabajo semanal: importar, validar y exportar por cliente en cadena.

Estructura de carpetas esperada (la misma que usa el despacho):
    <raiz>/<cliente>/Emitidas|Recibidas/<AAAA>/<MM>/...xml
Un cliente puede tener Emitidas, Recibidas o ambas. La cola procesa cada
cliente completo (importar -> validar estatus -> exportar Excel) antes de
pasar al siguiente, con pausa entre clientes para no castigar al SAT.
"""

from __future__ import annotations

import calendar
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from conxml.catalog.db import Catalogo
from conxml.catalog.importer import importar_carpeta
from conxml.export.listado import exportar_listado
from conxml.export.pagos import exportar_pagos
from conxml.sat.estatus import ConfigLote, consultar_lote

DIRECCIONES = ("Emitidas", "Recibidas")
_DEFAULT_CONFIG = "semana.json"


@dataclass
class ConfigSemana:
    raiz: str | Path = ""
    periodo: str = ""
    direcciones: tuple[str, ...] = DIRECCIONES
    pausa_segundos: float = 60.0
    delay_segundos: float = 2.0
    forzar_revalidacion: bool = False
    clientes: dict[str, dict] = field(default_factory=dict)

    def guardar(self, ruta: str | Path) -> None:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(
            json.dumps(
                {
                    "raiz": str(self.raiz),
                    "periodo": self.periodo,
                    "direcciones": list(self.direcciones),
                    "pausa_segundos": self.pausa_segundos,
                    "delay_segundos": self.delay_segundos,
                    "forzar_revalidacion": self.forzar_revalidacion,
                    "clientes": self.clientes,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    @classmethod
    def cargar(cls, ruta: str | Path) -> "ConfigSemana":
        ruta = Path(ruta)
        if not ruta.is_file():
            return cls()
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return cls(
            raiz=datos.get("raiz", ""),
            periodo=datos.get("periodo", ""),
            direcciones=tuple(datos.get("direcciones") or DIRECCIONES),
            pausa_segundos=datos.get("pausa_segundos", 60.0),
            delay_segundos=datos.get("delay_segundos", 2.0),
            forzar_revalidacion=datos.get("forzar_revalidacion", False),
            clientes=datos.get("clientes") or {},
        )


def ruta_config(base: Path) -> Path:
    return base / _DEFAULT_CONFIG


def detectar_clientes(raiz: str | Path) -> dict[str, dict]:
    """Descubre clientes bajo <raiz> con la estructura Emitidas/Recibidas/AAAA/MM.

    Devuelve {etiqueta: {'direcciones': [...]}}.
    """
    raiz = Path(raiz)
    descubiertos: dict[str, dict] = {}
    if not raiz.is_dir():
        return descubiertos
    for carpeta in sorted(p for p in raiz.iterdir() if p.is_dir()):
        direcciones = [d for d in DIRECCIONES if (carpeta / d).is_dir()]
        if direcciones:
            descubiertos[carpeta.name] = {"direcciones": direcciones}
    return descubiertos


def meses_disponibles(raiz: str | Path) -> list[str]:
    """Meses 'AAAA-MM' existentes en cualquier cliente, más reciente primero."""
    raiz = Path(raiz)
    meses: set[str] = set()
    if raiz.is_dir():
        for carpeta in raiz.iterdir():
            if not carpeta.is_dir():
                continue
            for direccion in DIRECCIONES:
                sub = carpeta / direccion
                if not sub.is_dir():
                    continue
                for anio in (p for p in sub.iterdir() if p.is_dir()):
                    for mes in (p for p in anio.iterdir() if p.is_dir()):
                        if re.fullmatch(r"\d{2}", mes.name):
                            meses.add(f"{anio.name}-{mes.name}")
    return sorted(meses, reverse=True)


def carpeta_cliente(raiz: str | Path, etiqueta: str, periodo: str,
                    direccion: str) -> Path:
    anio, mes = periodo.split("-")
    return Path(raiz) / etiqueta / direccion / anio / mes


def periodo_rango(periodo: str) -> tuple[str, str]:
    anio, mes = (int(p) for p in periodo.split("-"))
    ultimo = calendar.monthrange(anio, mes)[1]
    return f"{periodo}-01", f"{periodo}-{ultimo:02d}"


def _nombre_archivo(etiqueta: str, base: str, periodo: str) -> str:
    limpio = re.sub(r"[^A-Za-z0-9_-]+", "_", etiqueta).strip("_") or "cliente"
    return f"{limpio}_{base}_{periodo}.xlsx"


def _ruta_salida_segura(salidas: Path, etiqueta: str, base: str, periodo: str) -> Path:
    """Evita traversal (../../) aunque la etiqueta venga de config externa."""
    salidas = salidas.resolve()
    salidas.mkdir(parents=True, exist_ok=True)
    destino = (salidas / _nombre_archivo(etiqueta, base, periodo)).resolve()
    if destino.parent != salidas:
        raise ValueError(f"etiqueta insegura: {etiqueta!r}")
    return destino


@dataclass
class ResultadoCliente:
    etiqueta: str
    notas: list[str] = field(default_factory=list)
    insertados: int = 0
    omitidos: int = 0
    errores_importacion: int = 0
    validados: int = 0
    vigentes: int = 0
    cancelados: int = 0
    no_encontrados: int = 0
    fallos_validacion: int = 0
    export_listado: Path | None = None
    export_pagos: Path | None = None
    anomalias: list[str] = field(default_factory=list)


@dataclass
class ResultadoSemana:
    clientes: list[ResultadoCliente] = field(default_factory=list)
    detenido: bool = False


Progreso = Callable[[str, str, int, int], None]


def procesar_semana(
    config: ConfigSemana,
    db_path: str | Path,
    progreso: Progreso | None = None,
    debe_detenerse: Callable[[], bool] | None = None,
) -> ResultadoSemana:
    """Procesa los clientes marcados en cadena; cada cliente aislado de los demás."""
    resultado = ResultadoSemana()
    if not config.clientes:
        return resultado
    anio, mes = config.periodo.split("-")
    salidas = Path(db_path).parent / "salidas"
    with Catalogo(db_path) as catalogo:
        orden = _ordenar_por_pendientes(config, catalogo)

    for posicion, etiqueta in enumerate(orden):
        if debe_detenerse is not None and debe_detenerse():
            resultado.detenido = True
            break
        if progreso is not None:
            progreso(etiqueta, "Preparando", 0, 0)
        res = _procesar_cliente(config, db_path, etiqueta, salidas, anio, mes, progreso)
        resultado.clientes.append(res)
        if posicion < len(orden) - 1 and debe_detenerse is not None and debe_detenerse():
            resultado.detenido = True
            break
        if posicion < len(orden) - 1 and config.pausa_segundos > 0:
            _pausar(config.pausa_segundos, progreso, debe_detenerse)
            if debe_detenerse is not None and debe_detenerse():
                resultado.detenido = True
                break
    return resultado


def _ordenar_por_pendientes(config: ConfigSemana, catalogo_o_path) -> list[str]:
    """Clientes con más folios por validar primero.

    Acepta un Catalogo abierto (reutiliza la conexión) o un path (compat).
    """
    from conxml.catalog.db import Catalogo as _Catalogo

    if isinstance(catalogo_o_path, _Catalogo):
        return _ordenados(config, catalogo_o_path)
    with _Catalogo(catalogo_o_path) as catalogo:
        return _ordenados(config, catalogo)


def _ordenados(config: ConfigSemana, catalogo) -> list[str]:
    pendientes: dict[str, int] = {}
    for etiqueta in config.clientes:
        pendientes[etiqueta] = catalogo.contar_consulta(
            cliente=etiqueta, sin_estatus=not config.forzar_revalidacion
        )
    return sorted(config.clientes, key=lambda e: pendientes.get(e, 0), reverse=True)


def _procesar_cliente(config: ConfigSemana, db_path: str | Path, etiqueta: str,
                      salidas: Path, anio: str, mes: str,
                      progreso: Progreso | None) -> ResultadoCliente:
    res = ResultadoCliente(etiqueta=etiqueta)
    direcciones = config.clientes[etiqueta].get("direcciones") or config.direcciones
    carpetas = [
        c for d in direcciones
        if (c := carpeta_cliente(config.raiz, etiqueta, config.periodo, d)).is_dir()
    ]
    if not carpetas:
        res.notas.append(
            f"no se encontraron carpetas {anio}-{mes} bajo {etiqueta} "
            f"(direcciones: {', '.join(direcciones)})"
        )
        return res

    with Catalogo(db_path) as catalogo:
        for carpeta in carpetas:
            if progreso is not None:
                progreso(etiqueta, "Importando", 0, 0)
            imp = importar_carpeta(catalogo, carpeta, etiqueta)
            res.insertados += imp.insertados
            res.omitidos += imp.omitidos
            res.errores_importacion += imp.errores
            res.notas.extend(imp.detalle_errores[:3])

        pendientes = catalogo.contar_consulta(
            cliente=etiqueta, sin_estatus=not config.forzar_revalidacion
        )
        if pendientes:
            if progreso is not None:
                progreso(etiqueta, "Validando", 0, pendientes)
            lote = consultar_lote(
                catalogo,
                config=ConfigLote(delay_segundos=config.delay_segundos),
                cliente=etiqueta,
                force=config.forzar_revalidacion,
                progreso=(lambda a, t, e=etiqueta: progreso(e, "Validando", a, t))
                if progreso else None,
            )
            res.validados = lote.consultados
            res.vigentes = lote.vigentes
            res.cancelados = lote.cancelados
            res.no_encontrados = lote.no_encontrados
            res.fallos_validacion = lote.fallos
            res.notas.extend(lote.detalle[:3])

        desde, hasta = periodo_rango(config.periodo)
        filas = list(catalogo.consulta(cliente=etiqueta, desde=desde, hasta=hasta))
        res.anomalias = [
            f"{fila['estatus']} — {fila['uuid']}"
            for fila in filas
            if fila["estatus"] in ("Cancelado", "No Encontrado")
        ]

        if not filas:
            res.notas.append("sin comprobantes en el periodo")
            return res
        if progreso is not None:
            progreso(etiqueta, "Exportando", 0, 0)
        res.export_listado = exportar_listado(
            catalogo, _ruta_salida_segura(salidas, etiqueta, "listado", config.periodo),
            cliente=etiqueta, desde=desde, hasta=hasta,
        )
        if next(catalogo.consultar_pagos(cliente=etiqueta), None) is not None:
            res.export_pagos = exportar_pagos(
                catalogo, _ruta_salida_segura(salidas, etiqueta, "pagos", config.periodo),
                cliente=etiqueta,
            )
    if progreso is not None:
        progreso(etiqueta, "Listo", 0, 0)
    return res


def _pausar(segundos: float, progreso: Progreso | None,
            debe_detenerse: Callable[[], bool] | None) -> None:
    total = int(segundos)
    for s in range(total):
        if debe_detenerse is not None and debe_detenerse():
            return
        if progreso is not None:
            progreso("", "Pausa", s, total)
        time.sleep(1)


def mes_actual() -> str:
    return datetime.now().strftime("%Y-%m")


def mes_anterior() -> str:
    hoy = datetime.now()
    if hoy.month == 1:
        return f"{hoy.year - 1}-12"
    return f"{hoy.year}-{hoy.month - 1:02d}"