"""Desplazamiento de páginas largas sin interferir con sus tablas."""
from __future__ import annotations

import sys
from tkinter import ttk

import customtkinter as ctk


class PaginaDesplazable(ctk.CTkScrollableFrame):
    def _mouse_wheel_all(self, event) -> None:
        # La rueda sobre una tabla desplaza sus filas; fuera de ella desplaza
        # la página completa, incluso si el puntero está sobre una tarjeta.
        if isinstance(event.widget, ttk.Scrollbar):
            return
        if isinstance(event.widget, ttk.Treeview) and event.widget.yview() != (0.0, 1.0):
            return
        if not self._check_if_valid_scroll(event.widget):
            return
        canvas = self._parent_canvas
        if canvas.yview() == (0.0, 1.0):
            return
        if sys.platform == "darwin":
            pasos = -int(event.delta * 3)
        elif sys.platform.startswith("win"):
            pasos = -int(event.delta / 120 * 3)
        else:
            pasos = -3 if event.num == 4 else 3
        if pasos:
            canvas.yview_scroll(pasos, "units")
