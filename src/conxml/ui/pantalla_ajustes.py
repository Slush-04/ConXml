"""Pantalla de ajustes y configuración del sistema."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, filedialog
from pathlib import Path

import customtkinter as ctk

from conxml.catalog.db import Catalogo
from conxml.config import Config
from conxml import estado_local
from conxml.archivos import abrir_local
from conxml.respaldos import crear_respaldo, restaurar_respaldo
from conxml.ui import theme as th
from conxml.ui.widgets import (
    BotonPrimario, BotonSecundario, Encabezado, PanelCard, ResumenOperacion,
    BarraAdaptable, ajustar_ancho_disponible, texto_adaptable,
)


class PantallaAjustes(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.botones: list = []

        contenedor = ctk.CTkScrollableFrame(self, fg_color="transparent")
        contenedor.pack(fill="both", expand=True, padx=32, pady=24)
        self._contenedor = contenedor
        ajustar_ancho_disponible(contenedor, self)

        Encabezado(
            contenedor,
            "Configuración",
            "Administra el comportamiento de lectura, almacenamiento y mantenimiento de la base de datos.",
        ).pack(fill="x", pady=(0, 20))

        # Tarjeta 1: Opciones de lectura y mantenimiento
        card_opciones = PanelCard(contenedor)
        card_opciones.pack(fill="x", pady=(0, 16))

        content_op = ctk.CTkFrame(card_opciones, fg_color="transparent")
        content_op.pack(fill="both", expand=True, padx=20, pady=18)

        ctk.CTkLabel(
            content_op,
            text="Lectura y catálogo",
            text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        self.limpiar_al_leer = tk.BooleanVar(value=estado_local.cargar().get('limpiar_al_leer', False))
        self.chk_limpiar = ctk.CTkCheckBox(
            content_op,
            text="Limpiar catálogo de trabajo automáticamente al leer carpetas",
            variable=self.limpiar_al_leer,
            command=lambda: estado_local.guardar({'limpiar_al_leer': self.limpiar_al_leer.get()}),
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
            text="Desactivado: los XML se agregan al catálogo y se conservan los anteriores. "
                 "Actívalo únicamente si deseas sustituir los comprobantes almacenados al leer otro lote.",
            text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA),
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(0, 16))

        # Botón de mantenimiento
        frame_btn = ctk.CTkFrame(content_op, fg_color="transparent")
        frame_btn.pack(anchor="w")

        self.btn_vaciar = BotonSecundario(
            frame_btn, "Vaciar catálogo…", self._confirmar_limpieza
        )
        self.btn_vaciar.configure(text_color=th.ROJO, hover_color=th.ROJO_FONDO)
        self.btn_vaciar.pack(side="left")

        # Tarjeta 2: Estado de la base de datos
        card_info = PanelCard(contenedor)
        card_info.pack(fill="x", pady=(0, 16))

        content_info = ctk.CTkFrame(card_info, fg_color="transparent")
        content_info.pack(fill="both", expand=True, padx=20, pady=18)

        ctk.CTkLabel(
            content_info,
            text="Almacenamiento",
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

        card_respaldo = PanelCard(contenedor)
        card_respaldo.pack(fill='x', pady=(0, 16))
        contenido = ctk.CTkFrame(card_respaldo, fg_color='transparent')
        contenido.pack(fill='x', padx=20, pady=18)
        ctk.CTkLabel(contenido, text='Respaldos y sesión local', font=(th.FUENTE, th.TAM_BODY, 'bold')).pack(anchor='w')
        ctk.CTkLabel(contenido, text='Clientes, catálogo, XML, solicitudes SAT, preferencias y última sesión se conservan en este equipo.\nLos respaldos incluyen los XML importados desde carpetas externas que sigan disponibles.', wraplength=690, justify='left').pack(anchor='w', pady=8)
        self.respaldo_al_cerrar = tk.BooleanVar(value=estado_local.cargar().get('respaldo_al_cerrar', True))
        ctk.CTkCheckBox(contenido, text='Respaldar al cerrar · conservar los últimos 10', variable=self.respaldo_al_cerrar, command=lambda: estado_local.guardar({'respaldo_al_cerrar': self.respaldo_al_cerrar.get()})).pack(anchor='w', pady=8)
        acciones = BarraAdaptable(contenido)
        acciones.pack(fill='x', pady=(8, 0))
        for texto, comando in [('Crear respaldo…', self._crear_respaldo), ('Restaurar respaldo…', self._restaurar_respaldo), ('Abrir datos locales', lambda: abrir_local(Config().base))]:
            boton = BotonSecundario(acciones, texto, comando)
            acciones.agregar(boton)
            self.botones.append(boton)
        self.botones.append(self.btn_vaciar)

        card_descargas = PanelCard(contenedor)
        card_descargas.pack(fill="x", pady=(0, 16))
        contenido_sat = ctk.CTkFrame(card_descargas, fg_color="transparent")
        contenido_sat.pack(fill="x", padx=20, pady=18)
        ctk.CTkLabel(contenido_sat, text="Destino de descargas SAT", font=(th.FUENTE, th.TAM_BODY, "bold")).pack(anchor="w")
        self._modos_sat = {"Organizar XML e importar al visor": "organizado", "Conservar ZIP sin extraer": "zip"}
        self._modo_sat = tk.StringVar()
        self._carpeta_sat = tk.StringVar()
        self._destinos_sat: dict[str, str] = {}
        self._modo_sat_anterior = "organizado"
        self._combo_modo_sat = ctk.CTkComboBox(contenido_sat, variable=self._modo_sat, values=list(self._modos_sat), width=320, state="readonly", command=self._cambiar_modo_sat)
        self._combo_modo_sat.pack(anchor="w", pady=(12, 8))
        self._lbl_modo_sat = ctk.CTkLabel(contenido_sat, text="", wraplength=650, justify="left", anchor="w", text_color=th.TEXTO_SECUNDARIO)
        self._lbl_modo_sat.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(contenido_sat, text="Carpeta destino", text_color=th.TEXTO).pack(anchor="w")
        ctk.CTkEntry(contenido_sat, textvariable=self._carpeta_sat).pack(fill="x", pady=8)
        for texto, comando in (("Elegir carpeta…", self._elegir_carpeta_sat), ("Guardar destino y modo", self._guardar_destino_sat)):
            boton = BotonSecundario(contenido_sat, texto, comando)
            boton.pack(anchor="w", pady=(0, 8))
            self.botones.append(boton)
        self._estado_destino_sat = ctk.CTkLabel(contenido_sat, text="", wraplength=650, justify="left", anchor="w", text_color=th.TEXTO_SECUNDARIO)
        self._estado_destino_sat.pack(fill="x")
        self._cargar_destino_sat()
        for panel in (content_op, content_info, contenido, contenido_sat):
            for widget in panel.winfo_children():
                if isinstance(widget, ctk.CTkLabel):
                    texto_adaptable(widget, panel, margen=8)
        self.chk_limpiar.configure(text="Sustituir el catálogo al leer nuevas carpetas")

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
        self.actualizar_stats()
        self._cargar_destino_sat()

    def _cargar_destino_sat(self) -> None:
        config = Config()
        self._destinos_sat = {"organizado": str(config.carpeta_boveda), "zip": str(config.carpeta_zip_sat)}
        self._modo_sat_anterior = config.modo_descarga_sat
        self._modo_sat.set(next(nombre for nombre, modo in self._modos_sat.items() if modo == config.modo_descarga_sat))
        self._carpeta_sat.set(self._destinos_sat[config.modo_descarga_sat])
        self._describir_modo_sat()

    def _cambiar_modo_sat(self, _valor: str) -> None:
        self._destinos_sat[self._modo_sat_anterior] = self._carpeta_sat.get()
        modo = self._modos_sat[self._modo_sat.get()]
        self._carpeta_sat.set(self._destinos_sat[modo])
        self._modo_sat_anterior = modo
        self._describir_modo_sat()

    def _describir_modo_sat(self) -> None:
        organizado = self._modos_sat[self._modo_sat.get()] == "organizado"
        self._lbl_modo_sat.configure(text=(
            "Los XML se extraerán y guardarán en cliente / Emitidos o Recibidos / año / mes, "
            "según el CFDI, y se incorporarán al visor. Esta carpeta será la raíz de Bóveda."
            if organizado else
            "Los paquetes ZIP se conservarán sin extraer ni importar en cliente / solicitud. "
            "Podrás extraerlos y moverlos manualmente después. La raíz de Bóveda se conserva."
        ))

    def _elegir_carpeta_sat(self) -> None:
        carpeta = filedialog.askdirectory(parent=self, title="Destino de descargas SAT", mustexist=True)
        if carpeta:
            self._carpeta_sat.set(carpeta)

    def _guardar_destino_sat(self) -> None:
        modo = self._modos_sat[self._modo_sat.get()]
        destino = self._carpeta_sat.get().strip()
        if not destino or not Path(destino).expanduser().is_absolute():
            messagebox.showerror("Destino SAT", "Elige una carpeta o escribe su ruta completa.", parent=self)
            return
        try:
            carpeta = Path(destino).expanduser().resolve()
            carpeta.mkdir(parents=True, exist_ok=True)
            import tempfile
            with tempfile.TemporaryFile(dir=carpeta):
                pass
            opciones = dict(Config().opciones_descarga_sat)
            opciones.update({"modo": modo, "carpeta_xml" if modo == "organizado" else "carpeta_zip": str(carpeta)})
            estado_local.guardar({"descargas_sat": opciones})
        except (OSError, ValueError) as exc:
            messagebox.showerror("Destino SAT", f"No se pudo guardar el destino: {exc}", parent=self)
            return
        self._cargar_destino_sat()
        self._estado_destino_sat.configure(text="Guardado. Se aplica a próximas recuperaciones. Los archivos anteriores no se mueven; el historial SAT se conserva.")

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

    def _crear_respaldo(self):
        Config().respaldos.mkdir(parents=True, exist_ok=True)
        destino = filedialog.asksaveasfilename(parent=self, title='Guardar respaldo local', initialdir=Config().respaldos, initialfile='conxml_respaldo.zip', defaultextension='.zip', filetypes=[('Respaldo ConXml', '*.zip')])
        if destino:
            self.app.guardar_sesion()
            self.app.ejecutar(lambda: crear_respaldo(Config().base, Path(destino)), self._respaldo_creado, 'Creando respaldo local')

    def _respaldo_creado(self, resultado):
        self._detalles_usados = True
        self.app.mostrar_detalles(True)
        self.al_alternar_detalles(True)
        self.resumen.mostrar(f'Respaldo guardado: {resultado.archivos} archivos', tono='verde', detalle=str(resultado.ruta))
        self.app.registro(f'Respaldo local: {resultado.ruta}')
        if resultado.faltantes:
            messagebox.showwarning('Respaldo incompleto', f'{len(resultado.faltantes)} XML ya no están disponibles en su ruta original. El respaldo conserva el catálogo y registra los faltantes en manifest.json.', parent=self)

    def _restaurar_respaldo(self):
        archivo = filedialog.askopenfilename(parent=self, title='Elegir respaldo ConXml', filetypes=[('Respaldo ConXml', '*.zip')])
        if not archivo:
            return
        if not messagebox.askyesno('Restaurar respaldo', 'Se recuperarán los clientes, XML y sesión del respaldo. Los datos actuales se conservarán en una carpeta de recuperación junto a los datos locales. ¿Continuar?', parent=self):
            return
        self.app.guardar_sesion()
        self.app.ejecutar(lambda: restaurar_respaldo(Path(archivo), Config().base), self._restaurado, 'Validando y restaurando respaldo local')

    def _restaurado(self, previa):
        messagebox.showinfo('Respaldo restaurado', f'Datos locales recuperados.\nCopia de los datos anteriores: {previa}', parent=self)
        self.app.recargar_datos_locales()
