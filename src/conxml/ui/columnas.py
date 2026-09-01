"""Visibilidad de columnas por tabla: preferencias persistentes + diálogo interactivo.

Componente reutilizable para ocultar/mostrar columnas de cualquier
``ttk.Treeview`` de la aplicación con vista previa y guardado en tiempo real.
"""
from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from conxml.config import Config
from conxml.ui import theme as th
from conxml.ui.widgets import BotonPrimario, BotonSecundario, PanelCard

ColumnasDef = list[tuple[str, str, int]]


def _carpeta(base: Path | None = None) -> Path:
    return (base or Config().base) / "configuraciones"


def cargar_ocultas(clave: str, base: Path | None = None) -> list[str]:
    """Devuelve la lista de columnas ocultas guardadas para ``clave``."""
    ruta = _carpeta(base) / f"columnas_{clave}.json"
    if not ruta.is_file():
        return []
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    ocultas = datos.get("ocultas", []) if isinstance(datos, dict) else []
    return [c for c in ocultas if isinstance(c, str)]


def guardar_ocultas(clave: str, ocultas: list[str], base: Path | None = None) -> None:
    """Persiste la lista de columnas ocultas para ``clave``."""
    ruta = _carpeta(base) / f"columnas_{clave}.json"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps({"ocultas": sorted(ocultas)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class GestorColumnas:
    """Controla qué columnas de un Treeview se muestran y persiste la elección."""

    def __init__(self, tabla, clave: str, cols_def: ColumnasDef, titulo: str = "") -> None:
        self._tabla = tabla
        self._clave = clave
        self._titulo = titulo or clave
        self._cols_def = list(cols_def)
        self._orden = [c[0] for c in cols_def]
        permitidas = set(self._orden)
        self._ocultas = [c for c in cargar_ocultas(clave) if c in permitidas]
        self.aplicar()

    def ocultas(self) -> list[str]:
        return list(self._ocultas)

    def aplicar(self) -> None:
        visibles = [c for c in self._orden if c not in self._ocultas]
        self._tabla.configure(displaycolumns=visibles if visibles else "#all")

    def fijar_ocultas(self, ocultas: list[str]) -> None:
        self._ocultas = list(ocultas)
        guardar_ocultas(self._clave, self._ocultas)
        self.aplicar()

    def abrir_dialogo(self, parent, al_aplicar=None) -> None:
        """Abre el diálogo modal con vista previa y persistencia en vivo."""

        def guardar(ocultas: list[str]) -> None:
            self.fijar_ocultas(ocultas)
            if al_aplicar is not None:
                al_aplicar()

        DialogoColumnas(parent, self._titulo, self._cols_def, self._ocultas, guardar)


class DialogoColumnas(ctk.CTkToplevel):
    """Diálogo interactivo moderno para configurar visibilidad de columnas."""

    def __init__(
        self,
        parent,
        titulo: str,
        cols_def: ColumnasDef,
        ocultas: list[str],
        al_guardar,
    ) -> None:
        super().__init__(parent)
        self.title("Configuración de Columnas Visibles")
        self.geometry("440x540")
        self.minsize(400, 440)
        self.configure(fg_color=th.FONDO)
        self.transient(parent.winfo_toplevel())
        self.after(60, self.grab_set)

        # Posicionar centrado sobre el padre
        try:
            px = parent.winfo_rootx() + (parent.winfo_width() // 2) - 245
            py = parent.winfo_rooty() + (parent.winfo_height() // 2) - 310
            self.geometry(f"+{max(px, 30)}+{max(py, 30)}")
        except Exception:
            pass

        self._cols_def = list(cols_def)
        self._claves = [c[0] for c in cols_def]
        self._al_guardar = al_guardar
        ocultas_set = set(ocultas)

        self._vars: dict[str, tk.BooleanVar] = {}
        self._filas_widgets: dict[str, ctk.CTkFrame] = {}

        # ── Cabecera Superior ────────────────────────────────────────────────
        cabecera = ctk.CTkFrame(self, fg_color="transparent")
        cabecera.pack(fill="x", padx=16, pady=(12, 6))

        info_header = ctk.CTkFrame(cabecera, fg_color="transparent")
        info_header.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            info_header,
            text="Columnas visibles",
            text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_H2, "bold"),
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            info_header,
            text=f"Tabla: {titulo}",
            text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA),
            anchor="w",
        ).pack(anchor="w", pady=(1, 0))

        # Badge contador en tiempo real
        self._lbl_contador = ctk.CTkLabel(
            cabecera,
            text="",
            text_color=th.PRIMARIO_TEXTO,
            fg_color=th.PRIMARIO_FONDO,
            corner_radius=th.RADIO_BADGE,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
            padx=12,
            pady=4,
        )
        self._lbl_contador.pack(side="right", padx=(8, 0))

        # ── Barra de Búsqueda ────────────────────────────────────────────────
        barra_busqueda = ctk.CTkFrame(self, fg_color="transparent")
        barra_busqueda.pack(fill="x", padx=16, pady=(0, 6))

        self._var_busqueda = tk.StringVar()
        self._var_busqueda.trace_add("write", lambda *_: self._filtrar_busqueda())

        self._ent_busqueda = ctk.CTkEntry(
            barra_busqueda,
            placeholder_text="🔍 Filtrar columna por nombre...",
            textvariable=self._var_busqueda,
            fg_color=th.FONDO_ENTRADA,
            border_color=th.BORDE,
            border_width=1,
            corner_radius=th.RADIO_CAMPO,
            text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_BODY),
            height=34,
        )
        self._ent_busqueda.pack(fill="x")

        # ── Acciones Rápidas ─────────────────────────────────────────────────
        barra_acciones = ctk.CTkFrame(self, fg_color="transparent")
        barra_acciones.pack(fill="x", padx=16, pady=(0, 6))

        ctk.CTkButton(
            barra_acciones,
            text="✓ Todas",
            command=self._marcar_todas,
            fg_color=th.FONDO_TARJETA,
            hover_color=th.PRIMARIO_FONDO,
            text_color=th.TEXTO,
            border_color=th.BORDE,
            border_width=1,
            corner_radius=th.RADIO_GRUPO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
            height=28,
            width=85,
        ).pack(side="left")

        ctk.CTkButton(
            barra_acciones,
            text="✗ Ninguna",
            command=self._marcar_ninguna,
            fg_color=th.FONDO_TARJETA,
            hover_color=th.PRIMARIO_FONDO,
            text_color=th.TEXTO,
            border_color=th.BORDE,
            border_width=1,
            corner_radius=th.RADIO_GRUPO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
            height=28,
            width=85,
        ).pack(side="left", padx=(6, 0))

        ctk.CTkButton(
            barra_acciones,
            text="↺ Restablecer",
            command=self._restablecer,
            fg_color=th.FONDO_TARJETA,
            hover_color=th.PRIMARIO_FONDO,
            text_color=th.TEXTO,
            border_color=th.BORDE,
            border_width=1,
            corner_radius=th.RADIO_GRUPO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
            height=28,
            width=95,
        ).pack(side="left", padx=(6, 0))

        # ── Lista de Columnas Scrollable ─────────────────────────────────────
        card_lista = PanelCard(self, fondo=th.FONDO_TARJETA)
        card_lista.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self._marco_scroll = ctk.CTkScrollableFrame(card_lista, fg_color="transparent")
        self._marco_scroll.pack(fill="both", expand=True, padx=6, pady=6)

        for clave, texto, _ancho in cols_def:
            var = tk.BooleanVar(value=(clave not in ocultas_set))
            self._vars[clave] = var

            fila = ctk.CTkFrame(self._marco_scroll, fg_color="transparent")
            fila.pack(fill="x", padx=4, pady=2)
            self._filas_widgets[clave] = fila

            chk = ctk.CTkCheckBox(
                fila,
                text=texto,
                variable=var,
                command=self._al_cambiar_item,
                fg_color=th.PRIMARIO,
                hover_color=th.PRIMARIO_HOVER,
                border_color=th.BORDE,
                text_color=th.TEXTO,
                corner_radius=4,
                font=(th.FUENTE, th.TAM_BODY),
            )
            chk.pack(side="left", anchor="w", padx=6, pady=4)

        # ── Pie de Diálogo (Footer con botón principal) ──────────────────────
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(0, 12))

        self._btn_listo = BotonPrimario(
            footer,
            "✓ Listo (Guardar y Cerrar)",
            self._cerrar,
            height=38,
        )
        self._btn_listo.pack(fill="x")

        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.bind("<Escape>", lambda _: self._cerrar())
        self.bind("<Return>", lambda _: self._cerrar())

        self._actualizar_contador()

    # ── Lógica de Interacción ─────────────────────────────────────────────────

    def _actualizar_contador(self) -> None:
        total = len(self._claves)
        visibles = sum(1 for v in self._vars.values() if v.get())
        self._lbl_contador.configure(text=f"{visibles} de {total} visibles")

    def _al_cambiar_item(self) -> None:
        """Aplica y guarda los cambios en tiempo real cada vez que se toca un checkbox."""
        visibles = sum(1 for v in self._vars.values() if v.get())
        if visibles == 0:
            # Si desmarcó todo, evitar que quede completamente vacío
            messagebox.showwarning(
                "Columna requerida",
                "Debes mantener al menos una columna visible.",
                parent=self,
            )
            # Reactivar la primera
            if self._claves:
                self._vars[self._claves[0]].set(True)

        self._actualizar_contador()
        self._persistir_cambios()

    def _persistir_cambios(self) -> None:
        ocultas = [c for c in self._claves if not self._vars[c].get()]
        if len(ocultas) < len(self._claves):
            self._al_guardar(ocultas)

    def _filtrar_busqueda(self) -> None:
        query = self._var_busqueda.get().strip().lower()
        for clave, texto, _ in self._cols_def:
            fila = self._filas_widgets.get(clave)
            if not fila:
                continue
            if not query or query in texto.lower() or query in clave.lower():
                fila.pack(fill="x", padx=4, pady=2)
            else:
                fila.pack_forget()

    def _marcar_todas(self) -> None:
        for var in self._vars.values():
            var.set(True)
        self._actualizar_contador()
        self._persistir_cambios()

    def _marcar_ninguna(self) -> None:
        # Deja solo la primera columna visible para evitar error de Treeview vacío
        for i, (clave, var) in enumerate(self._vars.items()):
            var.set(i == 0)
        self._actualizar_contador()
        self._persistir_cambios()

    def _restablecer(self) -> None:
        # Restablece todas visibles por defecto
        for var in self._vars.values():
            var.set(True)
        self._actualizar_contador()
        self._persistir_cambios()

    def _cerrar(self) -> None:
        self._persistir_cambios()
        self.destroy()

