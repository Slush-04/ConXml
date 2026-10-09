"""Introducción local de primera apertura, con reproductores nativos del sistema."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from typing import Callable

from conxml import estado_local

logger = logging.getLogger("conxml")
CLAVE_VISTA = "introduccion_vista"


def _recurso(nombre: str) -> Path:
    base = (Path(getattr(sys, "_MEIPASS", ".")) / "assets"
            if getattr(sys, "frozen", False) else Path(__file__).parent / "assets")
    return base / nombre


def _comando() -> list[str] | None:
    video = _recurso("introduccion.mp4")
    if not video.is_file():
        return None
    if sys.platform == "darwin":
        ejecutable = (_recurso("conxml-intro-player") if getattr(sys, "frozen", False)
                      else Path(__file__).resolve().parents[3] / "build/native/conxml-intro-player")
        return [str(ejecutable), str(video)] if ejecutable.is_file() else None
    if sys.platform == "win32":
        script = (_recurso("Introduccion.ps1") if getattr(sys, "frozen", False)
                  else Path(__file__).parent / "native/Introduccion.ps1")
        powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        if script.is_file() and powershell.is_file():
            return [str(powershell), "-NoProfile", "-NonInteractive", "-STA",
                    "-ExecutionPolicy", "Bypass", "-File", str(script), "-Video", str(video)]
    return None


class ReproductorIntroduccion:
    """Vigila el reproductor sin bloquear Tk ni dejar música tras cerrar la app."""

    def __init__(self, parent, proceso, al_terminar: Callable[[], None], primera: bool):
        self.parent = parent
        self.proceso = proceso
        self.al_terminar = al_terminar
        self.primera = primera
        self.cerrado = False
        self._after = None
        self._binding = parent.bind("<Destroy>", self._al_destruir, add="+")

    def comprobar(self):
        if self.cerrado:
            return
        codigo = self.proceso.poll()
        if codigo is None:
            self._after = self.parent.after(100, self.comprobar)
            return
        self.cerrado = True
        if self._binding:
            self.parent.unbind("<Destroy>", self._binding)
        self.parent._introduccion = None
        if codigo == 0 and self.primera:
            try:
                estado_local.guardar({CLAVE_VISTA: True})
            except OSError:
                logger.exception("No se pudo guardar la preferencia de introducción")
        elif codigo != 0:
            logger.warning("El reproductor de introducción terminó con código %s", codigo)
        self.parent.deiconify()
        self.al_terminar()

    def _al_destruir(self, event):
        if event.widget is not self.parent or self.cerrado:
            return
        self.cerrado = True
        if self._after:
            try:
                self.parent.after_cancel(self._after)
            except tk.TclError:
                pass
        if self.proceso.poll() is None:
            try:
                self.proceso.terminate()
            except OSError:
                pass


def mostrar_introduccion(parent, al_terminar: Callable[[], None] | None = None,
                         *, primera: bool = False) -> bool:
    """Devuelve False si no puede iniciar; el programa continúa sin marcarla vista."""
    if getattr(parent, "_introduccion", None) is not None:
        return True
    comando = _comando()
    if comando is None:
        logger.warning("Introducción o reproductor local no disponible")
        return False
    try:
        proceso = subprocess.Popen(comando, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    except OSError:
        logger.exception("No se pudo iniciar la introducción")
        return False
    reproductor = ReproductorIntroduccion(parent, proceso, al_terminar or (lambda: None), primera)
    parent._introduccion = reproductor
    if primera:
        parent.withdraw()
    parent.after(100, reproductor.comprobar)
    return True


def primera_apertura(parent, continuar: Callable[[], None]) -> None:
    """Muestra una sola vez por perfil local; omitir o cerrar también la completa."""
    if estado_local.cargar().get(CLAVE_VISTA) is True:
        continuar()
    elif not mostrar_introduccion(parent, continuar, primera=True):
        continuar()
