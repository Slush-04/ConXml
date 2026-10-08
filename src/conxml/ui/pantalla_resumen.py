"""Pantalla de resumen: métricas del catálogo y acceso rápido al flujo."""

from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from conxml.catalog.db import Catalogo
from conxml.ui import theme as th
from conxml.ui.widgets import (
    BotonPrimario,
    Card,
    Encabezado,
    Insignia,
    Metrica,
    TarjetaAccion,
    ajustar_ancho_disponible,
    texto_adaptable,
)

ACCIONES = [
    ("boveda", "Bóveda de XML",
     "Guarda XML en carpetas ordenadas por tipo, año y mes, y carga solo la selección que necesitas."),
    ("admin40", "Administración de XML 4.0",
     "Consulta los XML cargados, previsualiza su información, valida estatus SAT "
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

        self._contenedor = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._contenedor.pack(fill="both", expand=True, padx=32, pady=24)
        ajustar_ancho_disponible(self._contenedor, self)
        self._contenedor.columnconfigure(0, weight=1)

        self._encabezado = Encabezado(
            self._contenedor,
            "Resumen del catálogo",
            "Importa los XML de tus clientes, valida su estatus ante el SAT y genera los reportes Excel.",
        )
        self._encabezado.pack(anchor="w", fill="x")

        ctk.CTkLabel(
            self._contenedor, text="Tu catálogo, de un vistazo",
            text_color=th.TEXTO_SECUNDARIO, font=(th.FUENTE, th.TAM_NOTA, "bold"),
        ).pack(anchor="w", pady=(20, 8))

        self._metricas = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        self._metricas.pack(fill="x")

        ctk.CTkLabel(
            self._contenedor, text="Accesos rápidos",
            text_color=th.TEXTO_SECUNDARIO, font=(th.FUENTE, th.TAM_NOTA, "bold"),
        ).pack(anchor="w", pady=(24, 8))

        self._acciones = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        self._acciones.pack(fill="x")

        self._tarjetas_accion = []
        for i, (clave, titulo, descripcion) in enumerate(ACCIONES):
            tarjeta = TarjetaAccion(self._acciones, titulo=titulo, descripcion=descripcion,
                                   numero=f"0{i + 1}", comando=lambda c=clave: self.app.navegar(c))
            self._tarjetas_accion.append(tarjeta)
        tk.Misc.bind(self._acciones, "<Configure>", self._distribuir_acciones, add="+")

        self._estado = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        self._estado.pack(fill="x", pady=(20, 0))

    def aplicar_modo_compacto(self, ancho_compacto: bool, alto_compacto: bool) -> None:
        """Márgenes compactos en laptop sin recrear widgets."""
        try:
            if ancho_compacto or alto_compacto:
                self._contenedor.pack_configure(padx=12, pady=12)
            else:
                self._contenedor.pack_configure(padx=32, pady=24)
        except Exception:
            pass

    def al_mostrar(self) -> None:
        if self.app.cliente_actual:
            with Catalogo(self.app.db_path) as catalogo:
                cliente = catalogo.obtener_cliente(self.app.cliente_actual)
            if cliente:
                self._encabezado._lbl_sub.configure(
                    text=f"Cliente activo: {cliente['nombre']} ({cliente['clave']}). "
                    "Administra sus XML, valida SAT y genera reportes."
                )
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

        self._tarjetas_metrica = []
        for etiqueta, valor, tono in (("Comprobantes", total, "azul"),
                                     ("Vigentes", est["Vigente"], "verde"),
                                     ("Cancelados", est["Cancelado"], "rojo"),
                                     ("Sin validar", est["Sin validar"], "ambar")):
            self._tarjetas_metrica.append(Metrica(fila, etiqueta, str(valor), tono=tono))
        columnas_previas = None
        def distribuir(event):
            nonlocal columnas_previas
            if event.widget is fila:
                from conxml.ui.responsive import escalado_widget
                columnas = 4 if event.width / escalado_widget(fila) >= 680 else 2
                if columnas == columnas_previas:
                    return
                columnas_previas = columnas
                for col in range(4):
                    fila.columnconfigure(col, weight=1 if col < columnas else 0, uniform="metricas" if col < columnas else "")
                for i, tarjeta in enumerate(self._tarjetas_metrica):
                    tarjeta.grid(row=i // columnas, column=i % columnas, sticky="nsew",
                                 padx=(0, 10 if i % columnas < columnas - 1 else 0), pady=(0, 10))
        tk.Misc.bind(fila, "<Configure>", distribuir, add="+")
        etiquetas = ctk.CTkFrame(self._metricas, fg_color="transparent")
        etiquetas.pack(fill="x")
        Insignia(etiquetas, f"Clientes: {datos['clientes']}", tono="gris").pack(side="left", padx=(0, 8))
        Insignia(etiquetas, f"No encontrados: {est['No Encontrado']}", tono="gris").pack(side="left", padx=(0, 8))
        if datos["errores"]:
            Insignia(etiquetas, f"Archivos con error: {datos['errores']}", tono="rojo").pack(side="left")

        self._presentar_estado(total, est["Sin validar"])

    def _presentar_estado(self, total: int, sin_validar: int) -> None:
        if total and not sin_validar:
            self._estado.pack_forget()
            return
        self._estado.pack(fill="x", pady=(16, 0))
        tarjeta = Card(self._estado)
        tarjeta.pack(fill="x")
        if total == 0:
            ctk.CTkLabel(
                tarjeta, text="Todavía no hay comprobantes en el catálogo",
                text_color=th.TEXTO, font=(th.FUENTE, th.TAM_H3, "bold"),
            ).pack(anchor="w", padx=16, pady=(12, 0))
            ctk.CTkLabel(
                tarjeta,
                text="Abre la Bóveda, elige una carpeta o un periodo y pulsa Cargar selección para empezar.",
                text_color=th.TEXTO_SECUNDARIO, font=(th.FUENTE, th.TAM_BODY),
                justify="left", wraplength=760,
            ).pack(anchor="w", padx=16, pady=(2, 0))
            BotonPrimario(
                tarjeta, "Abrir Bóveda",
                comando=lambda: self.app.navegar("boveda"),
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

        for widget in tarjeta.winfo_children():
            if isinstance(widget, ctk.CTkLabel):
                texto_adaptable(widget, tarjeta)

    def _distribuir_acciones(self, event):
        if event.widget is not self._acciones:
            return
        from conxml.ui.responsive import escalado_widget
        columnas = 3 if event.width / escalado_widget(self._acciones) >= 850 else 1
        if getattr(self, "_columnas_accion", None) == columnas:
            return
        self._columnas_accion = columnas
        for col in range(3):
            self._acciones.columnconfigure(col, weight=1 if col < columnas else 0,
                                            uniform="acciones" if col < columnas else "")
        for i, tarjeta in enumerate(self._tarjetas_accion):
            tarjeta.grid(row=i // columnas, column=i % columnas, sticky="nsew",
                         padx=(0, 12 if i % columnas < columnas - 1 else 0), pady=(0, 10))
