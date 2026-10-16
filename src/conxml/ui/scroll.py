"""Desplazamiento de páginas largas sin interferir con sus tablas."""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk


class PaginaDesplazable(ctk.CTkScrollableFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._resto_touchpad_y = 0
        self._binding_touchpad = None
        if self.tk.call('info', 'commands', 'tk::PreciseScrollDeltas'):
            ventana = self.winfo_toplevel()
            # El tag de la ventana recibe también los gestos sobre las tarjetas
            # y sus controles. Las tablas consumen primero sus propios eventos.
            identificador = tk.Misc.bind(ventana, '<TouchpadScroll>', self._desplazar_touchpad, add='+')
            self._binding_touchpad = (ventana, identificador)

    def _puede_desplazar(self, event) -> bool:
        # La rueda sobre una tabla desplaza sus filas; fuera de ella desplaza
        # la página completa, incluso si el puntero está sobre una tarjeta.
        if isinstance(event.widget, ttk.Scrollbar):
            return False
        if isinstance(event.widget, ttk.Treeview) and event.widget.yview() != (0.0, 1.0):
            return False
        if not self._check_if_valid_scroll(event.widget):
            return False
        return self._parent_canvas.yview() != (0.0, 1.0)

    def _desplazar_touchpad(self, event):
        if not self._puede_desplazar(event):
            return
        try:
            _, delta_y = self.tk.call('tk::PreciseScrollDeltas', int(event.delta))
            delta_y = float(delta_y)
        except (tk.TclError, TypeError, ValueError):
            return
        if not delta_y:
            return
        # Los deltas están en píxeles; conservar el resto permite responder
        # a movimientos pequeños sin convertir cada evento en un salto grande.
        self._resto_touchpad_y -= delta_y
        incremento = float(self._parent_canvas.cget('yscrollincrement')) or 1
        pasos = int(self._resto_touchpad_y / incremento)
        if pasos:
            self._resto_touchpad_y -= pasos * incremento
            self._parent_canvas.yview_scroll(pasos, 'units')
        return 'break'

    def _mouse_wheel_all(self, event) -> None:
        if not self._puede_desplazar(event):
            return
        canvas = self._parent_canvas
        if sys.platform == "darwin":
            pasos = -int(event.delta * 3)
        elif sys.platform.startswith("win"):
            pasos = -int(event.delta / 120 * 3)
        else:
            pasos = -3 if event.num == 4 else 3
        if pasos:
            canvas.yview_scroll(pasos, "units")

    def destroy(self):
        if self._binding_touchpad is not None:
            ventana, identificador = self._binding_touchpad
            try:
                tk.Misc.unbind(ventana, '<TouchpadScroll>', identificador)
            except tk.TclError:
                pass
            self._binding_touchpad = None
        super().destroy()
