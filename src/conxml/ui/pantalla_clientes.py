"""Selección y mantenimiento del cliente activo."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from conxml.catalog.db import Catalogo
from conxml.config import Config
from conxml.ui.tabla_visor import TablaVisor
from conxml.ui import theme as th
from conxml.ui import responsive as resp
from conxml.ui.widgets import (
    BotonPrimario, BotonSecundario, Encabezado, PanelCard, texto_adaptable,
)


class PantallaClientes(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, app=None, on_selected=None, db_path=None) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._on_selected = on_selected
        self._db_path = db_path or (app.db_path if app is not None else Config().db_path)
        self._editando: str | None = None
        self._clientes: list[dict] = []
        self._busqueda = tk.StringVar()
        self._formulario_visible = False
        self._cantidad_visible = 0
        self._ajuste_pendiente = None
        self._distribucion = None
        self._contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self._contenedor.pack(fill="both", expand=True, padx=24, pady=20)
        self._contenedor.columnconfigure(0, weight=1)

        self._encabezado = Encabezado(
            self._contenedor, "Selecciona un cliente",
            "Busca tu cliente y entra a su bóveda de XML.",
        )
        self._encabezado.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        self._paneles = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        self._paneles.grid(row=1, column=0, sticky="ew")
        self._paneles.columnconfigure(0, weight=1)

        self._card_lista = PanelCard(self._paneles)
        self._card_lista.grid(row=0, column=0, sticky="new")
        self._card_lista.columnconfigure(0, weight=1)
        cabecera = ctk.CTkFrame(self._card_lista, fg_color="transparent")
        cabecera.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 12))
        cabecera.columnconfigure(0, weight=1)
        ctk.CTkLabel(
            cabecera, text="Clientes registrados", text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_H3, "bold"), anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self._lbl_conteo = ctk.CTkLabel(
            cabecera, text="0 clientes", text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA),
        )
        self._lbl_conteo.grid(row=0, column=1, sticky="e", padx=(8, 0))
        self._entrada_busqueda = ctk.CTkEntry(
            cabecera, placeholder_text="Buscar por clave, nombre o RFC", height=34,
        )
        self._entrada_busqueda.grid(row=1, column=0, sticky="ew", pady=(10, 0), padx=(0, 10))
        self._entrada_busqueda.bind("<KeyRelease>", self._buscar)
        self._entrada_busqueda.bind("<Return>", lambda _e: self._entrar())
        for evento in ("<<Paste>>", "<<Cut>>"):
            self._entrada_busqueda.bind(evento, lambda _e: self.after_idle(self._buscar), add="+")
        self._busqueda.trace_add("write", self._sincronizar_busqueda)
        self._btn_nuevo = BotonSecundario(cabecera, "+ Nuevo cliente", self._nuevo)
        self._btn_nuevo.grid(row=1, column=1, pady=(10, 0), sticky="e")

        self._marco_tabla = ctk.CTkFrame(self._card_lista, fg_color="transparent", height=162)
        self._marco_tabla.grid(row=1, column=0, sticky="ew", padx=16)
        self._marco_tabla.grid_propagate(False)
        self._marco_tabla.rowconfigure(0, weight=1)
        self._marco_tabla.columnconfigure(0, weight=1)
        self._tabla = TablaVisor(
            self._marco_tabla, columns=("clave", "nombre", "rfc"), paginacion_automatica=True,
        )
        for clave, titulo in (("clave", "Clave"), ("nombre", "Nombre"), ("rfc", "RFC")):
            self._tabla.heading(clave, text=titulo)
        self._tabla.sheet.set_options(
            default_row_height=32, default_header_height=34,
            empty_horizontal=0, empty_vertical=0,
        )
        self._tabla.sheet.disable_bindings("column_width_resize")
        self._tabla.grid(row=0, column=0, sticky="nsew")
        self._tabla.bind("<Double-1>", lambda _event: self._entrar())
        self._tabla.sheet.MT.bind("<Return>", lambda _event: self._entrar(), add="+")
        self._tabla.sheet.bind("<<SheetSelect>>", self._actualizar_seleccion, add="+")
        self._tabla.sheet.bind("<<SheetRedrawn>>", self._actualizar_seleccion, add="+")
        self._tabla.bind("<Configure>", self._programar_ajuste, add="+")
        tk.Misc.bind(self._tabla.sheet.MT, "<Configure>", self._programar_ajuste, add="+")
        self._vacio = ctk.CTkLabel(
            self._marco_tabla, text="Aún no hay clientes. Crea el primero con «Nuevo cliente».",
            text_color=th.TEXTO_SECUNDARIO, fg_color=th.FONDO_TARJETA,
            font=(th.FUENTE, th.TAM_BODY), wraplength=350, justify="center",
        )

        pie = ctk.CTkFrame(self._card_lista, fg_color=th.FONDO_ENTRADA, corner_radius=8)
        pie.grid(row=2, column=0, sticky="ew", padx=16, pady=(12, 16))
        pie.columnconfigure(0, weight=1)
        self._lbl_seleccion = ctk.CTkLabel(
            pie, text="Selecciona un cliente de la lista", text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA), anchor="w", justify="left", wraplength=400,
        )
        self._lbl_seleccion.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        acciones = ctk.CTkFrame(pie, fg_color="transparent")
        acciones.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        acciones.columnconfigure(0, weight=1)
        self._btn_editar = BotonSecundario(acciones, "Editar cliente", self._editar, state="disabled")
        self._btn_editar.grid(row=0, column=0, sticky="w")
        self._btn_entrar = BotonPrimario(acciones, "Entrar al cliente", self._entrar, state="disabled")
        self._btn_entrar.grid(row=0, column=1, sticky="e", padx=(8, 0))
        texto_adaptable(self._lbl_seleccion, pie, margen=32)

        self._formulario = PanelCard(self._paneles, width=288)
        self._formulario.columnconfigure(0, weight=1)
        self._titulo_formulario = ctk.CTkLabel(
            self._formulario, text="Nuevo cliente", text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_H3, "bold"), anchor="w", height=24,
        )
        self._titulo_formulario.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        ctk.CTkLabel(
            self._formulario, text="Organiza sus comprobantes en una bóveda propia.",
            font=(th.FUENTE, th.TAM_NOTA), text_color=th.TEXTO_SECUNDARIO,
            wraplength=260, justify="left", anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        for fila, atributo, titulo, ayuda in (
            (2, "_clave", "Clave", "Ej. CLIENTE-01"),
            (4, "_nombre", "Nombre", "Nombre del cliente"),
            (6, "_rfc", "RFC · opcional", "Ej. AAA010101AAA"),
        ):
            ctk.CTkLabel(
                self._formulario, text=titulo, text_color=th.TEXTO,
                font=(th.FUENTE, th.TAM_NOTA), anchor="w", height=18,
            ).grid(row=fila, column=0, sticky="ew", padx=16, pady=(0, 3))
            entrada = ctk.CTkEntry(self._formulario, placeholder_text=ayuda, height=32, width=256)
            entrada.grid(row=fila + 1, column=0, sticky="ew", padx=16, pady=(0, 10))
            entrada.bind("<Return>", lambda _event: self._guardar())
            setattr(self, atributo, entrada)
        self._btn_guardar = BotonPrimario(self._formulario, "Guardar cliente", self._guardar)
        self._btn_guardar.grid(row=8, column=0, sticky="ew", padx=16, pady=(4, 8))
        BotonSecundario(self._formulario, "Volver a la lista", self._cerrar_formulario).grid(
            row=9, column=0, sticky="ew", padx=16, pady=(0, 16),
        )
        tk.Misc.bind(self, "<Configure>", self._programar_ajuste, add="+")

    def _programar_ajuste(self, _event=None) -> None:
        if self._ajuste_pendiente is None:
            self._ajuste_pendiente = self.after_idle(self._ajustar_distribucion)

    def _ajustar_distribucion(self) -> None:
        self._ajuste_pendiente = None
        escala = resp.escalado_widget(self)
        ancho = self._paneles.winfo_width() / escala
        lateral = ancho >= 820
        distribucion = (self._formulario_visible, lateral)
        if distribucion != self._distribucion:
            self._distribucion = distribucion
            if self._formulario_visible:
                if lateral:
                    self._card_lista.grid()
                    self._formulario.grid(row=0, column=1, sticky="new", padx=(16, 0))
                else:
                    self._card_lista.grid_remove()
                    self._formulario.grid(row=0, column=0, sticky="new")
            else:
                self._formulario.grid_remove()
                self._card_lista.grid()
        # Una lista corta conserva una altura compacta; una larga utiliza el
        # espacio disponible sin obligar a llenar la ventana con filas vacías.
        paginacion = 40 if self._cantidad_visible > self._tabla.TAM_PAGINA else 0
        objetivo = 34 + min(12, max(4, self._cantidad_visible)) * 32 + paginacion
        disponible = max(162, int(self.winfo_height() / escala) - 246)
        alto = min(objetivo, disponible)
        if self._marco_tabla.cget("height") != alto:
            self._marco_tabla.configure(height=alto)
        ancho_tabla = self._tabla.sheet.MT.winfo_width()
        if ancho_tabla > 100:
            clave = min(190, max(100, int(ancho_tabla * .22)))
            rfc = min(210, max(140, int(ancho_tabla * .25)))
            anchos = (clave, max(100, ancho_tabla - clave - rfc - 6), rfc)
            self._tabla.ajustar_anchos(dict(zip(("clave", "nombre", "rfc"), anchos)))
        self._vacio.configure(wraplength=max(180, int(self._marco_tabla.winfo_width() / escala) - 32))

    def aplicar_modo_compacto(self, ancho_compacto: bool, alto_compacto: bool) -> None:
        compacto = ancho_compacto or alto_compacto
        self._contenedor.pack_configure(padx=12 if compacto else 24, pady=12 if compacto else 20)
        self._programar_ajuste()

    def al_mostrar(self) -> None:
        self._cargar()

    def _cargar(self) -> None:
        with Catalogo(self._db_path) as catalogo:
            self._clientes = [dict(cliente) for cliente in catalogo.clientes_detalle()]
        self._renderizar_tabla()
        if not self._clientes:
            self._nuevo()

    def _buscar(self, _event=None) -> None:
        self._busqueda.set(self._entrada_busqueda.get())

    def _sincronizar_busqueda(self, *_args) -> None:
        valor = self._busqueda.get()
        if self._entrada_busqueda.get() != valor:
            self._entrada_busqueda.delete(0, "end")
            if valor:
                self._entrada_busqueda.insert(0, valor)
        self._renderizar_tabla()

    def _renderizar_tabla(self) -> None:
        """Filtra la lista localmente para responder al escribir sin recargar SQLite."""
        if not hasattr(self, "_tabla"):
            return
        seleccion = self._seleccion()
        termino = self._busqueda.get().strip().casefold()
        visibles = [
            cliente for cliente in self._clientes
            if not termino or termino in " ".join(
                str(cliente.get(campo, "") or "") for campo in ("clave", "nombre", "rfc")
            ).casefold()
        ]
        self._tabla.selection_remove()
        self._tabla.delete(*self._tabla.get_children())
        for cliente in visibles:
            self._tabla.insert(
                "", "end", iid=cliente["clave"],
                values=(cliente["clave"], cliente["nombre"], cliente["rfc"] or ""),
            )
        if visibles:
            self._vacio.place_forget()
        else:
            self._vacio.configure(
                text="No hay clientes que coincidan con la búsqueda." if termino
                else "Aún no hay clientes. Crea el primero con «Nuevo cliente».",
            )
            self._vacio.place(relx=.5, rely=.5, anchor="center")
        self._cantidad_visible = len(visibles)
        self._lbl_conteo.configure(
            text=f"{len(visibles)} de {len(self._clientes)} clientes"
            if termino else f"{len(self._clientes)} clientes"
        )
        if seleccion in self._tabla.get_children():
            self._tabla.selection_set(seleccion)
        self._actualizar_seleccion()
        self._programar_ajuste()

    def _seleccion(self):
        seleccion = self._tabla.selection()
        return seleccion[0] if seleccion else None

    def _actualizar_seleccion(self, _event=None) -> None:
        clave = self._seleccion()
        cliente = next((c for c in self._clientes if c["clave"] == clave), None)
        texto = "Selecciona un cliente de la lista"
        if cliente:
            texto = cliente["nombre"]
            if cliente["rfc"]:
                texto += f" · {cliente['rfc']}"
        if self._lbl_seleccion.cget("text") != texto:
            self._lbl_seleccion.configure(text=texto, text_color=th.TEXTO if cliente else th.TEXTO_SECUNDARIO)
        for boton in (self._btn_entrar, self._btn_editar):
            estado = "normal" if cliente else "disabled"
            if boton.cget("state") != estado:
                boton.configure(state=estado)

    def _limpiar_formulario(self) -> None:
        self._editando = None
        self._clave.configure(state="normal")
        for entrada in (self._clave, self._nombre, self._rfc):
            entrada.delete(0, "end")
        self._titulo_formulario.configure(text="Nuevo cliente")
        self._btn_guardar.configure(text="Guardar cliente")

    def _nuevo(self) -> None:
        self._limpiar_formulario()
        self._formulario_visible = True
        self._ajustar_distribucion()
        self._clave.focus_set()

    def _cerrar_formulario(self) -> None:
        self._formulario_visible = False
        self._ajustar_distribucion()
        self._entrada_busqueda.focus_set()

    def _editar(self) -> None:
        clave = self._seleccion()
        if not clave:
            messagebox.showinfo("Cliente", "Selecciona un cliente para editarlo.", parent=self)
            return
        with Catalogo(self._db_path) as catalogo:
            cliente = catalogo.obtener_cliente(clave)
        if cliente is None:
            return
        self._limpiar_formulario()
        self._editando = clave
        self._clave.insert(0, clave)
        self._clave.configure(state="disabled")
        self._nombre.insert(0, cliente["nombre"])
        self._rfc.insert(0, cliente["rfc"] or "")
        self._titulo_formulario.configure(text="Editar cliente")
        self._btn_guardar.configure(text="Actualizar cliente")
        self._formulario_visible = True
        self._ajustar_distribucion()
        self._nombre.focus_set()

    def _guardar(self) -> None:
        clave = self._editando or self._clave.get().strip()
        nombre, rfc = self._nombre.get().strip(), self._rfc.get().strip()
        try:
            with Catalogo(self._db_path) as catalogo:
                if self._editando:
                    catalogo.actualizar_cliente(clave, nombre, rfc)
                else:
                    catalogo.crear_cliente(clave, nombre, rfc)
        except ValueError as exc:
            messagebox.showerror("Cliente", str(exc), parent=self)
            return
        self._limpiar_formulario()
        self._cerrar_formulario()
        self._busqueda.set("")
        self._cargar()
        self._tabla.selection_set(clave)
        self._actualizar_seleccion()

    def _entrar(self) -> None:
        clave = self._seleccion()
        if not clave:
            messagebox.showinfo("Cliente", "Selecciona un cliente para entrar.", parent=self)
            return
        if self._on_selected is not None:
            self._on_selected(clave)
        elif self.app is not None:
            self.app.seleccionar_cliente(clave)

    def destroy(self) -> None:
        if self._ajuste_pendiente is not None:
            self.after_cancel(self._ajuste_pendiente)
            self._ajuste_pendiente = None
        super().destroy()
