"""Pantalla de resumen: métricas del catálogo y acceso rápido al flujo."""

from __future__ import annotations

import customtkinter as ctk

from conxml.catalog.db import Catalogo
from conxml.ui import theme as th
from conxml.ui.widgets import (
    BotonPrimario,
    Card,
    Encabezado,
    Insignia,
    Metrica,
    PanelCard,
    TarjetaAccion,
)

ACCIONES = [
    ("admin40", "Administración de XML 4.0",
     "Lee los XML de una carpeta, previsualiza su información, valida estatus SAT "
     "y exporta el listado completo a Excel."),
    ("pagos", "Control y conciliación de pagos",
     "Lee los complementos de pago (REP), valida su estatus ante el SAT "
     "y genera la conciliación detallada en Excel."),
]


class PantallaResumen(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.botones: list = []

        self._contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self._contenedor.pack(fill="both", expand=True, padx=32, pady=24)
        self._contenedor.columnconfigure(0, weight=1)

        Encabezado(
            self._contenedor,
            "ConXml — Catálogo de comprobantes",
            "Importa los XML de tus clientes, valida su estatus ante el SAT y genera los reportes Excel.",
        ).pack(anchor="w", fill="x")

        ctk.CTkLabel(
            self._contenedor, text="RESUMEN DEL CATÁLOGO",
            text_color=th.TEXTO_SECUNDARIO, font=(th.FUENTE, th.TAM_NOTA, "bold"),
        ).pack(anchor="w", pady=(20, 8))

        self._metricas = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        self._metricas.pack(fill="x")

        ctk.CTkLabel(
            self._contenedor, text="¿QUÉ QUIERES HACER?",
            text_color=th.TEXTO_SECUNDARIO, font=(th.FUENTE, th.TAM_NOTA, "bold"),
        ).pack(anchor="w", pady=(24, 8))

        self._acciones = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        self._acciones.pack(fill="x")

        for i, (clave, titulo, descripcion) in enumerate(ACCIONES):
            self._acciones.columnconfigure(i % 2, weight=1, uniform="acciones")
            TarjetaAccion(
                self._acciones,
                titulo=titulo,
                descripcion=descripcion,
                numero=str(i + 1),
                comando=lambda c=clave: self.app.navegar(c),
                wraplength=380,
            ).grid(
                row=i // 2, column=i % 2, sticky="nsew",
                padx=(0, 12 if i % 2 == 0 else 0), pady=(0, 12),
            )

        self._estado = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        self._estado.pack(fill="x", pady=(20, 0))

    def al_mostrar(self) -> None:
        self.actualizar_metricas()

    def actualizar_metricas(self) -> None:
        def leer():
            with Catalogo(self.app.db_path) as catalogo:
                return {
                    "total": catalogo.contar("comprobantes"),
                    "estatus": catalogo.conteo_estatus(),
                    "errores": catalogo.contar("errores"),
                    "clientes": len(catalogo.clientes()),
                }

        self.app.ejecutar(leer, self._presentar, "Leyendo resumen del catálogo")

    def _presentar(self, datos: dict) -> None:
        for marco in (self._metricas, self._estado):
            for hijo in marco.winfo_children():
                hijo.destroy()

        est = datos["estatus"]
        total = datos["total"]
        fila = ctk.CTkFrame(self._metricas, fg_color="transparent")
        fila.pack(fill="x")
        for col in range(4):
            fila.columnconfigure(col, weight=1, uniform="metricas")

        if total:
            Metrica(fila, "Comprobantes", str(total), tono="azul").grid(
                row=0, column=0, sticky="nsew", padx=(0, 12)
            )
            Metrica(fila, "Vigentes", str(est["Vigente"]), tono="verde").grid(
                row=0, column=1, sticky="nsew", padx=(0, 12)
            )
            Metrica(fila, "Cancelados", str(est["Cancelado"]), tono="rojo").grid(
                row=0, column=2, sticky="nsew", padx=(0, 12)
            )
            Metrica(fila, "Sin validar", str(est["Sin validar"]), tono="ambar").grid(
                row=0, column=3, sticky="nsew"
            )

            etiquetas = ctk.CTkFrame(self._metricas, fg_color="transparent")
            etiquetas.pack(fill="x", pady=(12, 0))
            Insignia(etiquetas, f"Clientes: {datos['clientes']}", tono="gris").pack(
                side="left", padx=(0, 8)
            )
            Insignia(etiquetas, f"No encontrados: {est['No Encontrado']}", tono="gris").pack(
                side="left", padx=(0, 8)
            )
            if datos["errores"]:
                Insignia(etiquetas, f"Archivos con error: {datos['errores']}", tono="rojo").pack(
                    side="left"
                )
        else:
                for col in range(4):
                    Card(fila, height=72).grid(row=0, column=col, sticky="nsew", padx=(0, 12) if col < 3 else (0, 0))

        self._presentar_estado(total, est["Sin validar"])

    def _presentar_estado(self, total: int, sin_validar: int) -> None:
        tarjeta = Card(self._estado)
        tarjeta.pack(fill="x")
        if total == 0:
            ctk.CTkLabel(
                tarjeta, text="Todavía no hay comprobantes en el catálogo",
                text_color=th.TEXTO, font=(th.FUENTE, th.TAM_H3, "bold"),
            ).pack(anchor="w", padx=16, pady=(12, 0))
            ctk.CTkLabel(
                tarjeta,
                text="Empieza en Administración de XML 4.0: elige una carpeta, pulsa "
                "'Leer XMLs' y los comprobantes se cargarán al catálogo.",
                text_color=th.TEXTO_SECUNDARIO, font=(th.FUENTE, th.TAM_BODY),
                justify="left", wraplength=760,
            ).pack(anchor="w", padx=16, pady=(2, 0))
            BotonPrimario(
                tarjeta, "Administración de XML 4.0",
                comando=lambda: self.app.navegar("admin40"),
            ).pack(anchor="w", padx=16, pady=(12, 16))
        elif sin_validar:
            ctk.CTkLabel(
                tarjeta, text=f"Tienes {sin_validar} comprobantes sin validar ante el SAT",
                text_color=th.TEXTO, font=(th.FUENTE, th.TAM_H3, "bold"),
            ).pack(anchor="w", padx=16, pady=(12, 0))
            ctk.CTkLabel(
                tarjeta,
                text="La validación tarda unos segundos por comprobante y consulta el SAT "
                "directamente; no cierres la ventana mientras corre.",
                text_color=th.TEXTO_SECUNDARIO, font=(th.FUENTE, th.TAM_BODY),
                justify="left", wraplength=760,
            ).pack(anchor="w", padx=16, pady=(2, 0))
            BotonPrimario(
                tarjeta, "Validar estatus ahora",
                comando=lambda: self.app.navegar("admin40"),
            ).pack(anchor="w", padx=16, pady=(12, 16))
