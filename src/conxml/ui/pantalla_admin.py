"""Pantalla de administración de XML: leer carpeta, previsualizar, validar y exportar.

Tres modos:
- ``cfdi40``: Ingresos, Egresos y Traslado
- ``pagos``: Complementos de pago (REP) y conciliación
- ``nomina``: Recibos de nómina
"""
from __future__ import annotations

import calendar
from datetime import date, datetime
from pathlib import Path

import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from conxml.catalog.db import Catalogo
from conxml.catalog.importer import importar_carpetas
from conxml.cfdi import parse_comprobante, parse_nomina
from conxml.cfdi.catalogos import (
    FORMA_PAGO,
    REGIMEN_FISCAL,
    TIPO_COMPROBANTE,
    USO_CFDI,
    describir,
)
from conxml.config import Config
from conxml import estado_local
from conxml.archivos import abrir_local
from conxml.export.pdf import generar_pdf, exportar_lote, nombre_pdf
from conxml.ui.visor_pdf import abrir_vista_previa
from conxml.export.listado import (
    COMPLEMENTOS_IGNORADOS,
    _base_por_factor,
    _importes,
    _retencion_por_impuesto,
    _retencion_por_tasa,
    _suma_importes,
    _traslado_por_tasa,
    exportar_listado,
)
from conxml.export.nomina import exportar_nomina
from conxml.export.pagos import exportar_pagos
from conxml.sat.estatus import ConfigLote, consultar_lote
from conxml.ui import theme as th
from conxml.ui.columnas import GestorColumnas
from conxml.ui.widgets import (
    BotonPrimario,
    BotonSecundario,
    Encabezado,
    PanelCard,
    ResumenOperacion,
)

MODO_CFDI40 = "cfdi40"
MODO_PAGOS = "pagos"
MODO_NOMINA = "nomina"

_COLUMNAS_CFDI40 = [
    ("verificado", "Verificado o Asoc", 110),
    ("estatus", "Estado SAT", 100),
    ("es_cancelable", "EsCancelable", 110),
    ("estatus_cancelacion", "EstatusCancelacion", 140),
    ("relaciones", "CfdiRelacionados", 160),
    ("uuid", "UUID", 240),
    ("serie", "Serie", 60),
    ("folio", "Folio", 70),
    ("version", "Version", 60),
    ("tipo", "TipoComprobante", 110),
    ("fecha_timbrado", "FechaTimbradoXML", 140),
    ("fecha", "FechaEmisionXML", 140),
    ("lugar_expedicion", "LugarDeExpedicion", 110),
    ("emisor_rfc", "RFC Emisor", 110),
    ("emisor", "Nombre Emisor", 180),
    ("emisor_regimen", "RegimenFiscal", 140),
    ("receptor_rfc", "RFC Receptor", 110),
    ("receptor", "Nombre Receptor", 180),
    ("uso_cfdi", "UsoCFDI", 160),
    ("regimen_fiscal_receptor", "RegimenFiscalReceptor", 160),
    ("domicilio_fiscal_receptor", "DomicilioFiscalReceptor", 140),
    ("forma_pago", "FormaDePago", 140),
    ("metodo_pago", "Metodo de Pago", 120),
    ("complementos", "Complementos comprobante", 160),
    ("conceptos", "Conceptos", 220),
    ("complementos_conceptos", "Complementos conceptos", 140),
    ("subtotal", "SubTotal", 90),
    ("descuento", "Descuento", 90),
    ("total_traslados", "Total Trasladados", 100),
    ("total_retenciones", "Total Retenidos", 100),
    ("total", "Total", 100),
    ("moneda", "Moneda", 60),
    ("iva_exento", "IVA Exento Base", 90),
    ("iva_cero", "IVA Cero Base", 90),
    ("iva_8", "IVA 8 Importe", 90),
    ("iva_16", "IVA 16 Importe", 90),
    ("isr_ret", "ISR Retenido", 90),
    ("iva_ret", "IVA Retenido", 90),
    ("ieps_ret", "IEPS Retenido", 90),
    ("ret_isr_125", "Ret ISR 1.25 Importe", 100),
    ("ret_iva_106", "Ret IVA 10.6667 Importe", 110),
    ("ret_iva_8", "Ret IVA 8 Importe", 90),
    ("ret_iva_6", "Ret IVA 6 Importe", 90),
    ("ret_iva_16", "Ret IVA 16 Importe", 90),
    ("no_cert_sat", "No Certificado SAT", 140),
    ("no_cert_emisor", "No Certificado Emisor", 140),
    ("ruta", "Archivo XML", 200),
]

_COLUMNAS_PAGOS_CONCILIACION = [
    ("cliente", "Cliente", 120),
    ("uuid_rep", "UUID REP", 240),
    ("serie_rep", "Serie REP", 60),
    ("folio_rep", "Folio REP", 70),
    ("fecha_rep", "Fecha REP", 130),
    ("estatus_rep", "Estatus REP", 100),
    ("fecha_pago", "Fecha Pago", 130),
    ("forma_pago", "Forma Pago", 140),
    ("moneda_pago", "Moneda Pago", 70),
    ("monto", "Monto", 90),
    ("num_operacion", "Núm. Operación", 100),
    ("cta_origen", "Cuenta Origen", 110),
    ("cta_destino", "Cuenta Destino", 110),
    ("rfc_cta_origen", "RFC Cta Origen", 110),
    ("uuid_doc", "UUID Factura", 240),
    ("serie", "Serie", 60),
    ("folio", "Folio", 70),
    ("moneda_dr", "Moneda DR", 70),
    ("parcialidad", "Parcialidad", 60),
    ("saldo_ant", "Saldo Anterior", 95),
    ("pagado", "Pagado", 95),
    ("saldo_insoluto", "Saldo Insoluto", 95),
    ("estatus_factura", "Estatus Factura", 100),
    ("estatus_consultado", "Estatus consultado", 110),
    ("es_cancelable_rep", "EsCancelable REP", 110),
    ("estatus_cancelacion_rep", "EstatusCancelacion REP", 140),
    ("fecha_timbrado_rep", "FechaTimbrado REP", 130),
    ("tipo_comprobante_rep", "TipoComprobante REP", 110),
    ("ruta_rep", "Archivo XML REP", 180),
    ("es_cancelable", "EsCancelable", 110),
    ("estatus_cancelacion", "EstatusCancelacion", 140),
    ("fecha_timbrado", "FechaTimbradoXML", 130),
    ("tipo_comprobante", "TipoComprobante", 110),
    ("total_factura", "Total Factura", 95),
    ("ruta", "Archivo XML", 180),
]

_COLUMNAS_NOMINA = [
    ("cliente", "Cliente", 120),
    ("estatus", "Estado SAT", 100),
    ("es_cancelable", "EsCancelable", 110),
    ("estatus_cancelacion", "EstatusCancelacion", 140),
    ("uuid", "UUID", 240),
    ("serie", "Serie", 60),
    ("folio", "Folio", 70),
    ("fecha_timbrado", "FechaTimbradoXML", 130),
    ("fecha", "FechaEmisionXML", 130),
    ("emisor_rfc", "RFC Emisor", 110),
    ("emisor_nombre", "Nombre Emisor", 180),
    ("registro_patronal", "Registro Patronal", 120),
    ("receptor_rfc", "RFC Receptor", 110),
    ("receptor_nombre", "Nombre Receptor", 180),
    ("curp", "CURP", 140),
    ("num_empleado", "Num Empleado", 90),
    ("puesto", "Puesto", 140),
    ("tipo_nomina", "Tipo Nomina", 90),
    ("fecha_pago", "Fecha Pago", 110),
    ("fecha_inicial_pago", "Fecha Inicial Pago", 110),
    ("fecha_final_pago", "Fecha Final Pago", 110),
    ("num_dias_pagados", "Num Dias Pagados", 90),
    ("periodicidad_pago", "Periodicidad Pago", 110),
    ("total_percepciones", "Total Percepciones", 100),
    ("total_deducciones", "Total Deducciones", 100),
    ("total_otros_pagos", "Total Otros Pagos", 100),
    ("subtotal", "SubTotal", 90),
    ("descuento", "Descuento", 90),
    ("total", "Total", 90),
    ("moneda", "Moneda", 60),
    ("ruta", "Archivo XML", 180),
]

# ── Vistas de Conciliación de Pagos (estilo Mi Admin XML) ────────────────────

VISTAS_PAGOS = [
    ("conciliacion", "Conciliación"),
    ("facturas_ppd", "Facturas PPD"),
    ("facturas_p", "Facturas P"),
    ("pagos", "Pagos"),
    ("doctos", "Doctos relacionados"),
]

_COLUMNAS_FACTURAS_PPD = [
    ("cliente", "Cliente", 120),
    ("estatus", "Estado SAT", 100),
    ("es_cancelable", "EsCancelable", 110),
    ("estatus_cancelacion", "EstatusCancelacion", 140),
    ("uuid", "UUID", 240),
    ("serie", "Serie", 60),
    ("folio", "Folio", 70),
    ("fecha", "FechaEmisionXML", 140),
    ("fecha_timbrado", "FechaTimbradoXML", 140),
    ("emisor_rfc", "RFC Emisor", 110),
    ("emisor_nombre", "Nombre Emisor", 180),
    ("receptor_rfc", "RFC Receptor", 110),
    ("receptor_nombre", "Nombre Receptor", 180),
    ("moneda", "Moneda", 60),
    ("total", "Total", 100),
    ("pagado", "Pagado", 100),
    ("saldo_pendiente", "Saldo Pendiente", 110),
    ("estado_cobranza", "Estatus de Pago", 150),
    ("ruta", "Archivo XML", 200),
]

_COLUMNAS_FACTURAS_P = [
    ("cliente", "Cliente", 120),
    ("estatus", "Estado SAT", 100),
    ("es_cancelable", "EsCancelable", 110),
    ("estatus_cancelacion", "EstatusCancelacion", 140),
    ("uuid", "UUID", 240),
    ("serie", "Serie", 60),
    ("folio", "Folio", 70),
    ("fecha", "FechaEmisionXML", 140),
    ("fecha_timbrado", "FechaTimbradoXML", 140),
    ("emisor_rfc", "RFC Emisor", 110),
    ("emisor_nombre", "Nombre Emisor", 180),
    ("receptor_rfc", "RFC Receptor", 110),
    ("receptor_nombre", "Nombre Receptor", 180),
    ("moneda", "Moneda", 60),
    ("total", "Total", 100),
    ("num_pagos", "Núm. Pagos", 90),
    ("monto_pagos", "Monto Pagado", 110),
    ("ruta", "Archivo XML", 200),
]

_COLUMNAS_PAGOS_LISTA = [
    ("cliente", "Cliente", 120),
    ("uuid_rep", "UUID REP", 240),
    ("serie_rep", "Serie REP", 60),
    ("folio_rep", "Folio REP", 70),
    ("estatus_rep", "Estado SAT REP", 100),
    ("fecha_pago", "Fecha Pago", 130),
    ("forma_pago", "Forma Pago", 140),
    ("moneda", "Moneda", 70),
    ("monto", "Monto", 100),
    ("num_operacion", "Núm. Operación", 110),
    ("cta_origen", "Cuenta Origen", 130),
    ("cta_destino", "Cuenta Destino", 130),
    ("rfc_cta_origen", "RFC Cta Origen", 120),
    ("num_doctos", "Núm. Doctos", 90),
]

_COLUMNAS_DOCTOS = [
    ("cliente", "Cliente", 120),
    ("estatus_factura", "Estado SAT", 100),
    ("no_cert_emisor", "No Certificado Emisor", 140),
    ("no_cert_sat", "No Certificado SAT", 140),
    ("fecha_emision", "Fecha Emision", 140),
    ("fecha_timbrado", "Fecha Timbrado", 140),
    ("anio", "Año", 55),
    ("mes", "Mes", 50),
    ("dia", "Día", 50),
    ("serie", "Serie", 60),
    ("folio", "Folio", 70),
    ("uuid_doc", "UUID", 240),
    ("rfc_emisor", "RFC Emisor", 110),
    ("nombre_emisor", "Nombre Emisor", 180),
    ("regimen_fiscal", "RegimenFiscal", 140),
    ("fecha_pago", "Fecha Pago", 130),
    ("forma_pago", "Forma Pago", 130),
    ("monto", "Monto Pago", 90),
    ("parcialidad", "Parcialidad", 80),
    ("saldo_ant", "Saldo Anterior", 100),
    ("pagado", "Pagado", 100),
    ("saldo_insoluto", "Saldo Insoluto", 100),
    ("uuid_rep", "UUID REP", 240),
    ("serie_rep", "Serie REP", 60),
    ("folio_rep", "Folio REP", 70),
    ("ruta", "Archivo XML Factura", 200),
]

def _numero(valor: str | None) -> float | None:
    return float(valor) if valor not in (None, "") else None


def _breve(fecha: str | None) -> str:
    return fecha[:16] if fecha else ""


def aplicar_estilo_tabla(tabla: ttk.Treeview) -> None:
    """Reestila la tabla con el tema Fluent Empresarial."""
    estilo = ttk.Style()
    estilo.configure(
        "Tabla.Treeview",
        background=th.FONDO_TABLA,
        fieldbackground=th.FONDO_TABLA,
        foreground=th.TEXTO,
        borderwidth=0,
        rowheight=23,
        font=(th.FUENTE, th.TAM_TABLA),
    )
    estilo.configure(
        "Tabla.Treeview.Heading",
        background=th.FONDO,
        foreground=th.TEXTO_SECUNDARIO,
        relief="flat",
        # Encabezados compactos: las tablas tienen muchas columnas y el dato
        # debe ocupar visualmente más espacio que el título.
        font=(th.FUENTE, th.TAM_TABLA),
    )
    estilo.map("Tabla.Treeview", background=[("selected", th.PRIMARIO)])
    estilo.map("Tabla.Treeview.Heading", background=[])

    tabla.tag_configure("par", background=th.FONDO_TABLA)
    tabla.tag_configure("impar", background=th.FONDO_ENTRADA)


def auto_ajustar_columnas(tabla: ttk.Treeview, min_ancho: int = 70, max_ancho: int = 420) -> None:
    """Ajusta automáticamente el ancho de cada columna al contenido más largo."""
    try:
        font = tkfont.Font(family=th.FUENTE, size=th.TAM_TABLA)
        font_bold = tkfont.Font(family=th.FUENTE, size=th.TAM_TABLA)
    except Exception:
        return

    items = tabla.get_children()
    display = tabla["displaycolumns"]
    if display and "#all" not in display:
        columnas = list(display)
    else:
        columnas = list(tabla["columns"])
    for col in columnas:
        header_text = tabla.heading(col)["text"]
        w_max = font_bold.measure(str(header_text)) + 24
        for item in items[:100]:
            val = tabla.set(item, col)
            if val:
                w = font.measure(str(val)) + 18
                if w > w_max:
                    w_max = w
        ancho_final = max(min_ancho, min(w_max, max_ancho))
        tabla.column(col, width=ancho_final, stretch=False)


# ── Componentes de Resumen de Totales ─────────────────────────────────────────

class PanelResumenTotales(PanelCard):
    """Panel de resumen para XML 4.0 (Totales, Vigentes, Cancelados)."""

    def __init__(self, parent: ctk.CTkFrame, al_colapsar=None) -> None:
        super().__init__(parent)
        self._filas: list[dict] = []
        self._colapsado = False
        self._al_colapsar = al_colapsar
        self._cambio_interno = False

        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.pack(fill="x", expand=True, padx=16, pady=10)

        header = ctk.CTkFrame(contenedor, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            header, text="RESUMEN DE TOTALES", text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
        ).pack(side="left")

        self._btn_totales = ctk.CTkButton(
            header, text="Ocultar ▾", width=90, height=26,
            fg_color="transparent", hover_color=th.FONDO_ENTRADA,
            text_color=th.TEXTO_SECUNDARIO, corner_radius=th.RADIO_GRUPO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
            command=self.alternar_colapsado,
        )
        self._btn_totales.pack(side="right", padx=(8, 0))

        self.seg_modo = ctk.CTkSegmentedButton(
            header,
            values=["Totales", "Vigentes", "Cancelados"],
            command=self._al_cambiar_filtro,
            fg_color=th.FONDO_ENTRADA,
            selected_color=th.PRIMARIO,
            selected_hover_color=th.PRIMARIO_HOVER,
            unselected_color=th.FONDO_TARJETA,
            unselected_hover_color=th.PRIMARIO_FONDO,
            text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
            height=26,
        )
        self.seg_modo.set("Totales")
        self.seg_modo.pack(side="right")

        self.grid_totales = ctk.CTkFrame(contenedor, fg_color="transparent")
        self.grid_totales.pack(fill="x")
        for col in range(6):
            self.grid_totales.columnconfigure(col, weight=1, uniform="totales")

        self._labels_cnt: dict[str, ctk.CTkLabel] = {}
        self._labels_monto: dict[str, ctk.CTkLabel] = {}
        self._tarjetas: list[ctk.CTkFrame] = []

        items_def = [
            ("ingresos", "Total Ingresos", th.PRIMARIO),
            ("egresos", "Total Egresos", th.ROJO),
            ("traslados", "Total Traslados", "#0891B2"),
            ("ppd", "Total PPD", th.AMBAR),
            ("pue", "Total PUE", "#9333EA"),
            ("total", "Total XML", th.TEXTO),
        ]

        for col, (clave, titulo, color) in enumerate(items_def):
            card_item = ctk.CTkFrame(self.grid_totales, fg_color=th.FONDO_ENTRADA, corner_radius=6)
            card_item.grid(row=0, column=col, sticky="nsew", padx=3 if col > 0 else 0)
            self._tarjetas.append(card_item)

            pad = ctk.CTkFrame(card_item, fg_color="transparent")
            pad.pack(fill="both", expand=True, padx=8, pady=6)

            lbl_t = ctk.CTkLabel(
                pad, text=f"{titulo} (0)", text_color=color,
                font=(th.FUENTE, th.TAM_NOTA, "bold" if clave == "total" else "normal"), anchor="w",
            )
            lbl_t.pack(anchor="w")
            self._labels_cnt[clave] = lbl_t

            lbl_m = ctk.CTkLabel(
                pad, text="$0.00", text_color=color,
                font=(th.FUENTE, th.TAM_BODY, "bold"), anchor="e",
            )
            lbl_m.pack(anchor="e", pady=(2, 0))
            self._labels_monto[clave] = lbl_m

    @property
    def colapsado(self) -> bool:
        return self._colapsado

    def alternar_colapsado(self) -> None:
        self.fijar_colapsado(not self._colapsado)

    def fijar_colapsado(self, colapsado: bool) -> None:
        colapsado = bool(colapsado)
        if colapsado == self._colapsado:
            return
        self._colapsado = colapsado
        try:
            if colapsado:
                self.grid_totales.pack_forget()
                self._btn_totales.configure(text="Mostrar ▸")
            else:
                self.grid_totales.pack(fill="x")
                self._btn_totales.configure(text="Ocultar ▾")
        except Exception:
            pass
        if not self._cambio_interno and callable(self._al_colapsar):
            try:
                self._al_colapsar(colapsado)
            except Exception:
                pass

    def aplicar_compacto(self, compacto: bool) -> None:
        """Refluye a 2 filas en ventana estrecha para no comprimir tarjetas."""
        try:
            for tarjeta in self._tarjetas:
                tarjeta.grid_forget()
            if compacto:
                for col in range(6):
                    self.grid_totales.columnconfigure(col, weight=0, uniform="")
                for col in range(3):
                    self.grid_totales.columnconfigure(col, weight=1, uniform="tot-c")
                for i, tarjeta in enumerate(self._tarjetas):
                    tarjeta.grid(
                        row=i // 3, column=i % 3, sticky="nsew",
                        padx=3 if (i % 3) > 0 else 0, pady=3 if i >= 3 else 0,
                    )
            else:
                for col in range(6):
                    self.grid_totales.columnconfigure(col, weight=1, uniform="totales")
                for i, tarjeta in enumerate(self._tarjetas):
                    tarjeta.grid(row=0, column=i, sticky="nsew", padx=3 if i > 0 else 0)
        except Exception:
            pass

    def actualizar(self, filas: list) -> None:
        self._filas = [dict(f) if not isinstance(f, dict) else f for f in filas]
        self._al_cambiar_filtro(self.seg_modo.get())

    def _al_cambiar_filtro(self, modo: str) -> None:
        if modo == "Vigentes":
            filas_f = [f for f in self._filas if f.get("estatus") == "Vigente"]
        elif modo == "Cancelados":
            filas_f = [f for f in self._filas if f.get("estatus") == "Cancelado"]
        else:
            filas_f = self._filas

        c_ing, m_ing = 0, 0.0
        c_egr, m_egr = 0, 0.0
        c_tra, m_tra = 0, 0.0
        c_ppd, m_ppd = 0, 0.0
        c_pue, m_pue = 0, 0.0
        c_tot, m_tot = 0, 0.0

        for r in filas_f:
            t = r.get("tipo_comprobante")
            m = r.get("metodo_pago")
            tot_val = float(r.get("total")) if r.get("total") not in (None, "") else 0.0

            c_tot += 1
            m_tot += tot_val

            if t == "I":
                c_ing += 1; m_ing += tot_val
            elif t == "E":
                c_egr += 1; m_egr += tot_val
            elif t == "T":
                c_tra += 1; m_tra += tot_val

            if m == "PPD":
                c_ppd += 1; m_ppd += tot_val
            elif m == "PUE":
                c_pue += 1; m_pue += tot_val

        datos = {
            "ingresos": (c_ing, m_ing, "Total Ingresos"),
            "egresos": (c_egr, m_egr, "Total Egresos"),
            "traslados": (c_tra, m_tra, "Total Traslados"),
            "ppd": (c_ppd, m_ppd, "Total PPD"),
            "pue": (c_pue, m_pue, "Total PUE"),
            "total": (c_tot, m_tot, "Total XML"),
        }

        for clave, (cnt, monto, tit) in datos.items():
            self._labels_cnt[clave].configure(text=f"{tit} ({cnt})")
            self._labels_monto[clave].configure(text=f"${monto:,.2f}")


class PanelResumenPagos(PanelCard):
    """Panel de resumen para Conciliación de Pagos (PPD, P, Pagos, Doctos, Tot/Parcialmente pagadas)."""

    def __init__(self, parent: ctk.CTkFrame, al_colapsar=None) -> None:
        super().__init__(parent)
        self._colapsado = False
        self._al_colapsar = al_colapsar
        self._cambio_interno = False
        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.pack(fill="x", expand=True, padx=16, pady=10)

        header = ctk.CTkFrame(contenedor, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            header, text="RESUMEN DE CONCILIACIÓN DE PAGOS", text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
        ).pack(side="left")

        self._btn_totales = ctk.CTkButton(
            header, text="Ocultar ▾", width=90, height=26,
            fg_color="transparent", hover_color=th.FONDO_ENTRADA,
            text_color=th.TEXTO_SECUNDARIO, corner_radius=th.RADIO_GRUPO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
            command=self.alternar_colapsado,
        )
        self._btn_totales.pack(side="right")

        self.grid_pagos = ctk.CTkFrame(contenedor, fg_color="transparent")
        self.grid_pagos.pack(fill="x")
        for col in range(7):
            self.grid_pagos.columnconfigure(col, weight=1, uniform="pagos")

        self._labels_cnt: dict[str, ctk.CTkLabel] = {}
        self._labels_monto: dict[str, ctk.CTkLabel] = {}
        self._tarjetas: list[ctk.CTkFrame] = []

        items_def = [
            ("fact_ppd", "Facturas PPD", th.PRIMARIO),
            ("fact_p", "Facturas P", th.VERDE),
            ("pagos", "Pagos", th.VERDE),
            ("doctos", "Doctos Relacionados", "#0891B2"),
            ("no_pagadas", "No pagadas", "#9333EA"),
            ("tot_pagadas", "Totalmente pagadas", th.AMBAR),
            ("parc_pagadas", "Parcialmente pagadas", "#9333EA"),
        ]

        for col, (clave, titulo, color) in enumerate(items_def):
            card_item = ctk.CTkFrame(self.grid_pagos, fg_color=th.FONDO_ENTRADA, corner_radius=6)
            card_item.grid(row=0, column=col, sticky="nsew", padx=3 if col > 0 else 0)
            self._tarjetas.append(card_item)

            pad = ctk.CTkFrame(card_item, fg_color="transparent")
            pad.pack(fill="both", expand=True, padx=8, pady=6)

            lbl_t = ctk.CTkLabel(
                pad, text=f"{titulo} (0)", text_color=color,
                font=(th.FUENTE, th.TAM_NOTA, "bold"), anchor="w",
            )
            lbl_t.pack(anchor="w")
            self._labels_cnt[clave] = lbl_t

            lbl_m = ctk.CTkLabel(
                pad, text="$0.00", text_color=color,
                font=(th.FUENTE, th.TAM_BODY, "bold"), anchor="e",
            )
            lbl_m.pack(anchor="e", pady=(2, 0))
            self._labels_monto[clave] = lbl_m

    @property
    def colapsado(self) -> bool:
        return self._colapsado

    def alternar_colapsado(self) -> None:
        self.fijar_colapsado(not self._colapsado)

    def fijar_colapsado(self, colapsado: bool) -> None:
        colapsado = bool(colapsado)
        if colapsado == self._colapsado:
            return
        self._colapsado = colapsado
        try:
            if colapsado:
                self.grid_pagos.pack_forget()
                self._btn_totales.configure(text="Mostrar ▸")
            else:
                self.grid_pagos.pack(fill="x")
                self._btn_totales.configure(text="Ocultar ▾")
        except Exception:
            pass
        if not self._cambio_interno and callable(self._al_colapsar):
            try:
                self._al_colapsar(colapsado)
            except Exception:
                pass

    def aplicar_compacto(self, compacto: bool) -> None:
        """Refluye a 2 filas en ventana estrecha para no comprimir tarjetas."""
        try:
            for tarjeta in self._tarjetas:
                tarjeta.grid_forget()
            if compacto:
                for col in range(7):
                    self.grid_pagos.columnconfigure(col, weight=0, uniform="")
                for col in range(4):
                    self.grid_pagos.columnconfigure(col, weight=1, uniform="pag-c")
                for i, tarjeta in enumerate(self._tarjetas):
                    tarjeta.grid(
                        row=i // 4, column=i % 4, sticky="nsew",
                        padx=3 if (i % 4) > 0 else 0, pady=3 if i >= 4 else 0,
                    )
            else:
                for col in range(7):
                    self.grid_pagos.columnconfigure(col, weight=1, uniform="pagos")
                for i, tarjeta in enumerate(self._tarjetas):
                    tarjeta.grid(row=0, column=i, sticky="nsew", padx=3 if i > 0 else 0)
        except Exception:
            pass

    def actualizar(self, catalogo: Catalogo, cliente: str | None) -> None:
        comprobantes = list(catalogo.consulta(cliente=cliente))
        pagos = list(catalogo.consultar_pagos(cliente=cliente))
        doctos = []
        for p in pagos:
            doctos.extend(catalogo.consultar_doctos(p["id"]))

        ppd = [c for c in comprobantes if c["metodo_pago"] == "PPD"]
        ppd_cnt = len(ppd)
        ppd_tot = sum(float(c["total"]) for c in ppd if c["total"])

        fact_p = [c for c in comprobantes if c["tipo_comprobante"] == "P"]
        fact_p_cnt = len(fact_p)
        fact_p_tot = sum(float(c["total"]) for c in fact_p if c["total"])

        pagos_cnt = len(pagos)
        pagos_tot = sum(float(p["monto"]) for p in pagos if p["monto"])

        doctos_cnt = len(doctos)
        doctos_tot = sum(float(d["imp_pagado"]) for d in doctos if d["imp_pagado"])

        doctos_by_doc = {}
        for d in doctos:
            u = d["uuid_doc"]
            if u not in doctos_by_doc:
                doctos_by_doc[u] = []
            doctos_by_doc[u].append(d)

        tot_pagadas_cnt, tot_pagadas_m = 0, 0.0
        parc_pagadas_cnt, parc_pagadas_m = 0, 0.0
        no_pagadas_cnt, no_pagadas_m = 0, 0.0

        for f in ppd:
            uuid = f["uuid"]
            tot_f = float(f["total"]) if f["total"] else 0.0
            if uuid not in doctos_by_doc:
                no_pagadas_cnt += 1
                no_pagadas_m += tot_f
            else:
                docs_f = doctos_by_doc[uuid]
                ult_doc = max(docs_f, key=lambda x: x["num_parcialidad"] or 0)
                insoluto = float(ult_doc["imp_saldo_insoluto"]) if ult_doc["imp_saldo_insoluto"] else 0.0
                if insoluto <= 0.01:
                    tot_pagadas_cnt += 1
                    tot_pagadas_m += tot_f
                else:
                    parc_pagadas_cnt += 1
                    parc_pagadas_m += tot_f

        datos = {
            "fact_ppd": (ppd_cnt, ppd_tot, "Facturas PPD"),
            "fact_p": (fact_p_cnt, fact_p_tot, "Facturas P"),
            "pagos": (pagos_cnt, pagos_tot, "Pagos"),
            "doctos": (doctos_cnt, doctos_tot, "Doctos Relacionados"),
            "no_pagadas": (no_pagadas_cnt, no_pagadas_m, "No pagadas"),
            "tot_pagadas": (tot_pagadas_cnt, tot_pagadas_m, "Totalmente pagadas"),
            "parc_pagadas": (parc_pagadas_cnt, parc_pagadas_m, "Parcialmente pagadas"),
        }

        for clave, (cnt, monto, tit) in datos.items():
            self._labels_cnt[clave].configure(text=f"{tit} ({cnt})")
            self._labels_monto[clave].configure(text=f"${monto:,.2f}")


# ── Pantalla Principal de Administración ─────────────────────────────────────


class SelectorFecha(ctk.CTkFrame):
    """Campo compacto DD/MM/AA con calendario desplegable."""

    def __init__(self, parent, al_cambiar=None) -> None:
        super().__init__(parent, fg_color="transparent", height=32)
        self._al_cambiar = al_cambiar
        self._valor = tk.StringVar()
        self._popup = None
        self._mes_mostrado = date.today().replace(day=1)

        self._entrada = ctk.CTkEntry(
            self, textvariable=self._valor, width=96, height=32,
            placeholder_text="DD/MM/AA", font=(th.FUENTE, th.TAM_BODY),
        )
        self._entrada.pack(side="left", fill="x", expand=True)
        self._entrada.bind("<KeyRelease>", lambda _event: self._notificar())
        self._entrada.bind("<Return>", lambda _event: self._notificar())
        ctk.CTkButton(
            self, text="▾", width=28, height=32,
            fg_color=th.FONDO_TARJETA, hover_color=th.PRIMARIO_FONDO,
            text_color=th.TEXTO_SECUNDARIO, border_width=1,
            border_color=th.BORDE, corner_radius=th.RADIO_CAMPO,
            font=(th.FUENTE, th.TAM_BODY, "bold"),
            command=self._abrir_calendario,
        ).pack(side="left", padx=(4, 0))

    def get(self) -> str:
        return self._valor.get()

    def set(self, valor: str) -> None:
        self._valor.set(valor)

    def delete(self, _inicio=0, _fin="end") -> None:
        self._valor.set("")

    def _notificar(self) -> None:
        if callable(self._al_cambiar):
            self._al_cambiar()

    def _abrir_calendario(self) -> None:
        if self._popup is not None and self._popup.winfo_exists():
            self._popup.focus_force()
            return
        actual = self._parsear(self.get())
        self._mes_mostrado = actual.replace(day=1) if actual else date.today().replace(day=1)
        popup = ctk.CTkToplevel(self.winfo_toplevel())
        self._popup = popup
        popup.title("Seleccionar fecha")
        popup.geometry("270x265")
        popup.resizable(False, False)
        popup.transient(self.winfo_toplevel())
        popup.configure(fg_color=th.FONDO)

        contenido = ctk.CTkFrame(popup, fg_color="transparent")
        contenido.pack(fill="both", expand=True, padx=10, pady=10)
        cabecera = ctk.CTkFrame(contenido, fg_color="transparent")
        cabecera.pack(fill="x")
        self._btn_mes_anterior = ctk.CTkButton(
            cabecera, text="‹", width=30, height=28, fg_color="transparent",
            hover_color=th.PRIMARIO_FONDO, text_color=th.TEXTO,
            command=lambda: self._mover_mes(-1),
        )
        self._btn_mes_anterior.pack(side="left")
        self._lbl_mes = ctk.CTkLabel(
            cabecera, text="", text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_BODY, "bold"),
        )
        self._lbl_mes.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            cabecera, text="›", width=30, height=28, fg_color="transparent",
            hover_color=th.PRIMARIO_FONDO, text_color=th.TEXTO,
            command=lambda: self._mover_mes(1),
        ).pack(side="right")

        self._marco_dias = ctk.CTkFrame(contenido, fg_color="transparent")
        self._marco_dias.pack(fill="both", expand=True, pady=(6, 0))
        for columna, nombre in enumerate(("Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do")):
            self._marco_dias.columnconfigure(columna, weight=1)
            ctk.CTkLabel(
                self._marco_dias, text=nombre, text_color=th.TEXTO_SECUNDARIO,
                font=(th.FUENTE, th.TAM_NOTA, "bold"),
            ).grid(row=0, column=columna, padx=1, pady=1)
        self._dibujar_dias()
        popup.protocol("WM_DELETE_WINDOW", self._cerrar_popup)
        popup.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 4
        popup.geometry(f"+{x}+{y}")

    def _mover_mes(self, desplazamiento: int) -> None:
        mes = self._mes_mostrado.month - 1 + desplazamiento
        anio = self._mes_mostrado.year + mes // 12
        mes = mes % 12 + 1
        self._mes_mostrado = date(anio, mes, 1)
        self._dibujar_dias()

    def _dibujar_dias(self) -> None:
        if self._popup is None or not self._popup.winfo_exists():
            return
        meses = (
            "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
        )
        self._lbl_mes.configure(text=f"{meses[self._mes_mostrado.month]} {self._mes_mostrado.year}")
        for hijo in self._marco_dias.grid_slaves():
            if int(hijo.grid_info().get("row", 0)) > 0:
                hijo.destroy()
        seleccionado = self._parsear(self.get())
        for fila, semana in enumerate(calendar.monthcalendar(self._mes_mostrado.year, self._mes_mostrado.month), start=1):
            for columna, dia in enumerate(semana):
                if not dia:
                    continue
                fecha = date(self._mes_mostrado.year, self._mes_mostrado.month, dia)
                activo = seleccionado == fecha
                ctk.CTkButton(
                    self._marco_dias, text=str(dia), width=30, height=27,
                    fg_color=th.PRIMARIO if activo else "transparent",
                    hover_color=th.PRIMARIO_HOVER if activo else th.PRIMARIO_FONDO,
                    text_color="#FFFFFF" if activo else th.TEXTO,
                    corner_radius=4, font=(th.FUENTE, th.TAM_NOTA),
                    command=lambda valor=fecha: self._seleccionar(valor),
                ).grid(row=fila, column=columna, padx=1, pady=1)

    def _seleccionar(self, fecha: date) -> None:
        self._valor.set(fecha.strftime("%d/%m/%y"))
        self._notificar()
        self._cerrar_popup()

    def _cerrar_popup(self) -> None:
        if self._popup is not None:
            self._popup.destroy()
            self._popup = None

    @staticmethod
    def _parsear(valor: str) -> date | None:
        for formato in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M"):
            try:
                return datetime.strptime(valor.strip(), formato).date()
            except (TypeError, ValueError):
                pass
        return None

class PantallaAdministracion(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, app, modo: str) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.modo = modo
        self._cliente_cargado: str | None = None
        self._carpeta_cargada: Path | None = None
        self._vista = "conciliacion"
        self._gestores: dict[str, GestorColumnas] = {}
        self._orden_columna: str | None = None
        self._orden_desc = False

        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.pack(fill="both", expand=True, padx=32, pady=24)
        contenedor.columnconfigure(1, weight=1)
        # La tabla siempre conserva al menos 150px de altura en modo compacto.
        contenedor.rowconfigure(5 if modo == MODO_PAGOS else 4, weight=1, minsize=150)
        self._contenedor = contenedor
        self._padx_normal, self._pady_normal = 32, 24
        self._padx_compacto, self._pady_compacto = 12, 12
        self._ancho_compacto = False
        self._alto_compacto = False
        self._totales_colapsado_auto = False

        if modo == MODO_CFDI40:
            titulo = "Administración de XML 4.0 (Ingresos / Egresos / Traslados)"
            subtitulo = (
                "Consulta los XML seleccionados desde la Bóveda, previsualiza la "
                "información completa y valida estatus SAT."
            )
        elif modo == MODO_PAGOS:
            titulo = "Control y conciliación de pagos (REP)"
            subtitulo = (
                "Consulta los complementos de pago (REP) seleccionados desde la Bóveda, "
                "valida el estatus y exporta la conciliación."
            )
        else:
            titulo = "Recibos de Nómina"
            subtitulo = (
                "Previsualiza y exporta los comprobantes de nómina leídos en el catálogo, "
                "con detalle de percepciones, deducciones y periodos."
            )
        self._encabezado = Encabezado(contenedor, titulo, subtitulo)
        self._encabezado.grid(row=0, column=0, columnspan=3, sticky="ew")

        # La carga de archivos se hace desde la Bóveda. Esta pantalla queda
        # enfocada en consultar y visualizar el catálogo ya seleccionado.
        self._carpeta = tk.StringVar()
        self._fila_carpeta = ctk.CTkFrame(
            contenedor, fg_color=th.PRIMARIO_FONDO, corner_radius=th.RADIO_TARJETA
        )
        self._fila_carpeta.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(24, 6))
        ctk.CTkLabel(
            self._fila_carpeta,
            text="Selecciona primero los XML en la Bóveda y después usa este visor.",
            text_color=th.PRIMARIO_TEXTO,
            font=(th.FUENTE, th.TAM_BODY), anchor="w",
        ).pack(fill="x", padx=14, pady=9)
        self._btn_leer = BotonPrimario(contenedor, "Abrir Bóveda", lambda: self.app.navegar("boveda"))
        self._btn_leer.grid(row=1, column=2, padx=(10, 0), pady=6, sticky="e")

        # Panel de Resumen de Totales según el modo (colapsable, con control visible).
        if modo == MODO_PAGOS:
            self._totales_panel = PanelResumenPagos(contenedor, al_colapsar=self._al_colapsar_totales)
        else:
            self._totales_panel = PanelResumenTotales(contenedor, al_colapsar=self._al_colapsar_totales)
        self._totales_panel.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(12, 0))

        # Panel compacto de búsqueda. Los campos se aplican automáticamente
        # al escribir, sin botones que consuman espacio ni una fila duplicada
        # dentro de la tabla.
        barra_tabla = ctk.CTkFrame(
            contenedor, fg_color=th.FONDO_ENTRADA, corner_radius=th.RADIO_TARJETA
        )
        barra_tabla.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self._barra_tabla = barra_tabla
        barra_tabla.columnconfigure(1, weight=1)
        self._filtros = {}
        self._filtro_after = None
        ctk.CTkLabel(
            barra_tabla, text="Buscar por", text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_BODY, "bold"), anchor="w",
        ).grid(row=0, column=0, padx=(14, 10), pady=10, sticky="w")

        campos = ctk.CTkFrame(barra_tabla, fg_color="transparent")
        campos.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=8)
        for columna in range(6):
            campos.columnconfigure(columna, weight=1)

        definicion_filtros = (
            ("uuid", "UUID", 190, 0),
            ("rfc", "RFC", 115, 1),
            ("serie", "Serie", 85, 2),
            ("folio", "Folio", 85, 3),
        )
        for clave, texto, ancho, columna in definicion_filtros:
            entrada = ctk.CTkEntry(campos, width=ancho, placeholder_text=texto)
            entrada.grid(row=0, column=columna, padx=(0, 6), pady=(0, 4), sticky="ew")
            entrada.bind("<KeyRelease>", lambda _event: self._programar_carga_filtrada())
            entrada.bind("<Return>", lambda _event: self._cargar_tabla())
            self._filtros[clave] = entrada

        self._fecha = SelectorFecha(campos, self._programar_carga_filtrada)
        self._fecha.grid(row=0, column=4, padx=(0, 6), sticky="ew")
        self._monto = ctk.CTkEntry(campos, width=105, placeholder_text="Monto")
        self._monto.grid(row=0, column=5, padx=(0, 0), sticky="ew")
        self._monto.bind("<KeyRelease>", lambda _event: self._programar_carga_filtrada())
        self._monto.bind("<Return>", lambda _event: self._cargar_tabla())

        self._lbl_resultados = ctk.CTkLabel(
            barra_tabla, text="0 registros", text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA),
        )
        self._lbl_resultados.grid(row=0, column=2, padx=(8, 14), pady=10, sticky="e")

        self._seg_vista = None
        self._combo_vista = None
        self._barra_vistas = None
        if modo == MODO_PAGOS:
            # Separar el selector evita que las opciones se recorten cuando
            # conviven con la búsqueda y el zoom del sistema operativo.
            self._barra_vistas = ctk.CTkFrame(contenedor, fg_color="transparent")
            self._barra_vistas.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 0))
            self._lbl_vista = ctk.CTkLabel(
                self._barra_vistas, text="Vista:", text_color=th.TEXTO,
                font=(th.FUENTE, th.TAM_BODY, "bold"),
            )
            self._lbl_vista.pack(side="left")
            self._seg_vista = ctk.CTkSegmentedButton(
                self._barra_vistas,
                values=[titulo for _clave, titulo in VISTAS_PAGOS],
                command=self._cambiar_vista,
                fg_color=th.FONDO_ENTRADA,
                selected_color=th.PRIMARIO,
                selected_hover_color=th.PRIMARIO_HOVER,
                unselected_color=th.FONDO_TARJETA,
                unselected_hover_color=th.PRIMARIO_FONDO,
                text_color=th.TEXTO,
                font=(th.FUENTE, th.TAM_TABLA),
                height=30,
            )
            self._seg_vista.set("Conciliación")
            self._seg_vista.pack(side="left", padx=(8, 0))
            self._combo_vista = ctk.CTkComboBox(
                self._barra_vistas,
                values=[titulo for _clave, titulo in VISTAS_PAGOS],
                command=self._cambiar_vista,
                fg_color=th.FONDO_ENTRADA,
                border_color=th.BORDE,
                corner_radius=th.RADIO_CAMPO,
                text_color=th.TEXTO,
                dropdown_fg_color=th.FONDO_TARJETA,
                dropdown_text_color=th.TEXTO,
                button_color=th.BORDE,
                button_hover_color=th.PRIMARIO,
                font=(th.FUENTE, th.TAM_BODY),
                width=210,
            )
            self._combo_vista.set("Conciliación")

        marco_tabla = PanelCard(contenedor)
        marco_tabla.grid(
            row=5 if modo == MODO_PAGOS else 4,
            column=0, columnspan=3, sticky="nsew", pady=(8, 0),
        )
        marco_tabla.rowconfigure(0, weight=1)
        marco_tabla.columnconfigure(0, weight=1)
        self._marco_tabla = marco_tabla

        cols_ini = self._columnas_actuales()
        self._tabla = ttk.Treeview(
            marco_tabla,
            columns=[c[0] for c in cols_ini],
            displaycolumns="#all",
            show="headings",
            style="Tabla.Treeview",
            selectmode="extended",
        )
        self._configurar_columnas(cols_ini)
        aplicar_estilo_tabla(self._tabla)
        self._gestor().aplicar()

        scroll_y = ctk.CTkScrollbar(marco_tabla, command=self._tabla.yview)
        scroll_x = ctk.CTkScrollbar(
            marco_tabla, orientation="horizontal", command=self._tabla.xview
        )
        self._tabla.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self._tabla.grid(row=0, column=0, sticky="nsew")
        self._tabla.bind('<Double-1>', self._doble_clic_pdf)
        self._tabla.bind('<Button-3>', self._menu_pdf)
        self._tabla.bind('<Button-2>', self._menu_pdf)
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        self._scroll_y = scroll_y
        self._scroll_x = scroll_x

        # Fila de acciones inferiores
        marco_acciones = ctk.CTkFrame(contenedor, fg_color="transparent")
        marco_acciones.grid(
            row=6 if modo == MODO_PAGOS else 5,
            column=0, columnspan=3, sticky="ew", pady=(16, 0),
        )
        self._marco_acciones = marco_acciones

        self._btn_validar = BotonPrimario(marco_acciones, "Validar estatus", self._validar)
        self._btn_validar.pack(side="left")

        self._btn_exportar = BotonPrimario(marco_acciones, "Exportar Excel", self._exportar)
        self._btn_exportar.pack(side="left", padx=(12, 0))

        self._force = tk.BooleanVar(value=False)
        self._chk_force = ctk.CTkCheckBox(
            marco_acciones,
            text="Re-consultar ya validados",
            variable=self._force,
            fg_color=th.PRIMARIO,
            hover_color=th.PRIMARIO_HOVER,
            border_color=th.BORDE,
            text_color=th.TEXTO,
            corner_radius=4,
            font=(th.FUENTE, th.TAM_BODY),
        )
        self._chk_force.pack(side="left", padx=(16, 0))

        self._btn_columnas = BotonSecundario(marco_acciones, "⚙ Columnas", self._abrir_columnas)
        self._btn_columnas.pack(side="right")

        self.botones = [self._btn_leer, self._btn_validar, self._btn_exportar]

        barra_pdf = ctk.CTkFrame(contenedor, fg_color='transparent')
        barra_pdf.grid(
            row=7 if modo == MODO_PAGOS else 6,
            column=0, columnspan=3, sticky='ew', pady=(8, 0),
        )
        for texto, comando in [('Vista previa PDF', self._vista_previa_pdf), ('Guardar PDF', self._guardar_pdf), ('PDF selección (ZIP)', self._pdf_seleccion), ('PDF vista (ZIP)', self._pdf_vista)]:
            boton = BotonSecundario(barra_pdf, texto, comando)
            boton.pack(side='left', padx=(0, 6))
            self.botones.append(boton)
        self._barra_pdf = barra_pdf

        # Resumen de operaciones
        self._resumen = ResumenOperacion(contenedor)
        self._resumen.grid(
            row=8 if modo == MODO_PAGOS else 7,
            column=0, columnspan=3, sticky="ew", pady=(16, 0),
        )

        # Progreso
        self._progreso = ctk.CTkProgressBar(
            contenedor, mode="determinate",
            fg_color=th.FONDO_ENTRADA,
            progress_color=th.PRIMARIO,
            corner_radius=4,
            height=6,
        )
        self._progreso.grid(
            row=9 if modo == MODO_PAGOS else 8,
            column=0, columnspan=3, sticky="ew", pady=(8, 0),
        )
        self._progreso.set(0)
        self._lbl_progreso = ctk.CTkLabel(
            contenedor, text="", text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA),
        )
        self._lbl_progreso.grid(
            row=10 if modo == MODO_PAGOS else 9,
            column=0, columnspan=3, sticky="w", pady=(2, 0),
        )

        # Sin espacio reservado: el resumen y el progreso aparecen solo al operar
        self._detalles_usados = False
        self._aplicar_detalles(self.app.detalles_visibles)
        sesion = estado_local.cargar().get('sesion', {}).get('pantallas', {}).get(self.modo, {})
        for clave, valor in sesion.get('filtros', {}).items():
            if clave in self._filtros and isinstance(valor, str):
                self._filtros[clave].insert(0, valor)
        campos_sesion = {
            "fecha": self._fecha,
            "monto": self._monto,
        }
        for clave, entrada in campos_sesion.items():
            valor = sesion.get("filtros", {}).get(clave, "")
            if isinstance(valor, str) and valor:
                entrada.insert(0, valor)
        self._carpeta.set(sesion.get('carpeta', ''))
        vista = sesion.get('vista')
        if self.modo == MODO_PAGOS and vista in dict(VISTAS_PAGOS):
            self._cambiar_vista(dict(VISTAS_PAGOS)[vista])

    def al_alternar_detalles(self, visible: bool) -> None:
        self._aplicar_detalles(visible)

    def _aplicar_detalles(self, visible: bool) -> None:
        if visible and self._detalles_usados:
            self._resumen.grid()
            self._progreso.grid()
            self._lbl_progreso.grid()
        else:
            self._resumen.grid_remove()
            self._progreso.grid_remove()
            self._lbl_progreso.grid_remove()

    def _mostrar_detalles_operacion(self) -> None:
        self._detalles_usados = True
        # En poca altura no reabrir el registro global involuntariamente:
        # respetar el control de detalles para que la tabla conserve altura.
        try:
            baja = bool(getattr(self.app, "_alto_compacto", False))
        except Exception:
            baja = False
        if baja:
            self._aplicar_detalles(self.app.detalles_visibles)
            return
        self.app.mostrar_detalles(True)
        self._aplicar_detalles(True)

    # ── Interfaz adaptable ──────────────────────────────────────────────

    @property
    def totales_colapsados(self) -> bool:
        try:
            return bool(self._totales_panel.colapsado)
        except Exception:
            return False

    def _al_colapsar_totales(self, colapsado: bool) -> None:
        # El usuario toggló manualmente: toma el control y cancela el auto.
        self._totales_colapsado_auto = False

    def fijar_totales_colapsados(self, colapsado: bool, auto: bool = False) -> None:
        colapsado = bool(colapsado)
        try:
            self._totales_panel._cambio_interno = bool(auto)
            self._totales_panel.fijar_colapsado(colapsado)
        finally:
            try:
                self._totales_panel._cambio_interno = False
            except Exception:
                pass
        if auto:
            self._totales_colapsado_auto = colapsado
        else:
            self._totales_colapsado_auto = False

    def aplicar_modo_compacto(self, ancho_compacto: bool, alto_compacto: bool) -> None:
        """Ajusta márgenes, selector REP y totales sin tocar filas/selección."""
        ancho_compacto = bool(ancho_compacto)
        alto_compacto = bool(alto_compacto)
        if (ancho_compacto, alto_compacto) == (self._ancho_compacto, self._alto_compacto):
            return
        anterior_alto = self._alto_compacto
        self._ancho_compacto = ancho_compacto
        self._alto_compacto = alto_compacto
        if ancho_compacto:
            self._lbl_resultados.grid_remove()
        else:
            self._lbl_resultados.grid()
        self._fila_carpeta.grid_configure(pady=(8 if alto_compacto else 24, 6))
        self._marco_acciones.grid_configure(pady=(8 if alto_compacto else 16, 0))
        if self.modo == MODO_PAGOS:
            self._barra_tabla.grid_configure(pady=(6 if alto_compacto else 12, 0))
        # Márgenes compactos para dar aire a la tabla en laptops.
        try:
            if ancho_compacto or alto_compacto:
                self._contenedor.pack_configure(padx=self._padx_compacto, pady=self._pady_compacto)
            else:
                self._contenedor.pack_configure(padx=self._padx_normal, pady=self._pady_normal)
        except Exception:
            pass
        # Refluir tarjetas de totales en ventana estrecha.
        try:
            aplicar = getattr(self._totales_panel, "aplicar_compacto", None)
            if callable(aplicar):
                aplicar(ancho_compacto)
        except Exception:
            pass
        # Poca altura: colapsar totales automáticamente (restaurar al ampliar).
        try:
            if alto_compacto and not anterior_alto:
                if not self._totales_panel.colapsado:
                    self.fijar_totales_colapsados(True, auto=True)
            elif not alto_compacto:
                if self._totales_colapsado_auto and self._totales_panel.colapsado:
                    self.fijar_totales_colapsados(False, auto=True)
                    self._totales_colapsado_auto = False
        except Exception:
            pass
        # Selector REP: ComboBox en estrecha para no empujar "Columnas".
        try:
            self._aplicar_selector_vista(ancho_compacto)
        except Exception:
            pass

    def _aplicar_selector_vista(self, ancho_compacto: bool) -> None:
        if self.modo != MODO_PAGOS or self._seg_vista is None or self._combo_vista is None:
            return
        if ancho_compacto:
            try:
                self._seg_vista.pack_forget()
            except Exception:
                pass
            try:
                if not str(self._combo_vista.winfo_manager()):
                    pass
            except Exception:
                pass
            try:
                self._combo_vista.pack(side="left", padx=(8, 0))
            except Exception:
                pass
        else:
            try:
                self._combo_vista.pack_forget()
            except Exception:
                pass
            try:
                self._seg_vista.pack(side="left", padx=(8, 0))
            except Exception:
                # Si ya estaba visible, pack lo reordena sin duplicar.
                pass
        # Sincronizar valor mostrado con la vista actual.
        titulo = dict(VISTAS_PAGOS).get(self._vista, "Conciliación")
        try:
            self._seg_vista.set(titulo)
        except Exception:
            pass
        try:
            self._combo_vista.set(titulo)
        except Exception:
            pass

    def _columnas_actuales(self) -> list[tuple[str, str, int]]:
        if self.modo == MODO_CFDI40:
            return _COLUMNAS_CFDI40
        if self.modo == MODO_NOMINA:
            return _COLUMNAS_NOMINA
        return self._columnas_vista(self._vista)

    def _columnas_vista(self, vista: str) -> list[tuple[str, str, int]]:
        return {
            "conciliacion": _COLUMNAS_PAGOS_CONCILIACION,
            "facturas_ppd": _COLUMNAS_FACTURAS_PPD,
            "facturas_p": _COLUMNAS_FACTURAS_P,
            "pagos": _COLUMNAS_PAGOS_LISTA,
            "doctos": _COLUMNAS_DOCTOS,
        }.get(vista, _COLUMNAS_PAGOS_CONCILIACION)

    def _clave_columnas(self) -> str:
        if self.modo == MODO_CFDI40:
            return "cfdi40"
        if self.modo == MODO_NOMINA:
            return "nomina"
        return f"pagos_{self._vista}"

    def _titulo_tabla(self) -> str:
        if self.modo == MODO_CFDI40:
            return "XML 4.0"
        if self.modo == MODO_NOMINA:
            return "Recibos de Nómina"
        titulo_vista = dict(VISTAS_PAGOS).get(self._vista, self._vista)
        return f"Conciliación de Pagos — {titulo_vista}"

    def _gestor(self) -> GestorColumnas:
        clave = self._clave_columnas()
        gestor = self._gestores.get(clave)
        if gestor is None:
            gestor = GestorColumnas(self._tabla, clave, self._columnas_actuales(), self._titulo_tabla())
            self._gestores[clave] = gestor
        return gestor

    def _abrir_columnas(self) -> None:
        self._gestor().abrir_dialogo(
            self, al_aplicar=lambda: auto_ajustar_columnas(self._tabla)
        )

    def _cambiar_vista(self, titulo: str) -> None:
        clave = dict((t, c) for c, t in VISTAS_PAGOS).get(titulo, "conciliacion")
        if clave == self._vista:
            # Sincronizar ambos selectores aunque no cambie la vista.
            try:
                if self._seg_vista is not None:
                    self._seg_vista.set(titulo)
            except Exception:
                pass
            try:
                if self._combo_vista is not None:
                    self._combo_vista.set(titulo)
            except Exception:
                pass
            return
        self._vista = clave
        self._configurar_columnas(self._columnas_actuales())
        self._gestor().aplicar()
        self._cargar_tabla()
        try:
            if self._seg_vista is not None:
                self._seg_vista.set(titulo)
        except Exception:
            pass
        try:
            if self._combo_vista is not None:
                self._combo_vista.set(titulo)
        except Exception:
            pass

    def _configurar_columnas(self, cols_def: list[tuple[str, str, int]]) -> None:
        self._tabla.configure(displaycolumns="#all")
        self._tabla.configure(columns=[c[0] for c in cols_def])
        for clave, texto, ancho in cols_def:
            self._tabla.heading(
                clave, text=texto,
                command=lambda c=clave: self._ordenar_columna(c),
            )
            self._tabla.column(clave, width=ancho, anchor="w", stretch=False)

    def _programar_carga_filtrada(self) -> None:
        if self._filtro_after is not None:
            try:
                self.after_cancel(self._filtro_after)
            except tk.TclError:
                pass
        self._filtro_after = self.after(220, self._cargar_tabla)

    def _fila_pasa_filtros(self, valores) -> bool:
        columnas = list(self._tabla["columns"])
        por_clave = {
            clave: "" if valor is None else str(valor)
            for clave, valor in zip(columnas, valores)
        }
        for clave, entrada in self._filtros.items():
            filtro = entrada.get().strip().casefold()
            if clave not in por_clave:
                # RFC es un filtro SQL sobre emisor/receptor y no una columna
                # visible única; UUID/serie/folio sí suelen estar presentes.
                continue
            if filtro and filtro not in por_clave.get(clave, "").casefold():
                return False

        fecha_filtro = SelectorFecha._parsear(self._fecha.get())
        if self._fecha.get().strip() and fecha_filtro:
            fechas = [
                SelectorFecha._parsear(por_clave.get(clave, "")[:10])
                for clave in ("fecha", "fecha_rep", "fecha_emision", "fecha_pago", "fecha_timbrado")
                if por_clave.get(clave, "")
            ]
            fecha = next((valor for valor in fechas if valor), None)
            if fecha != fecha_filtro:
                return False

        monto_filtro = self._numero_filtro(self._monto.get())
        if monto_filtro is not None:
            montos = (
                "total", "total_factura", "monto", "monto_pagos", "pagado",
                "saldo_pendiente", "saldo_insoluto",
            )
            monto = next(
                (self._numero_filtro(por_clave.get(clave, "")) for clave in montos if por_clave.get(clave, "") != ""),
                None,
            )
            if monto is None or monto != monto_filtro:
                return False
        return True

    @staticmethod
    def _numero_filtro(valor: str) -> float | None:
        texto = str(valor or "").strip().replace(",", "").replace("$", "")
        if not texto:
            return None
        try:
            return float(texto)
        except ValueError:
            return None

    def _insertar_fila(self, _parent="", _index="end", *, values=(), tags=()) -> None:
        """Inserta una fila solo si coincide con búsqueda/filtros activos."""
        if self._fila_pasa_filtros(values):
            self._tabla.insert(_parent, _index, values=values, tags=tags)

    def _ordenar_columna(self, clave: str) -> None:
        if self._orden_columna == clave:
            self._orden_desc = not self._orden_desc
        else:
            self._orden_columna = clave
            self._orden_desc = False
        self._actualizar_titulo_orden()
        self._ordenar_filas()

    def _actualizar_titulo_orden(self) -> None:
        for clave, texto, _ancho in self._columnas_actuales():
            indicador = " ▼" if self._orden_columna == clave and self._orden_desc else " ▲" if self._orden_columna == clave else ""
            self._tabla.heading(clave, text=f"{texto}{indicador}")

    def _ordenar_filas(self) -> None:
        if not self._orden_columna or self._orden_columna not in self._tabla["columns"]:
            if self._orden_columna not in self._tabla["columns"]:
                self._orden_columna = None
            return
        items = list(self._tabla.get_children())
        indice = list(self._tabla["columns"]).index(self._orden_columna)

        def clave_orden(item):
            valor = self._tabla.item(item, "values")[indice]
            texto = "" if valor is None else str(valor).strip()
            try:
                return (1, float(texto.replace(",", "").replace("$", "")))
            except ValueError:
                return (0 if texto else -1, texto.casefold())

        for item in sorted(items, key=clave_orden, reverse=self._orden_desc):
            self._tabla.move(item, "", "end")

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def al_mostrar(self) -> None:
        self._cliente_cargado = self.app.cliente_actual
        self._cargar_tabla()

    def _filtro_kwargs(self) -> dict[str, str]:
        filtros = {
            clave: entrada.get().strip()
            for clave, entrada in self._filtros.items()
            if clave in {"uuid", "rfc", "serie", "folio"} and entrada.get().strip()
        }
        return filtros

    def _consulta(self, catalogo: Catalogo, **kwargs):
        """Consulta siempre el cliente activo y aplica los filtros visibles."""
        kwargs.update(self._filtro_kwargs())
        return catalogo.consulta(cliente=self._cliente_cargado, **kwargs)

    def _aplicar_filtros(self) -> None:
        self._cargar_tabla()

    def _limpiar_filtros(self) -> None:
        for entrada in self._filtros.values():
            entrada.delete(0, "end")
        for entrada in (self._fecha, self._monto):
            entrada.delete(0, "end")
        self._cargar_tabla()

    def _elegir_carpeta(self) -> None:
        carpeta = filedialog.askdirectory(parent=self, title="Seleccionar carpeta con los XMLs")
        if carpeta:
            self._carpeta.set(carpeta)

    # ── Leer ──────────────────────────────────────────────────────────────────

    def _leer(self) -> None:
        texto_rutas = self._carpeta.get().strip()
        rutas = [Path(r.strip()) for r in texto_rutas.split(";") if r.strip()]
        rutas_validas = [r for r in rutas if r.is_dir()]
        if not rutas_validas:
            messagebox.showerror(
                "Carpeta inválida",
                "Elige al menos una carpeta existente con archivos XML.",
                parent=self,
            )
            return
        cliente = self.app.cliente_actual
        if not cliente:
            messagebox.showinfo("Cliente", "Selecciona un cliente antes de leer XML.", parent=self)
            return
        etiqueta = cliente
        self._cliente_cargado = cliente

        limpiar_antes = False
        pantalla_ajustes = getattr(self.app, "_pantallas", {}).get("ajustes")
        if pantalla_ajustes and hasattr(pantalla_ajustes, "limpiar_al_leer"):
            limpiar_antes = pantalla_ajustes.limpiar_al_leer.get()

        self._resumen.mostrar("Leyendo XMLs…")
        self._mostrar_detalles_operacion()
        self.app.ejecutar(
            lambda: self._run_leer(rutas_validas, etiqueta, limpiar_antes),
            lambda res: self._presentar_leer(res),
            f"Leyendo XMLs desde {len(rutas_validas)} carpeta(s)",
        )

    def _run_leer(self, carpetas: list[Path], cliente: str, limpiar_antes: bool):
        with Catalogo(self.app.db_path) as catalogo:
            return importar_carpetas(catalogo, carpetas, cliente, limpiar_antes=limpiar_antes)

    def _presentar_leer(self, res) -> None:
        self._cargar_tabla()
        partes = [
            (f"Procesados: {res.procesados}", "gris"),
            (f"Insertados: {res.insertados}", "verde"),
            (f"Omitidos (ya existían): {res.omitidos}", "ambar"),
        ]
        if res.errores:
            partes.append((f"Con error: {res.errores}", "rojo"))
        self._resumen.mostrar(
            "Lectura terminada",
            tono="verde" if not res.errores else "rojo",
            detalle=" | ".join(t for t, _ in partes),
        )
        if res.detalle_errores:
            self.app.registro("Errores de lectura (primeros 10):")
            for err in res.detalle_errores[:10]:
                self.app.registro(f"  {err}")
        self.app.actualizar_resumen()

    # ── Validar ───────────────────────────────────────────────────────────────

    def _validar(self) -> None:
        cliente = self.app.cliente_actual or self._cliente_cargado
        force = self._force.get()
        config = ConfigLote(delay_segundos=2.0)
        self._resumen.mostrar("Consultando estatus SAT…", detalle="Preparando la consulta.")
        self._progreso.set(0)
        self._mostrar_detalles_operacion()
        self.app.ejecutar(
            lambda progreso: self._run_validar(cliente, force, config, progreso),
            lambda res: self._presentar_validar(res),
            "Consultando estatus SAT (puede tardar varios minutos)",
            con_progreso=True,
        )

    def _run_validar(self, cliente, force, config, progreso):
        with Catalogo(self.app.db_path) as catalogo:
            resultado = consultar_lote(
                catalogo, config=config, cliente=cliente, force=force, progreso=progreso
            )
            return resultado

    def _presentar_validar(self, res) -> None:
        self._cargar_tabla()
        self._lbl_progreso.configure(text=f"{res.consultados} comprobantes consultados")
        self._progreso.set(1)
        partes = [
            (f"Consultados: {res.consultados}", "gris"),
            (f"Vigentes: {res.vigentes}", "verde"),
            (f"Cancelados: {res.cancelados}", "rojo"),
            (f"No encontrados: {res.no_encontrados}", "gris"),
            (f"Fallos: {res.fallos}", "ambar"),
        ]
        self._resumen.mostrar(
            "Consulta terminada",
            tono="verde" if not res.fallos else "ambar",
            detalle=" | ".join(t for t, _ in partes),
        )
        if res.detalle:
            self.app.registro("Fallos del lote (primeros 10):")
            for fallo in res.detalle[:10]:
                self.app.registro(f"  {fallo}")
        self.app.actualizar_resumen()

    def on_progreso(self, actual: int, total: int) -> None:
        if total > 0:
            self._progreso.set(actual / total)
            self._lbl_progreso.configure(text=f"Consultando… [{actual}/{total}]")

    # ── Exportar ──────────────────────────────────────────────────────────────

    def _exportar(self) -> None:
        destino = Path(self._destino_default())
        ruta = filedialog.asksaveasfilename(
            parent=self,
            title="Guardar Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialdir=Config().base / "salidas",
            initialfile=destino.name,
        )
        if not ruta:
            return
        cliente = self.app.cliente_actual or self._cliente_cargado
        self._resumen.mostrar("Generando Excel…")
        self._mostrar_detalles_operacion()
        self.app.ejecutar(
            lambda: self._run_exportar(Path(ruta), cliente),
            lambda ruta_ok: self._presentar_exportar(ruta_ok),
            f"Generando reportes ({self.modo})",
        )

    def _destino_default(self) -> str:
        hoy = datetime.now().strftime("%Y%m%d")
        nombres = {MODO_CFDI40: "listado", MODO_PAGOS: "pagos", MODO_NOMINA: "nomina"}
        nombre = nombres.get(self.modo, "reporte")
        return str(Config().base / "salidas" / f"{nombre}_{hoy}.xlsx")

    def _run_exportar(self, destino: Path, cliente):
        with Catalogo(self.app.db_path) as catalogo:
            if self.modo == MODO_CFDI40:
                return exportar_listado(catalogo, destino, cliente=cliente)
            if self.modo == MODO_PAGOS:
                return exportar_pagos(catalogo, destino, cliente=cliente)
            return exportar_nomina(catalogo, destino, cliente=cliente)

    def _presentar_exportar(self, ruta) -> None:
        self.app.registro(f"Excel generado: {ruta}")
        self._resumen.mostrar(
            "Excel generado",
            tono="verde",
            detalle=str(ruta),
            accion=("Abrir carpeta", lambda: self._abrir_carpeta(ruta)),
        )

    def _abrir_carpeta(self, ruta) -> None:
        try:
            abrir_local(Path(ruta).parent)
        except OSError as exc:
            messagebox.showerror("No se pudo abrir la carpeta", str(exc), parent=self)

    def _doble_clic_pdf(self, event) -> None:
        item = self._tabla.identify_row(event.y)
        if item:
            self._tabla.selection_set(item)
            self._vista_previa_pdf()

    def _menu_pdf(self, event) -> None:
        item = self._tabla.identify_row(event.y)
        if not item:
            return
        if item not in self._tabla.selection():
            self._tabla.selection_set(item)
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label='Vista previa PDF', command=self._vista_previa_pdf)
        menu.add_command(label='Guardar PDF', command=self._guardar_pdf)
        menu.add_command(label='PDF de selección (ZIP)', command=self._pdf_seleccion)
        menu.tk_popup(event.x_root, event.y_root)

    def _documentos_pdf(self, todos=False, individual=False):
        items = self._tabla.get_children() if todos else self._tabla.selection()
        if not items:
            messagebox.showinfo('PDF', 'Selecciona un comprobante en la tabla.' if not todos else 'La vista no tiene comprobantes.', parent=self)
            return []
        if individual and len(items) != 1:
            messagebox.showinfo('PDF', 'Selecciona una sola fila para abrir o guardar un PDF.', parent=self)
            return []
        columnas = list(self._tabla['columns'])
        uuids = []
        for item in items:
            fila = dict(zip(columnas, self._tabla.item(item, 'values')))
            uuid = fila.get('uuid') or fila.get('uuid_rep') or fila.get('uuid_doc')
            if uuid and uuid not in uuids:
                uuids.append(uuid)
        with Catalogo(self.app.db_path) as cat:
            documentos = {f['uuid']: dict(f) for f in cat.consulta(cliente=self._cliente_cargado)}
        encontrados = [documentos[u] for u in uuids if u in documentos]
        if not encontrados:
            messagebox.showinfo('PDF', 'El XML de esta fila no está en el catálogo del cliente.', parent=self)
        return encontrados

    def _vista_previa_pdf(self):
        documentos = self._documentos_pdf(individual=True)
        if not documentos:
            return
        doc = documentos[0]
        import uuid
        destino = Config().base / 'cache' / 'pdf' / f'{uuid.uuid4().hex}_{nombre_pdf(doc["uuid"])}'
        self.app.ejecutar(lambda: generar_pdf(Path(doc['ruta']), destino), lambda ruta: abrir_vista_previa(self, ruta), 'Generando vista previa PDF')

    def _guardar_pdf(self):
        documentos = self._documentos_pdf(individual=True)
        if not documentos:
            return
        doc = documentos[0]
        destino = filedialog.asksaveasfilename(parent=self, title='Guardar comprobante PDF', initialfile=nombre_pdf(doc['uuid']), defaultextension='.pdf', filetypes=[('PDF', '*.pdf')])
        if destino:
            self.app.ejecutar(lambda: generar_pdf(Path(doc['ruta']), Path(destino)), self._pdf_guardado, 'Guardando PDF')

    def _pdf_guardado(self, ruta):
        self.app.registro(f'PDF guardado: {ruta}')
        self._mostrar_detalles_operacion()
        self._resumen.mostrar('PDF guardado', tono='verde', detalle=str(ruta), accion=('Abrir carpeta', lambda: abrir_local(Path(ruta).parent)))

    def _pdf_seleccion(self):
        self._pdf_lote(False)

    def _pdf_vista(self):
        self._pdf_lote(True)

    def _pdf_lote(self, todos):
        documentos = self._documentos_pdf(todos=todos)
        if not documentos:
            return
        destino = filedialog.asksaveasfilename(parent=self, title=f'Guardar {len(documentos)} PDF en ZIP', initialfile=f'pdf_{self._cliente_cargado}_{datetime.now():%Y%m%d}.zip', defaultextension='.zip', filetypes=[('ZIP de PDF', '*.zip')])
        if destino:
            self.app.ejecutar(lambda: exportar_lote([Path(d['ruta']) for d in documentos], Path(destino)), self._pdf_lote_guardado, f'Generando {len(documentos)} PDF')

    def _pdf_lote_guardado(self, resultado):
        self._pdf_guardado(resultado.ruta)
        self._resumen.mostrar(f'{resultado.generados} PDF guardados; {len(resultado.errores)} errores', tono='rojo' if resultado.errores else 'verde', detalle=str(resultado.ruta), accion=('Abrir carpeta', lambda: abrir_local(resultado.ruta.parent)))

    def estado_sesion(self):
        filtros = {k: v.get() for k, v in self._filtros.items()}
        filtros.update({
            "fecha": self._fecha.get(),
            "monto": self._monto.get(),
        })
        return {'filtros': filtros, 'carpeta': self._carpeta.get(), 'vista': self._vista}

    # ── Tabla ─────────────────────────────────────────────────────────────────

    def _cargar_tabla(self) -> None:
        for item in self._tabla.get_children():
            self._tabla.delete(item)
        with Catalogo(self.app.db_path) as catalogo:
            if self.modo == MODO_PAGOS:
                self._totales_panel.actualizar(catalogo, self._cliente_cargado)
                {
                    "conciliacion": self._filas_pagos,
                    "facturas_ppd": self._filas_facturas_ppd,
                    "facturas_p": self._filas_facturas_p,
                    "pagos": self._filas_pagos_lista,
                    "doctos": self._filas_doctos,
                }[self._vista](catalogo)
            else:
                filas_db = [dict(f) for f in self._consulta(catalogo)]
                self._totales_panel.actualizar(filas_db)
                if self.modo == MODO_CFDI40:
                    self._filas_cfdi(catalogo)
                else:
                    self._filas_nomina(catalogo)

        auto_ajustar_columnas(self._tabla)
        self._actualizar_titulo_orden()
        self._ordenar_filas()
        try:
            total = len(self._tabla.get_children())
            activos = len(self._filtro_kwargs())
            activos += sum(
                bool(entrada.get().strip())
                for entrada in (self._fecha, self._monto)
            )
            self._lbl_resultados.configure(
                text=f"{total:,} registros" + (f" · {activos} filtros" if activos else "")
            )
        except Exception:
            pass

    def _filas_facturas_ppd(self, catalogo: Catalogo) -> None:
        doctos_por_uuid: dict[str, list] = {}
        for pago in catalogo.consultar_pagos(cliente=self._cliente_cargado):
            for doc in catalogo.consultar_doctos(pago["id"]):
                doctos_por_uuid.setdefault(doc["uuid_doc"], []).append(doc)

        for i, f in enumerate(self._consulta(catalogo)):
            if f["metodo_pago"] != "PPD" or f["tipo_comprobante"] not in ("I", "E"):
                continue
            base = "impar" if i % 2 == 1 else "par"
            total = _numero(f["total"]) or 0.0
            docs = doctos_por_uuid.get(f["uuid"], [])
            pagado = sum(_numero(d["imp_pagado"]) or 0.0 for d in docs)
            if not docs:
                estado = "No pagada"
            else:
                ult_doc = max(docs, key=lambda x: x["num_parcialidad"] or 0)
                insoluto = _numero(ult_doc["imp_saldo_insoluto"]) or 0.0
                estado = "Totalmente pagada" if insoluto <= 0.01 else "Parcialmente pagada"
            self._insertar_fila(
                "", "end",
                values=(
                    f["cliente"],
                    f["estatus"] or "Sin validar",
                    f["es_cancelable"] or "",
                    f["estatus_cancelacion"] or "",
                    f["uuid"],
                    f["serie"] or "",
                    f["folio"] or "",
                    _breve(f["fecha"]),
                    _breve(f["fecha_timbrado"]),
                    f["emisor_rfc"] or "",
                    f["emisor_nombre"] or "",
                    f["receptor_rfc"] or "",
                    f["receptor_nombre"] or "",
                    f["moneda"] or "",
                    total,
                    pagado,
                    total - pagado,
                    estado,
                    f["ruta"],
                ),
                tags=(base,),
            )

    def _filas_facturas_p(self, catalogo: Catalogo) -> None:
        resumen_rep: dict[str, tuple[int, float]] = {}
        for pago in catalogo.consultar_pagos(cliente=self._cliente_cargado):
            n, m = resumen_rep.get(pago["comprobante_uuid"], (0, 0.0))
            resumen_rep[pago["comprobante_uuid"]] = (n + 1, m + (_numero(pago["monto"]) or 0.0))

        for i, f in enumerate(self._consulta(catalogo)):
            if f["tipo_comprobante"] != "P":
                continue
            base = "impar" if i % 2 == 1 else "par"
            n_pagos, monto = resumen_rep.get(f["uuid"], (0, 0.0))
            self._insertar_fila(
                "", "end",
                values=(
                    f["cliente"],
                    f["estatus"] or "Sin validar",
                    f["es_cancelable"] or "",
                    f["estatus_cancelacion"] or "",
                    f["uuid"],
                    f["serie"] or "",
                    f["folio"] or "",
                    _breve(f["fecha"]),
                    _breve(f["fecha_timbrado"]),
                    f["emisor_rfc"] or "",
                    f["emisor_nombre"] or "",
                    f["receptor_rfc"] or "",
                    f["receptor_nombre"] or "",
                    f["moneda"] or "",
                    _numero(f["total"]),
                    n_pagos,
                    monto,
                    f["ruta"],
                ),
                tags=(base,),
            )

    def _filas_pagos_lista(self, catalogo: Catalogo) -> None:
        comprobantes = {f["uuid"]: f for f in self._consulta(catalogo)}
        for i, pago in enumerate(catalogo.consultar_pagos(cliente=self._cliente_cargado)):
            rep = comprobantes.get(pago["comprobante_uuid"])
            base = "impar" if i % 2 == 1 else "par"
            self._insertar_fila(
                "", "end",
                values=(
                    rep["cliente"] if rep else pago["cliente"],
                    pago["comprobante_uuid"],
                    rep["serie"] if rep else "",
                    rep["folio"] if rep else "",
                    rep["estatus"] if rep else "Sin validar",
                    _breve(pago["fecha_pago"]),
                    describir(FORMA_PAGO, pago["forma_pago"]),
                    pago["moneda"] or "",
                    _numero(pago["monto"]),
                    pago["num_operacion"] or "",
                    pago["cta_ordenante"] or "",
                    pago["cta_beneficiario"] or "",
                    pago["rfc_emisor_cta_ord"] or "",
                    len(catalogo.consultar_doctos(pago["id"])),
                ),
                tags=(base,),
            )

    def _filas_doctos(self, catalogo: Catalogo) -> None:
        comprobantes = {f["uuid"]: f for f in self._consulta(catalogo)}
        todo = {f["uuid"]: f for f in catalogo.consulta()}
        contador_filas = 0
        for pago in catalogo.consultar_pagos(cliente=self._cliente_cargado):
            rep = comprobantes.get(pago["comprobante_uuid"])
            for doc in catalogo.consultar_doctos(pago["id"]):
                factura = todo.get(doc["uuid_doc"])
                fecha = (factura["fecha"] or "") if factura else ""
                base = "impar" if contador_filas % 2 == 1 else "par"
                self._insertar_fila(
                    "", "end",
                    values=(
                        pago["cliente"],
                        (factura["estatus"] if factura else "") or "Sin validar",
                        factura["no_certificado_emisor"] if factura else "",
                        factura["no_certificado_sat"] if factura else "",
                        _breve(fecha),
                        _breve(factura["fecha_timbrado"]) if factura else "",
                        fecha[:4],
                        fecha[5:7],
                        fecha[8:10],
                        doc["serie"] or (factura["serie"] if factura else "") or "",
                        doc["folio"] or (factura["folio"] if factura else "") or "",
                        doc["uuid_doc"],
                        factura["emisor_rfc"] if factura else "",
                        factura["emisor_nombre"] if factura else "",
                        describir(REGIMEN_FISCAL, factura["emisor_regimen_fiscal"]) if factura else "",
                        _breve(pago["fecha_pago"]),
                        describir(FORMA_PAGO, pago["forma_pago"]),
                        _numero(pago["monto"]),
                        doc["num_parcialidad"] or "",
                        _numero(doc["imp_saldo_ant"]),
                        _numero(doc["imp_pagado"]),
                        _numero(doc["imp_saldo_insoluto"]),
                        pago["comprobante_uuid"],
                        rep["serie"] if rep else "",
                        rep["folio"] if rep else "",
                        factura["ruta"] if factura else "",
                    ),
                    tags=(base,),
                )
                contador_filas += 1

    def _filas_cfdi(self, catalogo: Catalogo) -> None:
        for i, fila in enumerate(self._consulta(catalogo)):
            if fila["tipo_comprobante"] in ("P", "N"):
                continue
            base = "impar" if i % 2 == 1 else "par"
            traslados = _importes(fila["traslados_json"])
            retenciones = _importes(fila["retenciones_json"])
            complementos = [
                c for c in (fila["complementos"] or "").split(", ") if c and c not in COMPLEMENTOS_IGNORADOS
            ]
            self._insertar_fila(
                "", "end",
                values=(
                    "",  # Verificado o Asoc
                    fila["estatus"] or "Sin validar",
                    fila["es_cancelable"] or "",
                    fila["estatus_cancelacion"] or "",
                    fila["relaciones"] or "",
                    fila["uuid"],
                    fila["serie"] or "",
                    fila["folio"] or "",
                    fila["version"] or "",
                    describir(TIPO_COMPROBANTE, fila["tipo_comprobante"]),
                    _breve(fila["fecha_timbrado"]),
                    _breve(fila["fecha"]),
                    fila["lugar_expedicion"] or "",
                    fila["emisor_rfc"] or "",
                    fila["emisor_nombre"] or "",
                    describir(REGIMEN_FISCAL, fila["emisor_regimen_fiscal"]),
                    fila["receptor_rfc"] or "",
                    fila["receptor_nombre"] or "",
                    describir(USO_CFDI, fila["uso_cfdi"]),
                    describir(REGIMEN_FISCAL, fila["regimen_fiscal_receptor"]),
                    fila["domicilio_fiscal_receptor"] or "",
                    describir(FORMA_PAGO, fila["forma_pago"]),
                    fila["metodo_pago"] or "",
                    ", ".join(complementos) or "",
                    fila["conceptos"] or "",
                    "",  # Complementos conceptos
                    _numero(fila["subtotal"]),
                    _numero(fila["descuento"]),
                    _suma_importes(traslados),
                    _suma_importes(retenciones),
                    _numero(fila["total"]),
                    fila["moneda"] or "",
                    _base_por_factor(traslados, "Exento"),
                    _base_por_factor(traslados, "Tasa")
                    if any(
                        t.get("tasa_o_cuota") == "0"
                        for t in traslados
                        if t.get("impuesto") == "002" and t.get("tipo_factor") == "Tasa"
                    )
                    else "",
                    _traslado_por_tasa(traslados, "0.08"),
                    _traslado_por_tasa(traslados, "0.16"),
                    _retencion_por_impuesto(retenciones, "001"),
                    _retencion_por_impuesto(retenciones, "002"),
                    _retencion_por_impuesto(retenciones, "003"),
                    _retencion_por_tasa(retenciones, "001", "0.0125"),
                    _retencion_por_tasa(retenciones, "002", "0.106667"),
                    _retencion_por_tasa(retenciones, "002", "0.08"),
                    _retencion_por_tasa(retenciones, "002", "0.06"),
                    _retencion_por_tasa(retenciones, "002", "0.16"),
                    fila["no_certificado_sat"] or "",
                    fila["no_certificado_emisor"] or "",
                    fila["ruta"],
                ),
                tags=(base,),
            )

    def _filas_pagos(self, catalogo: Catalogo) -> None:
        comprobantes = {f["uuid"]: f for f in self._consulta(catalogo)}
        todo = {f["uuid"]: f for f in catalogo.consulta()}
        contador_filas = 0
        for pago in catalogo.consultar_pagos(cliente=self._cliente_cargado):
            rep = comprobantes.get(pago["comprobante_uuid"])
            for doc in catalogo.consultar_doctos(pago["id"]):
                factura = todo.get(doc["uuid_doc"])
                base = "impar" if contador_filas % 2 == 1 else "par"
                est_rep = rep["estatus"] if rep else "Sin validar"
                est_fact = factura["estatus"] if factura else "Sin validar"
                self._insertar_fila(
                    "", "end",
                    values=(
                        rep["cliente"] if rep else "",
                        pago["comprobante_uuid"],
                        rep["serie"] if rep else "",
                        rep["folio"] if rep else "",
                        _breve(rep["fecha"]) if rep else "",
                        est_rep,
                        _breve(pago["fecha_pago"]),
                        describir(FORMA_PAGO, pago["forma_pago"]),
                        pago["moneda"] or "",
                        _numero(pago["monto"]),
                        pago["num_operacion"] or "",
                        pago["cta_ordenante"] or "",
                        pago["cta_beneficiario"] or "",
                        pago["rfc_emisor_cta_ord"] or "",
                        doc["uuid_doc"] or "",
                        doc["serie"] or "",
                        doc["folio"] or "",
                        doc["moneda"] or "",
                        doc["num_parcialidad"] or "",
                        _numero(doc["imp_saldo_ant"]),
                        _numero(doc["imp_pagado"]),
                        _numero(doc["imp_saldo_insoluto"]),
                        est_fact,
                        est_fact,
                        rep["es_cancelable"] if rep else "",
                        rep["estatus_cancelacion"] if rep else "",
                        _breve(rep["fecha_timbrado"]) if rep else "",
                        describir(TIPO_COMPROBANTE, rep["tipo_comprobante"]) if rep else "",
                        rep["ruta"] if rep else "",
                        factura["es_cancelable"] if factura else "",
                        factura["estatus_cancelacion"] if factura else "",
                        _breve(factura["fecha_timbrado"]) if factura else "",
                        describir(TIPO_COMPROBANTE, factura["tipo_comprobante"]) if factura else "",
                        _numero(factura["total"]) if factura else "",
                        factura["ruta"] if factura else "",
                    ),
                    tags=(base,),
                )
                contador_filas += 1

    def _filas_nomina(self, catalogo: Catalogo) -> None:
        for i, fila in enumerate(self._consulta(catalogo, tipo="N")):
            base = "impar" if i % 2 == 1 else "par"
            path_xml = Path(fila["ruta"])
            nom = None
            if path_xml.is_file():
                try:
                    comp = parse_comprobante(path_xml)
                    nom = parse_nomina(comp)
                except Exception:
                    pass

            reg_patronal = nom.registro_patronal if nom else ""
            curp = nom.curp if nom else ""
            num_emp = nom.num_empleado if nom else ""
            puesto = nom.puesto if nom else ""
            tipo_nom = nom.tipo_nomina if nom else ""
            f_pago = nom.fecha_pago.strftime("%Y-%m-%d") if (nom and nom.fecha_pago) else ""
            f_ini = nom.fecha_inicial_pago.strftime("%Y-%m-%d") if (nom and nom.fecha_inicial_pago) else ""
            f_fin = nom.fecha_final_pago.strftime("%Y-%m-%d") if (nom and nom.fecha_final_pago) else ""
            dias_pag = float(nom.num_dias_pagados) if (nom and nom.num_dias_pagados) else ""
            period = nom.periodicidad_pago if nom else ""
            t_per = float(nom.total_percepciones) if (nom and nom.total_percepciones) else ""
            t_ded = float(nom.total_deducciones) if (nom and nom.total_deducciones) else ""
            t_otr = float(nom.total_otros_pagos) if (nom and nom.total_otros_pagos) else ""

            self._insertar_fila(
                "", "end",
                values=(
                    fila["cliente"],
                    fila["estatus"] or "Sin validar",
                    fila["es_cancelable"] or "",
                    fila["estatus_cancelacion"] or "",
                    fila["uuid"],
                    fila["serie"] or "",
                    fila["folio"] or "",
                    _breve(fila["fecha_timbrado"]),
                    _breve(fila["fecha"]),
                    fila["emisor_rfc"] or "",
                    fila["emisor_nombre"] or "",
                    reg_patronal,
                    fila["receptor_rfc"] or "",
                    fila["receptor_nombre"] or "",
                    curp,
                    num_emp,
                    puesto,
                    tipo_nom,
                    f_pago,
                    f_ini,
                    f_fin,
                    dias_pag,
                    period,
                    t_per,
                    t_ded,
                    t_otr,
                    _numero(fila["subtotal"]),
                    _numero(fila["descuento"]),
                    _numero(fila["total"]),
                    fila["moneda"] or "",
                    fila["ruta"],
                ),
                tags=(base,),
            )
