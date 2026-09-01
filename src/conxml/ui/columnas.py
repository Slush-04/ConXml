"""Visibilidad de columnas por tabla: preferencias persistentes + diálogo.

Componente reutilizable para ocultar/mostrar columnas de cualquier
``ttk.Treeview`` de la aplicación. La guía para replicarlo en tablas nuevas
vive en ``configuraciones/columnas-visibles-en-tablas.md``.

Uso típico dentro de una pantalla::

    gestor = GestorColumnas(tabla, "mi_tabla", _MIS_COLUMNAS, "Mi tabla")
    ...
    gestor.abrir_dialogo(self, al_aplicar=auto_ajustar_columnas)

Las preferencias se guardan en ``<data>/configuraciones/columnas_<clave>.json``.
"""
from __future__ import annotations

import json
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox

from conxml.config import Config
from conxml.ui import theme as th
from conxml.ui.widgets import BotonPrimario, BotonSecundario

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

    def _fijar_ocultas(self, ocultas: list[str]) -> None:
        self._ocultas = ocultas
        guardar_ocultas(self._clave, ocultas)
        self.aplicar()

    def abrir_dialogo(self, parent, al_aplicar=None) -> None:
        """Abre el diálogo modal; al aceptar persiste y aplica la selección."""

        def aceptar(ocultas: list[str]) -> None:
            self._fijar_ocultas(ocultas)
            if al_aplicar is not None:
                al_aplicar()

        DialogoColumnas(parent, self._titulo, self._cols_def, self._ocultas, aceptar)


class DialogoColumnas(ctk.CTkToplevel):
    """Diálogo modal con un checkbox por columna (mínimo una visible)."""

    def __init__(
        self,
        parent,
        titulo: str,
        cols_def: ColumnasDef,
        ocultas: list[str],
        al_aceptar,
    ) -> None:
        super().__init__(parent)
        self.title(f"Columnas visibles — {titulo}")
        self.geometry("430x540")
        self.configure(fg_color=th.FONDO)
        self.transient(parent.winfo_toplevel())
        self.after(60, self.grab_set)
        self.geometry(
            f"+{max(parent.winfo_rootx() - 60, 0)}+{max(parent.winfo_rooty() - 40, 0)}"
        )

        self._claves = [c[0] for c in cols_def]
        self._al_aceptar = al_aceptar
        ocultas_set = set(ocultas)
        self._vars: dict[str, ctk.BooleanVar] = {}

        ctk.CTkLabel(
            self, text="Selecciona las columnas que quieres ver",
            text_color=th.TEXTO, font=(th.FUENTE, th.TAM_H3, "bold"),
        ).pack(anchor="w", padx=16, pady=(16, 4))

        marco = ctk.CTkScrollableFrame(self, fg_color=th.FONDO_TARJETA)
        marco.pack(fill="both", expand=True, padx=16, pady=8)
        for clave, texto, _ancho in cols_def:
            var = ctk.BooleanVar(value=clave not in ocultas_set)
            ctk.CTkCheckBox(
                marco, text=texto, variable=var,
                fg_color=th.PRIMARIO, hover_color=th.PRIMARIO_HOVER,
                border_color=th.BORDE, text_color=th.TEXTO,
                corner_radius=4, font=(th.FUENTE, th.TAM_BODY),
            ).pack(anchor="w", padx=8, pady=3)
            self._vars[clave] = var

        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(fill="x", padx=16, pady=(0, 16))
        BotonSecundario(botones, "Todas", self._marcar_todas).pack(side="left")
        BotonSecundario(botones, "Ninguna", self._marcar_ninguna).pack(side="left", padx=(8, 0))
        BotonSecundario(botones, "Cancelar", self.destroy).pack(side="right")
        BotonPrimario(botones, "Aplicar", self._aplicar).pack(side="right", padx=(0, 8))

    def _marcar_todas(self) -> None:
        for var in self._vars.values():
            var.set(True)

    def _marcar_ninguna(self) -> None:
        for var in self._vars.values():
            var.set(False)

    def _aplicar(self) -> None:
        ocultas = [c for c in self._claves if not self._vars[c].get()]
        if len(ocultas) == len(self._claves):
            messagebox.showwarning(
                "Sin columnas",
                "Deja al menos una columna visible.",
                parent=self,
            )
            return
        self._al_aceptar(ocultas)
        self.destroy()
