"""Campo de fecha con calendario compartido por las pantallas."""
from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date, datetime

import customtkinter as ctk

from conxml.ui import theme as th


class SelectorFecha(ctk.CTkFrame):
    """Campo compacto DD/MM/AA con calendario desplegable."""

    def __init__(self, parent, al_cambiar=None, *, variable=None, anio_completo=False) -> None:
        super().__init__(parent, fg_color="transparent", height=32)
        self._al_cambiar = al_cambiar
        self._valor = variable if variable is not None else tk.StringVar()
        self._formato = "%d/%m/%Y" if anio_completo else "%d/%m/%y"
        self._popup = None
        self._mes_mostrado = date.today().replace(day=1)

        self._entrada = ctk.CTkEntry(
            self, textvariable=self._valor, width=118 if anio_completo else 96, height=32,
            placeholder_text="DD/MM/AAAA" if anio_completo else "DD/MM/AA", font=(th.FUENTE, th.TAM_BODY),
        )
        self._entrada.pack(side="left", fill="x", expand=True)
        self._entrada.bind("<KeyRelease>", lambda _event: self._notificar())
        self._entrada.bind("<Return>", lambda _event: self._notificar())
        self._entrada.bind("<FocusOut>", lambda _event: self._normalizar())
        self._entrada.bind("<Down>", lambda _event: self._abrir_calendario())
        ctk.CTkButton(
            self, text="▾", width=28, height=32,
            fg_color=th.FONDO_TARJETA, hover_color=th.PRIMARIO_FONDO,
            text_color=th.TEXTO_SECUNDARIO, border_width=1,
            border_color=th.BORDE, corner_radius=th.RADIO_CAMPO,
            font=(th.FUENTE, th.TAM_BODY, "bold"),
            command=self._abrir_calendario,
        ).pack(side="left", padx=(4, 0))

    def get(self) -> str:
        return self._valor.get()

    def set(self, valor: str) -> None:
        self._valor.set(valor)

    def delete(self, _inicio=0, _fin="end") -> None:
        self._valor.set("")

    def _notificar(self) -> None:
        if callable(self._al_cambiar):
            self._al_cambiar()

    def _normalizar(self) -> None:
        valor = self.get().strip()
        if len(valor) == 8 and valor.isdigit():
            valor = f"{valor[:2]}/{valor[2:4]}/{valor[4:]}"
        fecha = self._parsear(valor)
        if fecha:
            self._valor.set(fecha.strftime(self._formato))
            self._notificar()

    def _abrir_calendario(self) -> None:
        if self._popup is not None and self._popup.winfo_exists():
            self._popup.focus_force()
            return
        actual = self._parsear(self.get())
        self._mes_mostrado = actual.replace(day=1) if actual else date.today().replace(day=1)
        popup = ctk.CTkToplevel(self.winfo_toplevel())
        self._popup = popup
        popup.title("Seleccionar fecha")
        popup.geometry("270x265")
        popup.resizable(False, False)
        popup.transient(self.winfo_toplevel())
        popup.configure(fg_color=th.FONDO)

        contenido = ctk.CTkFrame(popup, fg_color="transparent")
        contenido.pack(fill="both", expand=True, padx=10, pady=10)
        cabecera = ctk.CTkFrame(contenido, fg_color="transparent")
        cabecera.pack(fill="x")
        self._btn_mes_anterior = ctk.CTkButton(
            cabecera, text="‹", width=30, height=28, fg_color="transparent",
            hover_color=th.PRIMARIO_FONDO, text_color=th.TEXTO,
            command=lambda: self._mover_mes(-1),
        )
        self._btn_mes_anterior.pack(side="left")
        self._lbl_mes = ctk.CTkLabel(
            cabecera, text="", text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_BODY, "bold"),
        )
        self._lbl_mes.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            cabecera, text="›", width=30, height=28, fg_color="transparent",
            hover_color=th.PRIMARIO_FONDO, text_color=th.TEXTO,
            command=lambda: self._mover_mes(1),
        ).pack(side="right")

        self._marco_dias = ctk.CTkFrame(contenido, fg_color="transparent")
        self._marco_dias.pack(fill="both", expand=True, pady=(6, 0))
        for columna, nombre in enumerate(("Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do")):
            self._marco_dias.columnconfigure(columna, weight=1)
            ctk.CTkLabel(
                self._marco_dias, text=nombre, text_color=th.TEXTO_SECUNDARIO,
                font=(th.FUENTE, th.TAM_NOTA, "bold"),
            ).grid(row=0, column=columna, padx=1, pady=1)
        self._dibujar_dias()
        popup.protocol("WM_DELETE_WINDOW", self._cerrar_popup)
        popup.bind("<Escape>", lambda _event: self._cerrar_popup())
        popup.update_idletasks()
        x = max(0, min(self.winfo_rootx(), popup.winfo_screenwidth() - popup.winfo_width()))
        y = self.winfo_rooty() + self.winfo_height() + 4
        if y + popup.winfo_height() > popup.winfo_screenheight():
            y = max(0, self.winfo_rooty() - popup.winfo_height() - 4)
        popup.geometry(f"+{x}+{y}")
        popup.deiconify()
        popup.focus_force()

    def _mover_mes(self, desplazamiento: int) -> None:
        mes = self._mes_mostrado.month - 1 + desplazamiento
        anio = self._mes_mostrado.year + mes // 12
        if not 1 <= anio <= 9999:
            return
        mes = mes % 12 + 1
        self._mes_mostrado = date(anio, mes, 1)
        self._dibujar_dias()

    def _dibujar_dias(self) -> None:
        if self._popup is None or not self._popup.winfo_exists():
            return
        meses = (
            "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
        )
        self._lbl_mes.configure(text=f"{meses[self._mes_mostrado.month]} {self._mes_mostrado.year}")
        for hijo in self._marco_dias.grid_slaves():
            if int(hijo.grid_info().get("row", 0)) > 0:
                hijo.destroy()
        seleccionado = self._parsear(self.get())
        for fila, semana in enumerate(calendar.monthcalendar(self._mes_mostrado.year, self._mes_mostrado.month), start=1):
            for columna, dia in enumerate(semana):
                if not dia:
                    continue
                fecha = date(self._mes_mostrado.year, self._mes_mostrado.month, dia)
                activo = seleccionado == fecha
                ctk.CTkButton(
                    self._marco_dias, text=str(dia), width=30, height=27,
                    fg_color=th.PRIMARIO if activo else "transparent",
                    hover_color=th.PRIMARIO_HOVER if activo else th.PRIMARIO_FONDO,
                    text_color="#FFFFFF" if activo else th.TEXTO,
                    corner_radius=4, font=(th.FUENTE, th.TAM_NOTA),
                    command=lambda valor=fecha: self._seleccionar(valor),
                ).grid(row=fila, column=columna, padx=1, pady=1)

    def _seleccionar(self, fecha: date) -> None:
        self._valor.set(fecha.strftime(self._formato))
        self._notificar()
        self._cerrar_popup()

    def _cerrar_popup(self) -> None:
        if self._popup is not None:
            self._popup.destroy()
            self._popup = None

    def destroy(self) -> None:
        self._cerrar_popup()
        super().destroy()

    @staticmethod
    def _parsear(valor: str) -> date | None:
        for formato in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M"):
            try:
                return datetime.strptime(valor.strip(), formato).date()
            except (TypeError, ValueError):
                pass
        return None
