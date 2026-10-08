"""Pantalla para guardar y seleccionar XML desde la bóveda organizada."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from conxml.boveda import (
    instrucciones_boveda_ocultas,
    inicializar_boveda,
    ocultar_instrucciones_boveda,
    periodos_disponibles,
    seleccionar_xmls,
)
from conxml.catalog.db import Catalogo
from conxml.catalog.importer import importar_carpetas
from conxml.config import Config
from conxml.ui import theme as th
from conxml.ui.widgets import BotonPrimario, BotonSecundario, Encabezado, PanelCard, ResumenOperacion, BarraAdaptable, texto_adaptable


class PantallaBoveda(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._origen = tk.StringVar()
        self._direccion = tk.StringVar(value="Masivo")
        self._anio = tk.StringVar(value="Todos")
        self._mes = tk.StringVar(value="Todos")
        self._archivos_actuales: list[Path] = []
        self._origen_externo = False
        self._dialogo_instrucciones = None
        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.pack(fill="both", expand=True, padx=32, pady=24)
        contenedor.columnconfigure(0, weight=1)
        contenedor.rowconfigure(3, weight=1)
        self._contenedor = contenedor
        self._encabezado = Encabezado(contenedor, "Bóveda de XML", "Guarda los archivos organizados por cliente, recibidos o emitidos, año y mes.")
        self._encabezado.grid(row=0, column=0, sticky="ew")

        card = PanelCard(contenedor)
        card.grid(row=1, column=0, sticky="ew", pady=(20, 12))
        card.columnconfigure(0, weight=1)
        self._cliente_lbl = ctk.CTkLabel(card, text="Cliente activo: —", text_color=th.TEXTO,
                                        font=(th.FUENTE, th.TAM_BODY, "bold"), anchor="w")
        self._cliente_lbl.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))
        texto_adaptable(self._cliente_lbl, card)
        ctk.CTkLabel(card, text="Carpeta externa", text_color=th.TEXTO_SECUNDARIO).grid(
            row=1, column=0, sticky="w", padx=16)
        origen = ctk.CTkFrame(card, fg_color="transparent")
        origen.grid(row=2, column=0, sticky="ew", padx=16, pady=(4, 10))
        origen.columnconfigure(0, weight=1)
        self._entrada_origen = ctk.CTkEntry(origen, textvariable=self._origen,
                                          placeholder_text="Selecciona una carpeta con archivos XML", height=34)
        self._entrada_origen.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._entrada_origen.bind("<Return>", lambda _event: self._usar_carpeta_escrita())
        BotonSecundario(origen, "Examinar", self._elegir_origen).grid(row=0, column=1, padx=(0, 8))
        BotonSecundario(origen, "Leer carpeta", self._usar_carpeta_escrita).grid(row=0, column=2)
        filtros = BarraAdaptable(card)
        filtros.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 12))
        for nombre, variable, valores, comando, atributo, ancho in (
            ("Origen", self._direccion, ["Emitidos", "Recibidos", "Masivo"], self._cambiar_origen, "_combo_direccion", 150),
            ("Año", self._anio, ["Todos"], lambda _v: self._actualizar_lista(), "_combo_anio", 105),
            ("Mes", self._mes, ["Todos"], lambda _v: self._actualizar_lista(), "_combo_mes", 105),
        ):
            grupo = ctk.CTkFrame(filtros, fg_color="transparent")
            ctk.CTkLabel(grupo, text=nombre, text_color=th.TEXTO_SECUNDARIO).pack(side="left", padx=(0, 8))
            combo = ctk.CTkComboBox(grupo, variable=variable, values=valores, command=comando, width=ancho)
            combo.pack(side="left")
            setattr(self, atributo, combo)
            filtros.agregar(grupo)

        lista = PanelCard(contenedor)
        lista.grid(row=3, column=0, sticky="nsew")
        lista.rowconfigure(1, weight=1); lista.columnconfigure(0, weight=1)
        cabecera = ctk.CTkFrame(lista, fg_color="transparent")
        cabecera.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 8))
        self._estado = ctk.CTkLabel(cabecera, text="0 XML seleccionables", text_color=th.TEXTO_SECUNDARIO, font=(th.FUENTE, th.TAM_NOTA))
        self._estado.pack(side="left")
        BotonPrimario(cabecera, "Cargar selección", self._cargar_seleccion).pack(side="right")
        marco = ctk.CTkFrame(lista, fg_color="transparent")
        marco.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16)); marco.rowconfigure(0, weight=1); marco.columnconfigure(0, weight=1)
        self._tabla = ttk.Treeview(marco, columns=("direccion", "anio", "mes", "archivo"), show="headings")
        for clave, titulo, ancho in (("direccion", "Tipo", 100), ("anio", "Año", 70), ("mes", "Mes", 70), ("archivo", "Archivo XML", 280)):
            self._tabla.heading(clave, text=titulo); self._tabla.column(clave, width=ancho, anchor="w")
        self._tabla.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(marco, orient="vertical", command=self._tabla.yview); scroll.grid(row=0, column=1, sticky="ns"); self._tabla.configure(yscrollcommand=scroll.set)
        scroll_x = ttk.Scrollbar(marco, orient="horizontal", command=self._tabla.xview)
        scroll_x.grid(row=1, column=0, sticky="ew")
        self._tabla.configure(xscrollcommand=scroll_x.set)
        self._vacio = ctk.CTkLabel(marco, text="Elige una carpeta o un periodo para ver sus XML.",
                                  text_color=th.TEXTO_SECUNDARIO, fg_color=th.FONDO_TARJETA)
        self._vacio.place(relx=.5, rely=.5, anchor="center")
        self._resumen = ResumenOperacion(contenedor); self._resumen.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        self._detalles_usados = False; self.al_alternar_detalles(self.app.detalles_visibles)

    def aplicar_modo_compacto(self, ancho_compacto: bool, alto_compacto: bool) -> None:
        self._contenedor.pack_configure(padx=12 if (ancho_compacto or alto_compacto) else 32, pady=12 if (ancho_compacto or alto_compacto) else 24)

    def al_alternar_detalles(self, visible: bool) -> None:
        if visible and self._detalles_usados: self._resumen.grid()
        else: self._resumen.grid_remove()

    def al_mostrar(self) -> None:
        cliente = self.app.cliente_actual
        if not cliente:
            self.app.cambiar_cliente(); return
        inicializar_boveda(Config(), cliente)
        with Catalogo(self.app.db_path) as catalogo:
            detalle = catalogo.obtener_cliente(cliente)
        self._cliente_lbl.configure(text=f"Cliente activo: {detalle['nombre'] if detalle else cliente} ({cliente})")
        anios, meses = periodos_disponibles(Config(), cliente)
        self._combo_anio.configure(values=["Todos", *anios]); self._combo_mes.configure(values=["Todos", *meses])
        self._actualizar_estado_filtros()
        self._actualizar_lista()
        self._mostrar_instrucciones_si_corresponde()

    def _mostrar_instrucciones_si_corresponde(self) -> None:
        if instrucciones_boveda_ocultas(Config()) or self._dialogo_instrucciones is not None:
            return
        ventana = ctk.CTkToplevel(self.winfo_toplevel())
        self._dialogo_instrucciones = ventana
        ventana.title("Cómo usar la Bóveda")
        ventana.geometry("680x490")
        ventana.minsize(580, 430)
        ventana.transient(self.winfo_toplevel())
        ventana.configure(fg_color=th.FONDO)

        contenido = ctk.CTkFrame(ventana, fg_color="transparent")
        contenido.pack(fill="both", expand=True, padx=28, pady=24)
        ctk.CTkLabel(
            contenido, text="Cómo trabajar con la Bóveda", text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_H1, "bold"), anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            contenido,
            text="La Bóveda conserva tus XML ordenados y el visor solo carga el periodo que selecciones.",
            text_color=th.TEXTO_SECUNDARIO, font=(th.FUENTE, th.TAM_BODY),
            justify="left", wraplength=600, anchor="w",
        ).pack(anchor="w", pady=(4, 16))

        pasos = (
            "1. Pulsa Examinar y elige cualquier carpeta que contenga archivos XML.",
            "2. Para la Bóveda, selecciona Emitidos, Recibidos o Masivo; después elige año y mes.",
            "3. Revisa la lista de XML que corresponde a tu selección.",
            "4. Pulsa Cargar selección para llevar esos XML a Administración de XML.",
        )
        tarjeta = PanelCard(contenido)
        tarjeta.pack(fill="x", pady=(0, 16))
        for paso in pasos:
            ctk.CTkLabel(
                tarjeta, text=paso, text_color=th.TEXTO, font=(th.FUENTE, th.TAM_BODY),
                justify="left", wraplength=570, anchor="w",
            ).pack(anchor="w", padx=16, pady=(10, 0))
        ctk.CTkLabel(
            tarjeta,
            text="La carpeta Bóveda se crea automáticamente para cada cliente activo.",
            text_color=th.TEXTO_SECUNDARIO, font=(th.FUENTE, th.TAM_NOTA),
            justify="left", wraplength=570, anchor="w",
        ).pack(anchor="w", padx=16, pady=(10, 14))

        no_mostrar = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            contenido, text="No volver a mostrar estas instrucciones",
            variable=no_mostrar, fg_color=th.PRIMARIO, hover_color=th.PRIMARIO_HOVER,
            border_color=th.BORDE, text_color=th.TEXTO, font=(th.FUENTE, th.TAM_BODY),
        ).pack(anchor="w")
        acciones = ctk.CTkFrame(contenido, fg_color="transparent")
        acciones.pack(fill="x", pady=(18, 0))

        def cerrar() -> None:
            if no_mostrar.get():
                ocultar_instrucciones_boveda(Config())
            try:
                ventana.grab_release()
            except tk.TclError:
                pass
            self._dialogo_instrucciones = None
            ventana.destroy()

        BotonSecundario(acciones, "Cancelar", cerrar).pack(side="right", padx=(8, 0))
        BotonPrimario(acciones, "Aceptar", cerrar).pack(side="right")
        ventana.protocol("WM_DELETE_WINDOW", cerrar)
        ventana.after_idle(lambda: (ventana.deiconify(), ventana.grab_set(), ventana.focus_force()))

    def _elegir_origen(self) -> None:
        ruta = filedialog.askdirectory(parent=self, title="Seleccionar carpeta con XML")
        if ruta:
            self._origen.set(ruta)
            self._origen_externo = True
            self._actualizar_estado_filtros()
            self._actualizar_lista()

    def _usar_carpeta_escrita(self) -> None:
        carpeta = Path(self._origen.get().strip())
        if not carpeta.is_dir():
            messagebox.showinfo("Carpeta XML", "La ruta escrita no es una carpeta válida.", parent=self)
            return
        self._origen_externo = True
        self._actualizar_estado_filtros()
        self._actualizar_lista()

    def _cambiar_origen(self, _valor: str = "") -> None:
        """Muestra la Bóveda sin borrar la carpeta externa elegida."""
        if self._origen_externo:
            self._origen_externo = False
        self._actualizar_estado_filtros()
        self._actualizar_lista()

    def _actualizar_estado_filtros(self) -> None:
        # Los filtros de la Bóveda se conservan mientras se consulta una
        # carpeta externa. La carpeta externa se lee completa y por separado.
        self._combo_anio.configure(state="normal")
        self._combo_mes.configure(state="normal")

    def _actualizar_lista(self) -> None:
        if self._origen_externo and self._origen.get().strip():
            carpeta = Path(self._origen.get().strip())
            archivos = sorted(
                archivo for archivo in carpeta.rglob("*.xml")
                if archivo.is_file()
            ) if carpeta.is_dir() else []
        elif not self.app.cliente_actual:
            archivos = []
        else:
            archivos = seleccionar_xmls(
                Config(), self.app.cliente_actual, self._direccion.get(),
                self._anio.get(), self._mes.get(),
            )
        self._archivos_actuales = archivos
        if archivos:
            self._vacio.place_forget()
        else:
            self._vacio.place(relx=.5, rely=.5, anchor="center")
        for item in self._tabla.get_children(): self._tabla.delete(item)
        for archivo in archivos:
            self._tabla.insert("", "end", values=self._fila_archivo(archivo))
        origen = " en la carpeta seleccionada" if self._origen_externo else ""
        self._estado.configure(text=f"{len(archivos)} XML seleccionables{origen}")

    def _fila_archivo(self, archivo: Path) -> tuple[str, str, str, str]:
        if self._origen_externo:
            return ("Carpeta", "—", "—", archivo.name)
        partes = archivo.parts
        if "Masivo" in partes:
            indice = partes.index("Masivo")
            direccion = partes[indice - 1] if indice else "Masivo"
            return (direccion, "Pendiente", "Masivo", archivo.name)
        if len(partes) >= 2 and partes[-2].isdigit() and len(partes[-2]) == 4:
            direccion = next((p for p in reversed(partes[:-2]) if p in ("Emitidos", "Recibidos")), "—")
            return (direccion, partes[-2], "—", archivo.name)
        if len(partes) >= 3 and partes[-3].isdigit() and len(partes[-3]) == 4:
            direccion = next((p for p in reversed(partes[:-3]) if p in ("Emitidos", "Recibidos")), "—")
            return (direccion, partes[-3], partes[-2], archivo.name)
        return ("—", "—", "—", archivo.name)

    def _cargar_seleccion(self) -> None:
        if not self.app.cliente_actual:
            self.app.cambiar_cliente()
            return
        archivos = self._archivos_actuales
        if not archivos:
            messagebox.showinfo("Bóveda", "No hay XML para la selección actual.", parent=self); return
        ajustes = self.app._pantallas.get("ajustes")
        limpiar = ajustes.limpiar_al_leer.get() if ajustes else True
        self._detalles_usados = True; self.app.mostrar_detalles(True); self._resumen.mostrar("Cargando selección en el catálogo…")
        self.app.ejecutar(lambda: self._run_carga(archivos, limpiar), self._presentar_carga, "Cargando XML seleccionados")

    def _run_carga(self, archivos: list[Path], limpiar: bool):
        with Catalogo(self.app.db_path) as catalogo:
            return importar_carpetas(catalogo, archivos, self.app.cliente_actual, limpiar_antes=limpiar)

    def _presentar_carga(self, resultado) -> None:
        self._resumen.mostrar("Selección cargada", detalle=f"Procesados: {resultado.procesados} | Insertados: {resultado.insertados} | Errores: {resultado.errores}")
        self.app.actualizar_resumen()
        admin = self.app._pantallas.get("admin40")
        if admin: admin._cargar_tabla()
