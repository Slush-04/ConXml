"""Helpers de tabla: estilo, auto-ajuste acotado y paginación de 100 filas."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from conxml.export.comun import numero as _numero_comun
from conxml.ui import theme as th

FILAS_POR_PAGINA = 100


def numero(valor) -> float | None:
    return _numero_comun(valor)


def breve(fecha: str | None) -> str:
    return fecha[:16] if fecha else ""


def aplicar_estilo_tabla(tabla: ttk.Treeview) -> None:
    """Reestila la tabla con el tema Fluent Empresarial."""
    estilo = ttk.Style()
    estilo.configure(
        "Tabla.Treeview",
        background=th.FONDO_TABLA,
        fieldbackground=th.FONDO_TABLA,
        foreground=th.TEXTO,
        borderwidth=0,
        rowheight=24,
        font=(th.FUENTE, th.TAM_TABLA),
    )
    estilo.configure(
        "Tabla.Treeview.Heading",
        background=th.FONDO,
        foreground=th.TEXTO_SECUNDARIO,
        relief="flat",
        font=(th.FUENTE, th.TAM_NOTA, "bold"),
    )
    estilo.map("Tabla.Treeview", background=[("selected", th.PRIMARIO)])
    estilo.map("Tabla.Treeview.Heading", background=[])

    tabla.tag_configure("par", background=th.FONDO_TABLA)
    tabla.tag_configure("impar", background=th.FONDO_ENTRADA)


def auto_ajustar_columnas(
    tabla: ttk.Treeview, min_ancho: int = 70, max_ancho: int = 420, max_filas: int = 100
) -> None:
    """Mide como máximo `max_filas` (la página visible) para no congelar la UI."""
    try:
        font = tkfont.Font(family=th.FUENTE, size=th.TAM_TABLA)
        font_bold = tkfont.Font(family=th.FUENTE, size=th.TAM_NOTA, weight="bold")
    except Exception:
        return

    items = tabla.get_children()
    display = tabla["displaycolumns"]
    if display and "#all" not in display:
        columnas = list(display)
    else:
        columnas = list(tabla["columns"])
    for col in columnas:
        header_text = tabla.heading(col)["text"]
        w_max = font_bold.measure(str(header_text)) + 24
        for item in items[:max_filas]:
            val = tabla.set(item, col)
            if val:
                w = font.measure(str(val)) + 18
                if w > w_max:
                    w_max = w
        ancho_final = max(min_ancho, min(w_max, max_ancho))
        tabla.column(col, width=ancho_final, stretch=False)


class PaginacionMixin:
    """Paginación genérica de 100 filas para Treeview.

    Uso: el host guarda la lista completa en `self._filas_pagina`
    (lista de tuplas values) y llama `mostrar_pagina(0)`.
    """

    filas_por_pagina: int = FILAS_POR_PAGINA
    _filas_pagina: list[tuple] = []
    _pagina: int = 0

    def _tv(self) -> ttk.Treeview:
        tabla = getattr(self, "_tabla", None)
        if tabla is None:
            raise RuntimeError("tabla no inicializada")
        return tabla

    def total_paginas(self) -> int:
        total = len(getattr(self, "_filas_pagina", []))
        return max(1, (total + self.filas_por_pagina - 1) // self.filas_por_pagina)

    def mostrar_pagina(self, pagina: int) -> None:
        tabla = self._tv()
        filas = getattr(self, "_filas_pagina", [])
        total_pags = self.total_paginas()
        self._pagina = max(0, min(pagina, total_pags - 1))
        for item in tabla.get_children():
            tabla.delete(item)
        inicio = self._pagina * self.filas_por_pagina
        for i, values in enumerate(filas[inicio : inicio + self.filas_por_pagina]):
            tabla.insert("", "end", values=values, tags=("par" if i % 2 else "impar",))
        self._actualizar_etiqueta_pagina()
        auto_ajustar_columnas(tabla, max_filas=self.filas_por_pagina)

    def pagina_siguiente(self) -> None:
        self.mostrar_pagina(self._pagina + 1)

    def pagina_anterior(self) -> None:
        self.mostrar_pagina(self._pagina - 1)

    def texto_pagina(self) -> str:
        total = len(getattr(self, "_filas_pagina", []))
        if not total:
            return "0 filas"
        ini = self._pagina * self.filas_por_pagina + 1
        fin = min(total, ini + self.filas_por_pagina - 1)
        return f"{ini}-{fin} de {total} (pág. {self._pagina + 1}/{self.total_paginas()})"

    def _actualizar_etiqueta_pagina(self) -> None:
        etiqueta = getattr(self, "_lbl_pagina", None)
        if etiqueta is not None:
            try:
                etiqueta.configure(text=self.texto_pagina())
            except tk.TclError:
                pass


__all__ = [
    "FILAS_POR_PAGINA",
    "PaginacionMixin",
    "aplicar_estilo_tabla",
    "auto_ajustar_columnas",
    "breve",
    "numero",
]
