"""Repositorio SQLite: esquema v1 del catálogo de CFDI."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from conxml.cfdi.models import Comprobante
from conxml.cfdi.pagos import Pago

SCHEMA = """
CREATE TABLE IF NOT EXISTS comprobantes (
    uuid TEXT PRIMARY KEY,
    cliente TEXT NOT NULL,
    ruta TEXT NOT NULL,
    version TEXT NOT NULL,
    serie TEXT,
    folio TEXT,
    fecha TEXT NOT NULL,
    tipo_comprobante TEXT NOT NULL,
    moneda TEXT NOT NULL,
    tipo_cambio TEXT,
    subtotal TEXT,
    descuento TEXT,
    iva TEXT,
    total TEXT,
    emisor_rfc TEXT,
    emisor_nombre TEXT,
    receptor_rfc TEXT,
    receptor_nombre TEXT,
    uso_cfdi TEXT,
    metodo_pago TEXT,
    forma_pago TEXT,
    tipo_relacion TEXT,
    relaciones TEXT,
    lugar_expedicion TEXT,
    regimen_fiscal_receptor TEXT,
    domicilio_fiscal_receptor TEXT,
    no_certificado_sat TEXT,
    no_certificado_emisor TEXT,
    conceptos TEXT,
    complementos TEXT,
    emisor_regimen_fiscal TEXT,
    fecha_timbrado TEXT,
    traslados_json TEXT,
    retenciones_json TEXT,
    estatus TEXT,
    estatus_fecha TEXT,
    es_cancelable TEXT,
    estatus_cancelacion TEXT,
    FOREIGN KEY (uuid) REFERENCES comprobantes(uuid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pagos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comprobante_uuid TEXT NOT NULL REFERENCES comprobantes(uuid) ON DELETE CASCADE,
    fecha_pago TEXT NOT NULL,
    forma_pago TEXT,
    moneda TEXT,
    monto TEXT,
    tipo_cambio TEXT,
    num_operacion TEXT,
    rfc_emisor_cta_ord TEXT,
    cta_ordenante TEXT,
    cta_beneficiario TEXT
);

CREATE TABLE IF NOT EXISTS doctos_relacionados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pago_id INTEGER NOT NULL REFERENCES pagos(id) ON DELETE CASCADE,
    uuid_doc TEXT NOT NULL,
    moneda TEXT,
    num_parcialidad INTEGER,
    imp_saldo_ant TEXT,
    imp_pagado TEXT,
    imp_saldo_insoluto TEXT,
    serie TEXT,
    folio TEXT
);

CREATE TABLE IF NOT EXISTS errores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ruta TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    fecha TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_comprobantes_cliente_fecha
    ON comprobantes(cliente, fecha);
CREATE INDEX IF NOT EXISTS idx_comprobantes_tipo_estatus
    ON comprobantes(tipo_comprobante, estatus);
CREATE INDEX IF NOT EXISTS idx_pagos_comprobante
    ON pagos(comprobante_uuid);
CREATE INDEX IF NOT EXISTS idx_doctos_pago
    ON doctos_relacionados(pago_id);
"""

_COLUMNAS = (
    "uuid, cliente, ruta, version, serie, folio, fecha, tipo_comprobante, moneda, "
    "tipo_cambio, subtotal, descuento, iva, total, emisor_rfc, emisor_nombre, receptor_rfc, "
    "receptor_nombre, uso_cfdi, metodo_pago, forma_pago, tipo_relacion, relaciones, "
    "lugar_expedicion, "
    "regimen_fiscal_receptor, domicilio_fiscal_receptor, no_certificado_sat, "
    "no_certificado_emisor, conceptos, complementos, emisor_regimen_fiscal, fecha_timbrado, "
    "traslados_json, retenciones_json, estatus, estatus_fecha, es_cancelable, "
    "estatus_cancelacion"
)

_NUEVAS_COLUMNAS = [
    ("cliente", "TEXT NOT NULL DEFAULT ''"),
    ("iva", "TEXT"),
    ("relaciones", "TEXT"),
    ("lugar_expedicion", "TEXT"),
    ("regimen_fiscal_receptor", "TEXT"),
    ("domicilio_fiscal_receptor", "TEXT"),
    ("no_certificado_sat", "TEXT"),
    ("no_certificado_emisor", "TEXT"),
    ("conceptos", "TEXT"),
    ("complementos", "TEXT"),
    ("emisor_regimen_fiscal", "TEXT"),
    ("fecha_timbrado", "TEXT"),
    ("traslados_json", "TEXT"),
    ("retenciones_json", "TEXT"),
    ("es_cancelable", "TEXT"),
    ("estatus_cancelacion", "TEXT"),
]


def _dec(valor: Decimal | None) -> str | None:
    return str(valor) if valor is not None else None


_TABLAS = frozenset({"comprobantes", "pagos", "doctos_relacionados", "errores"})


def _json(objetos: list[Any]) -> str | None:
    """Serializa traslados/retenciones como JSON (Decimal -> str)."""
    if not objetos:
        return None
    import dataclasses

    def _fila(o: Any) -> dict:
        if dataclasses.is_dataclass(o):
            data = dataclasses.asdict(o)  # compatible con slots=True
        else:
            data = o.__dict__
        return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in data.items()}

    return json.dumps([_fila(o) for o in objetos], ensure_ascii=False)


class Catalogo:
    """Conexión al repositorio SQLite con operaciones del catálogo."""

    def __init__(self, ruta: Path) -> None:
        self.ruta = ruta
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(ruta))
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            pass  # sistema de archivos sin soporte WAL; se sigue con el modo por defecto
        self.conn.execute("PRAGMA busy_timeout=10000")
        self.conn.executescript(SCHEMA)
        self._migrar_esquema()

    def _migrar_esquema(self) -> None:
        """Migraciones idempotentes para BD ya creadas con un esquema anterior."""
        columnas = {
            fila[1]
            for fila in self.conn.execute("PRAGMA table_info(comprobantes)").fetchall()
        }
        faltantes = [(nombre, tipo) for nombre, tipo in _NUEVAS_COLUMNAS if nombre not in columnas]
        for nombre, tipo in faltantes:
            self.conn.execute(f"ALTER TABLE comprobantes ADD COLUMN {nombre} {tipo}")
        if faltantes:
            self.conn.commit()

    def __enter__(self) -> "Catalogo":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    def insert_comprobante(
        self, cliente: str, comprobante: Comprobante, pagos: list[Pago] | None = None
    ) -> str:
        """Guarda un comprobante (y sus pagos). Dedupe por UUID.

        Devuelve 'inserted' o 'skipped' si el UUID ya existía.
        """
        columnas = _COLUMNAS.split(", ")
        try:
            cur = self.conn.execute(
                f"INSERT OR IGNORE INTO comprobantes ({_COLUMNAS}) "
                f"VALUES ({', '.join('?' for _ in columnas)})",
                (
                    comprobante.uuid,
                    cliente,
                    str(comprobante.ruta),
                    comprobante.version,
                    comprobante.serie,
                    comprobante.folio,
                    comprobante.fecha.isoformat(),
                    comprobante.tipo_comprobante,
                    comprobante.moneda,
                    _dec(comprobante.tipo_cambio),
                    _dec(comprobante.subtotal),
                    _dec(comprobante.descuento),
                    _dec(comprobante.iva),
                    _dec(comprobante.total),
                    comprobante.emisor_rfc,
                    comprobante.emisor_nombre,
                    comprobante.receptor_rfc,
                    comprobante.receptor_nombre,
                    comprobante.receptor_uso_cfdi,
                    comprobante.metodo_pago,
                    comprobante.forma_pago,
                    comprobante.tipo_relacion,
                    ", ".join(comprobante.relaciones) or None,
                    comprobante.lugar_expedicion,
                    comprobante.receptor_regimen_fiscal,
                    comprobante.receptor_domicilio_fiscal,
                    comprobante.no_certificado_sat,
                    comprobante.no_certificado_emisor,
                    " | ".join(comprobante.conceptos) or None,
                    ", ".join(comprobante.complementos) or None,
                    comprobante.emisor_regimen_fiscal,
                    comprobante.fecha_timbrado.isoformat() if comprobante.fecha_timbrado else None,
                    _json(comprobante.traslados),
                    _json(comprobante.retenciones),
                    None,
                    None,
                    None,
                    None,
                ),
            )
            if cur.rowcount == 0:
                self.actualizar_metadatos(comprobante.uuid, comprobante, commit=False)
                if comprobante.uuid and pagos:
                    self._completar_pagos_si_vacios(comprobante.uuid, pagos)
                self.conn.commit()
                return "skipped"
            if comprobante.uuid and pagos:
                self._insert_pagos(comprobante.uuid, pagos)
            self.conn.commit()
            return "inserted"
        except Exception:
            self.conn.rollback()
            raise

    def actualizar_metadatos(
        self, uuid: str, comprobante: Comprobante, commit: bool = True
    ) -> None:
        """Completa los metadatos nuevos de un comprobante ya existente.

        Solo escribe los campos que aún están vacíos (backfill idempotente),
        sin tocar el estatus, que pertenece al caché de consulta SAT.
        """
        self.conn.execute(
            "UPDATE comprobantes SET "
            "lugar_expedicion = COALESCE(lugar_expedicion, ?), "
            "regimen_fiscal_receptor = COALESCE(regimen_fiscal_receptor, ?), "
            "domicilio_fiscal_receptor = COALESCE(domicilio_fiscal_receptor, ?), "
            "no_certificado_sat = COALESCE(no_certificado_sat, ?), "
            "no_certificado_emisor = COALESCE(no_certificado_emisor, ?), "
            "conceptos = COALESCE(conceptos, ?), "
            "complementos = COALESCE(complementos, ?), "
            "relaciones = COALESCE(relaciones, ?), "
            "emisor_regimen_fiscal = COALESCE(emisor_regimen_fiscal, ?), "
            "fecha_timbrado = COALESCE(fecha_timbrado, ?), "
            "traslados_json = COALESCE(traslados_json, ?), "
            "retenciones_json = COALESCE(retenciones_json, ?) "
            "WHERE uuid = ?",
            (
                comprobante.lugar_expedicion,
                comprobante.receptor_regimen_fiscal,
                comprobante.receptor_domicilio_fiscal,
                comprobante.no_certificado_sat,
                comprobante.no_certificado_emisor,
                " | ".join(comprobante.conceptos) or None,
                ", ".join(comprobante.complementos) or None,
                ", ".join(comprobante.relaciones) or None,
                comprobante.emisor_regimen_fiscal,
                comprobante.fecha_timbrado.isoformat() if comprobante.fecha_timbrado else None,
                _json(comprobante.traslados),
                _json(comprobante.retenciones),
                uuid,
            ),
        )
        if commit:
            self.conn.commit()

    def _completar_pagos_si_vacios(self, comprobante_uuid: str, pagos: list[Pago]) -> None:
        """Backfill idempotente: solo inserta pagos si la factura no tiene ninguno.

        Repara datos corruptos de versiones anteriores (opcional: factura con
        comprobante guardado pero pagos nunca persistidos) sin duplicar.
        """
        existentes = self.conn.execute(
            "SELECT COUNT(*) FROM pagos WHERE comprobante_uuid = ?", (comprobante_uuid,)
        ).fetchone()[0]
        if existentes == 0:
            self._insert_pagos(comprobante_uuid, pagos)

    def _insert_pagos(self, comprobante_uuid: str, pagos: list[Pago]) -> None:
        for pago in pagos:
            cur = self.conn.execute(
                "INSERT INTO pagos (comprobante_uuid, fecha_pago, forma_pago, moneda, monto, "
                "tipo_cambio, num_operacion, rfc_emisor_cta_ord, cta_ordenante, cta_beneficiario) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    comprobante_uuid,
                    pago.fecha.isoformat(),
                    pago.forma_pago,
                    pago.moneda,
                    _dec(pago.monto),
                    _dec(pago.tipo_cambio),
                    pago.num_operacion,
                    pago.rfc_emisor_cta_ord,
                    pago.cta_ordenante,
                    pago.cta_beneficiario,
                ),
            )
            pago_id = cur.lastrowid
            for doc in pago.doctos_relacionados:
                self.conn.execute(
                    "INSERT INTO doctos_relacionados (pago_id, uuid_doc, moneda, num_parcialidad, "
                    "imp_saldo_ant, imp_pagado, imp_saldo_insoluto, serie, folio) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        pago_id,
                        doc.uuid,
                        doc.moneda,
                        doc.num_parcialidad,
                        _dec(doc.imp_saldo_ant),
                        _dec(doc.imp_pagado),
                        _dec(doc.imp_saldo_insoluto),
                        doc.serie,
                        doc.folio,
                    ),
                )

    def registrar_error(self, ruta: str | Path, mensaje: str) -> None:
        self.conn.execute(
            "INSERT INTO errores (ruta, mensaje, fecha) VALUES (?, ?, ?)",
            (str(ruta), mensaje, datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()

    def commit(self) -> None:
        """Confirma los cambios pendientes del lote actual."""
        self.conn.commit()

    def asignar_estatus(
        self,
        uuid: str,
        estatus: str,
        es_cancelable: str | None = None,
        estatus_cancelacion: str | None = None,
        commit: bool = False,
    ) -> None:
        self.conn.execute(
            "UPDATE comprobantes SET estatus = ?, estatus_fecha = ?, es_cancelable = ?, "
            "estatus_cancelacion = ? WHERE uuid = ?",
            (
                estatus,
                datetime.now().isoformat(timespec="seconds"),
                es_cancelable,
                estatus_cancelacion,
                uuid,
            ),
        )
        if commit:
            self.conn.commit()

    def _filtros_consulta(
        self,
        cliente: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        tipo: str | None = None,
        sin_estatus: bool = False,
    ) -> tuple[str, list[Any]]:
        where = " WHERE 1=1"
        params: list[Any] = []
        if cliente is not None:
            where += " AND cliente = ?"
            params.append(cliente)
        if tipo is not None:
            where += " AND tipo_comprobante = ?"
            params.append(tipo)
        if desde is not None:
            where += " AND fecha >= ?"
            params.append(desde)
        if hasta is not None:
            where += " AND fecha <= ?"
            params.append(hasta if "T" in hasta else hasta + "T23:59:59")
        if sin_estatus:
            where += " AND estatus IS NULL"
        return where, params

    def consulta(
        self,
        cliente: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        tipo: str | None = None,
        sin_estatus: bool = False,
    ) -> Iterator[sqlite3.Row]:
        where, params = self._filtros_consulta(cliente, desde, hasta, tipo, sin_estatus)
        self.conn.row_factory = sqlite3.Row
        return self.conn.execute(
            "SELECT * FROM comprobantes" + where + " ORDER BY fecha", params
        )

    def contar_consulta(
        self,
        cliente: str | None = None,
        desde: str | None = None,
        hasta: str | None = None,
        tipo: str | None = None,
        sin_estatus: bool = False,
    ) -> int:
        where, params = self._filtros_consulta(cliente, desde, hasta, tipo, sin_estatus)
        return self.conn.execute(
            "SELECT COUNT(*) FROM comprobantes" + where, params
        ).fetchone()[0]

    def consultar_pagos(self, cliente: str | None = None) -> Iterator[sqlite3.Row]:
        sql = "SELECT p.*, c.cliente AS cliente FROM pagos p JOIN comprobantes c ON p.comprobante_uuid = c.uuid WHERE 1=1"
        params: list[Any] = []
        if cliente is not None:
            sql += " AND c.cliente = ?"
            params.append(cliente)
        sql += " ORDER BY p.fecha_pago"
        self.conn.row_factory = sqlite3.Row
        return self.conn.execute(sql, params)

    def consultar_doctos(self, pago_id: int) -> list[sqlite3.Row]:
        self.conn.row_factory = sqlite3.Row
        return self.conn.execute(
            "SELECT * FROM doctos_relacionados WHERE pago_id = ? ORDER BY num_parcialidad",
            (pago_id,),
        ).fetchall()

    def consultar_doctos_lote(self, pago_ids: list[int]) -> dict[int, list[sqlite3.Row]]:
        """Trae doctos de muchos pagos en 1 query (evita N+1)."""
        if not pago_ids:
            return {}
        self.conn.row_factory = sqlite3.Row
        marcadores = ",".join("?" for _ in pago_ids)
        filas = self.conn.execute(
            f"SELECT * FROM doctos_relacionados WHERE pago_id IN ({marcadores}) "
            "ORDER BY pago_id, num_parcialidad",
            pago_ids,
        ).fetchall()
        agrupados: dict[int, list[sqlite3.Row]] = {pid: [] for pid in pago_ids}
        for f in filas:
            agrupados.setdefault(f["pago_id"], []).append(f)
        return agrupados

    def contar(self, tabla: str) -> int:
        if tabla not in _TABLAS:
            raise ValueError(f"tabla no permitida: {tabla}")
        return self.conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]

    def clientes(self) -> list[str]:
        """Clientes que tienen al menos un comprobante en el catálogo, ordenados."""
        return [
            fila[0]
            for fila in self.conn.execute(
                "SELECT DISTINCT cliente FROM comprobantes ORDER BY cliente"
            )
        ]

    def conteo_estatus(self) -> dict[str, int]:
        """Conteo de comprobantes por estatus; 'Sin validar' si nunca se consultó."""
        conteo = {fila[0]: fila[1] for fila in self.conn.execute(
            "SELECT COALESCE(estatus, 'Sin validar') AS estatus, COUNT(*) AS n "
            "FROM comprobantes GROUP BY estatus"
        )}
        return {
            estado: conteo.get(estado, 0)
            for estado in ("Vigente", "Cancelado", "No Encontrado", "Sin validar")
        }

    def limpiar(self) -> None:
        """Vacía todas las tablas del catálogo para iniciar un nuevo lote limpio."""
        self.conn.executescript(
            "DELETE FROM doctos_relacionados; "
            "DELETE FROM pagos; "
            "DELETE FROM comprobantes; "
            "DELETE FROM errores; "
        )
        self.conn.commit()