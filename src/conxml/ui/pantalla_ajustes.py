"""Pantalla de ajustes y configuración del sistema."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from conxml.catalog.db import Catalogo
from conxml.config import Config
from conxml.sat.estatus import ConfigLote
from conxml.ui import theme as th
from conxml.ui.widgets import BotonPrimario, BotonSecundario, Encabezado, PanelCard, ResumenOperacion


class PantallaAjustes(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.botones: list = []

        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.pack(fill="both", expand=True, padx=32, pady=24)

        Encabezado(
            contenedor,
            "Configuración y Ajustes",
            "Administra el comportamiento de lectura, almacenamiento y mantenimiento de la base de datos.",
        ).pack(fill="x", pady=(0, 20))

        # Tarjeta 1: Opciones de lectura y mantenimiento
        card_opciones = PanelCard(contenedor)
        card_opciones.pack(fill="x", pady=(0, 16))

        content_op = ctk.CTkFrame(card_opciones, fg_color="transparent")
        content_op.pack(fill="both", expand=True, padx=20, pady=18)

        ctk.CTkLabel(
            content_op,
            text="PREFERENCIAS DE LECTURA Y CATÁLOGO",
            text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        self.limpiar_al_leer = tk.BooleanVar(value=True)
        self.chk_limpiar = ctk.CTkCheckBox(
            content_op,
            text="Limpiar catálogo de trabajo automáticamente al leer carpetas",
            variable=self.limpiar_al_leer,
            fg_color=th.PRIMARIO,
            hover_color=th.PRIMARIO_HOVER,
            border_color=th.BORDE,
            text_color=th.TEXTO,
            corner_radius=4,
            font=(th.FUENTE, th.TAM_BODY),
        )
        self.chk_limpiar.pack(anchor="w", pady=(0, 16))

        ctk.CTkLabel(
            content_op,
            text="Si está activado, cada vez que selecciones y leas una carpeta se eliminarán "
                 "los registros de pruebas anteriores para trabajar con un lote limpio.",
            text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA),
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(0, 16))

        # Botón de mantenimiento
        frame_btn = ctk.CTkFrame(content_op, fg_color="transparent")
        frame_btn.pack(anchor="w")

        self.btn_vaciar = BotonSecundario(
            frame_btn, "🗑️ Vaciar todo el catálogo ahora", self._confirmar_limpieza
        )
        self.btn_vaciar.pack(side="left")

        # Tarjeta 2: Velocidad de validación SAT
        card_sat = PanelCard(contenedor)
        card_sat.pack(fill="x", pady=(0, 16))

        content_sat = ctk.CTkFrame(card_sat, fg_color="transparent")
        content_sat.pack(fill="both", expand=True, padx=20, pady=18)

        ctk.CTkLabel(
            content_sat,
            text="VELOCIDAD DE VALIDACIÓN ANTE EL SAT",
            text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        self.velocidad_sat = tk.StringVar(value="Rápida (8 hilos)")
        self.seg_velocidad = ctk.CTkSegmentedButton(
            content_sat,
            values=["Rápida (8 hilos)", "Moderada (4 hilos)", "Conservadora (1 hilo)"],
            variable=self.velocidad_sat,
            fg_color=th.FONDO_ENTRADA,
            selected_color=th.PRIMARIO,
            selected_hover_color=th.PRIMARIO_HOVER,
            unselected_color=th.FONDO_TARJETA,
            unselected_hover_color=th.PRIMARIO_FONDO,
            text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_BODY, "bold"),
            height=32,
        )
        self.seg_velocidad.pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(
            content_sat,
            text="• Rápida (Recomendado): ejecuta 8 consultas simultáneas con reutilización de conexiones (máxima velocidad).\n"
                 "• Moderada: ejecuta 4 consultas simultáneas en paralelo.\n"
                 "• Conservadora: consulta 1 comprobante a la vez con pausa de 2 segundos.",
            text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA),
            wraplength=700,
            justify="left",
        ).pack(anchor="w")

        # Tarjeta 3: Estado de la base de datos
        card_info = PanelCard(contenedor)
        card_info.pack(fill="x", pady=(0, 16))

        content_info = ctk.CTkFrame(card_info, fg_color="transparent")
        content_info.pack(fill="both", expand=True, padx=20, pady=18)

        ctk.CTkLabel(
            content_info,
            text="INFORMACIÓN DEL ALMACENAMIENTO",
            text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        self.lbl_db_path = ctk.CTkLabel(
            content_info,
            text=f"Ruta de base de datos: {Config().db_path}",
            text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_BODY),
            anchor="w",
        )
        self.lbl_db_path.pack(anchor="w", pady=(0, 6))

        self.lbl_stats = ctk.CTkLabel(
            content_info,
            text="Cargando estadísticas…",
            text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA),
            anchor="w",
        )
        self.lbl_stats.pack(anchor="w")

        # Notificador de estado (sin espacio reservado hasta el primer uso)
        self.resumen = ResumenOperacion(contenedor)
        self.resumen.pack(fill="x", pady=(16, 0))
        self._detalles_usados = False
        self.al_alternar_detalles(self.app.detalles_visibles)

    def al_alternar_detalles(self, visible: bool) -> None:
        if visible and self._detalles_usados:
            self.resumen.pack(fill="x", pady=(16, 0))
        else:
            self.resumen.pack_forget()

    def al_mostrar(self) -> None:
        self.actualizar_stats()

    def actualizar_stats(self) -> None:
        try:
            with Catalogo(self.app.db_path) as cat:
                t_comp = cat.contar("comprobantes")
                t_pagos = cat.contar("pagos")
                t_err = cat.contar("errores")
                self.lbl_stats.configure(
                    text=f"Registros guardados: {t_comp} comprobantes | {t_pagos} pagos | {t_err} errores de lectura."
                )
        except Exception as exc:
            self.lbl_stats.configure(text=f"No se pudo consultar estadísticas: {exc}")

    def _confirmar_limpieza(self) -> None:
        si = messagebox.askyesno(
            "Vaciar catálogo",
            "¿Estás seguro de vaciar todo el catálogo de la base de datos?\n"
            "Se eliminarán todos los comprobantes, pagos y errores almacenados.",
            parent=self,
        )
        if not si:
            return

        try:
            with Catalogo(self.app.db_path) as cat:
                cat.limpiar()
            self.actualizar_stats()
            self.app.actualizar_resumen()
            self._detalles_usados = True
            self.app.mostrar_detalles(True)
            self.al_alternar_detalles(True)
            self.resumen.mostrar("Catálogo vaciado con éxito", tono="verde")
            self.app.registro("Catálogo vaciado manualmente desde Ajustes.")
        except Exception as exc:
            self.resumen.mostrar(f"Error al vaciar catálogo: {exc}", tono="rojo")

    def obtener_config_sat(self) -> ConfigLote:
        """Devuelve la configuración de lote SAT según la selección de velocidad."""
        val = self.velocidad_sat.get()
        if "Moderada" in val:
            return ConfigLote(max_workers=4, delay_segundos=0.0)
        elif "Conservadora" in val:
            return ConfigLote(max_workers=1, delay_segundos=2.0)
        return ConfigLote(max_workers=8, delay_segundos=0.0)

