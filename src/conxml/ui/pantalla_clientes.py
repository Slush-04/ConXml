"""Selección y mantenimiento del cliente activo."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

from conxml.catalog.db import Catalogo
from conxml.config import Config
from conxml.ui import theme as th
from conxml.ui.widgets import BotonPrimario, BotonSecundario, Encabezado, PanelCard, BarraAdaptable


class PantallaClientes(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, app=None, on_selected=None, db_path=None) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._on_selected = on_selected
        self._db_path = db_path or (app.db_path if app is not None else Config().db_path)
        self._editando: str | None = None
        self._clientes: list[dict] = []
        self._busqueda = tk.StringVar()
        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.pack(fill="both", expand=True, padx=16, pady=16)
        contenedor.columnconfigure(0, weight=1)
        contenedor.rowconfigure(2, weight=1)
        self._contenedor = contenedor

        Encabezado(
            contenedor,
            "Selecciona un cliente",
            "Elige el cliente con el que vas a trabajar o registra uno nuevo para organizar su bóveda de XML.",
        ).grid(row=0, column=0, sticky="ew")

        card = PanelCard(contenedor)
        card.grid(row=1, column=0, sticky="ew", pady=(20, 12))
        card.columnconfigure(1, weight=1)
        ctk.CTkLabel(card, text="Datos del cliente", font=(th.FUENTE, th.TAM_H3, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(card, text="Clave", text_color=th.TEXTO, font=(th.FUENTE, th.TAM_BODY)).grid(
            row=1, column=0, padx=(16, 10), pady=10, sticky="w"
        )
        self._clave = ctk.CTkEntry(card, placeholder_text="Ej. CLIENTE-01")
        self._clave.grid(row=1, column=1, padx=8, pady=10, sticky="ew")
        ctk.CTkLabel(card, text="Nombre", text_color=th.TEXTO, font=(th.FUENTE, th.TAM_BODY)).grid(
            row=2, column=0, padx=(16, 10), pady=10, sticky="w"
        )
        self._nombre = ctk.CTkEntry(card, placeholder_text="Nombre visible del cliente")
        self._nombre.grid(row=2, column=1, padx=8, pady=10, sticky="ew")
        ctk.CTkLabel(card, text="RFC", text_color=th.TEXTO, font=(th.FUENTE, th.TAM_BODY)).grid(
            row=3, column=0, padx=(16, 10), pady=10, sticky="w"
        )
        self._rfc = ctk.CTkEntry(card, placeholder_text="Opcional, ayuda a separar emitidos y recibidos")
        self._rfc.grid(row=3, column=1, padx=8, pady=10, sticky="ew")
        acciones = ctk.CTkFrame(card, fg_color="transparent")
        acciones.grid(row=1, column=2, rowspan=3, padx=16, pady=10, sticky="ns")
        self._btn_guardar = BotonPrimario(acciones, "Guardar cliente", self._guardar)
        self._btn_guardar.pack(fill="x", pady=(0, 8))
        BotonSecundario(acciones, "Nuevo", self._nuevo).pack(fill="x")

        card_lista = PanelCard(contenedor)
        card_lista.grid(row=2, column=0, sticky="nsew")
        card_lista.rowconfigure(1, weight=1)
        card_lista.columnconfigure(0, weight=1)
        cabecera = ctk.CTkFrame(card_lista, fg_color="transparent")
        cabecera.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 8))
        cabecera.columnconfigure(0, weight=1)
        ctk.CTkLabel(
            cabecera, text="Clientes registrados", text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self._entrada_busqueda = ctk.CTkEntry(
            cabecera,
            textvariable=self._busqueda,
            placeholder_text="Buscar por clave, nombre o RFC",
            width=230,
        )
        self._entrada_busqueda.grid(row=1, column=0, sticky="ew", columnspan=3, pady=(8, 0))
        self._busqueda.trace_add("write", lambda *_args: self._renderizar_tabla())
        self._lbl_conteo = ctk.CTkLabel(
            cabecera, text="0 clientes", text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA),
        )
        self._lbl_conteo.grid(row=0, column=1, sticky="e", padx=(8, 0))
        botones_lista = BarraAdaptable(card_lista)
        botones_lista.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 12))
        botones_lista.agregar(BotonPrimario(botones_lista, "Entrar al cliente", self._entrar))
        botones_lista.agregar(BotonSecundario(botones_lista, "Editar seleccionado", self._editar))

        marco_tabla = ctk.CTkFrame(card_lista, fg_color="transparent")
        marco_tabla.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        marco_tabla.rowconfigure(0, weight=1)
        marco_tabla.columnconfigure(0, weight=1)
        self._tabla = ttk.Treeview(
            marco_tabla, columns=("clave", "nombre", "rfc"), show="headings",
            selectmode="browse", style="Clientes.Treeview",
        )
        for clave, titulo, ancho in (("clave", "Clave", 150), ("nombre", "Nombre", 280), ("rfc", "RFC", 150)):
            self._tabla.heading(clave, text=titulo)
            self._tabla.column(clave, width=ancho, anchor="w")
        self._tabla.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(marco_tabla, orient="vertical", command=self._tabla.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self._tabla.configure(yscrollcommand=scroll.set)
        self._tabla.bind("<Double-1>", lambda _event: self._entrar())
        self._vacio = ctk.CTkLabel(marco_tabla, text="Aún no hay clientes. Registra el primero arriba.",
                                   text_color=th.TEXTO_SECUNDARIO, fg_color=th.FONDO_TARJETA)
        self._vacio.place(relx=.5, rely=.5, anchor="center")

    def aplicar_modo_compacto(self, ancho_compacto: bool, alto_compacto: bool) -> None:
        self._contenedor.pack_configure(padx=8 if (ancho_compacto or alto_compacto) else 16,
                                       pady=8 if (ancho_compacto or alto_compacto) else 16)

    def al_mostrar(self) -> None:
        self._cargar()

    def _cargar(self) -> None:
        with Catalogo(self._db_path) as catalogo:
            self._clientes = [dict(cliente) for cliente in catalogo.clientes_detalle()]
        self._renderizar_tabla()

    def _renderizar_tabla(self) -> None:
        """Filtra la lista localmente para responder al escribir sin recargar SQLite."""
        if not hasattr(self, "_tabla"):
            return
        termino = self._busqueda.get().strip().casefold()
        visibles = [
            cliente for cliente in self._clientes
            if not termino or termino in " ".join(
                str(cliente.get(campo, "")) for campo in ("clave", "nombre", "rfc")
            ).casefold()
        ]
        for item in self._tabla.get_children():
            self._tabla.delete(item)
        for cliente in visibles:
            self._tabla.insert(
                "", "end", iid=cliente["clave"],
                values=(cliente["clave"], cliente["nombre"], cliente["rfc"]),
            )
        if visibles:
            self._vacio.place_forget()
        else:
            self._vacio.configure(text="No hay clientes que coincidan con la búsqueda." if termino else "Aún no hay clientes. Registra el primero arriba.")
            self._vacio.place(relx=.5, rely=.5, anchor="center")
        self._lbl_conteo.configure(
            text=f"{len(visibles)} de {len(self._clientes)} clientes"
            if termino else f"{len(self._clientes)} clientes"
        )

    def _seleccion(self):
        seleccion = self._tabla.selection()
        return seleccion[0] if seleccion else None

    def _nuevo(self) -> None:
        self._editando = None
        self._clave.configure(state="normal")
        for entrada in (self._clave, self._nombre, self._rfc):
            entrada.delete(0, "end")
        self._btn_guardar.configure(text="Guardar cliente")
        self._clave.focus_set()

    def _editar(self) -> None:
        clave = self._seleccion()
        if not clave:
            messagebox.showinfo("Cliente", "Selecciona un cliente para editarlo.", parent=self)
            return
        with Catalogo(self._db_path) as catalogo:
            cliente = catalogo.obtener_cliente(clave)
        if cliente is None:
            return
        self._editando = clave
        self._clave.configure(state="disabled")
        self._clave.configure(state="normal")
        self._clave.delete(0, "end"); self._clave.insert(0, clave); self._clave.configure(state="disabled")
        self._nombre.delete(0, "end"); self._nombre.insert(0, cliente["nombre"])
        self._rfc.delete(0, "end"); self._rfc.insert(0, cliente["rfc"] or "")
        self._btn_guardar.configure(text="Actualizar cliente")

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
        self._nuevo()
        self._cargar()

    def _entrar(self) -> None:
        clave = self._seleccion()
        if not clave:
            messagebox.showinfo("Cliente", "Selecciona un cliente para entrar.", parent=self)
            return
        if self._on_selected is not None:
            self._on_selected(clave)
        elif self.app is not None:
            self.app.seleccionar_cliente(clave)
