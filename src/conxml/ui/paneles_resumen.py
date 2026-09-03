"""Paneles de resumen (extraído de pantalla_admin)."""

from __future__ import annotations

import customtkinter as ctk

from conxml.catalog.db import Catalogo
from conxml.ui import theme as th
from conxml.ui.widgets import PanelCard

class PanelResumenTotales(PanelCard):
    """Panel de resumen para XML 4.0 (Totales, Vigentes, Cancelados)."""

    def __init__(self, parent: ctk.CTkFrame) -> None:
        super().__init__(parent)
        self._filas: list[dict] = []

        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.pack(fill="x", expand=True, padx=12, pady=6)

        header = ctk.CTkFrame(contenedor, fg_color="transparent")
        header.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            header, text="RESUMEN DE TOTALES", text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
        ).pack(side="left")

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

    def __init__(self, parent: ctk.CTkFrame) -> None:
        super().__init__(parent)
        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.pack(fill="x", expand=True, padx=12, pady=6)

        header = ctk.CTkFrame(contenedor, fg_color="transparent")
        header.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            header, text="RESUMEN DE CONCILIACIÓN DE PAGOS", text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
        ).pack(side="left")

        self.grid_pagos = ctk.CTkFrame(contenedor, fg_color="transparent")
        self.grid_pagos.pack(fill="x")
        for col in range(7):
            self.grid_pagos.columnconfigure(col, weight=1, uniform="pagos")

        self._labels_cnt: dict[str, ctk.CTkLabel] = {}
        self._labels_monto: dict[str, ctk.CTkLabel] = {}

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
