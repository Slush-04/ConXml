"""Registro de diagnóstico y captura de errores de arranque en ConXml.

Escribe registros persistentes en %LOCALAPPDATA%\\ConXml\\logs\\conxml.log (Windows)
o ~/Library/Logs/ConXml (macOS), garantizando que no se registren secretos ni
datos confidenciales.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import platform
import re
import sys
import traceback
from pathlib import Path
from typing import Any

from conxml import __version__
from conxml.config import Config

_INICIALIZADO = False
_PATRONES_SECRETOS = [
    re.compile(r"(password|contrase[ñn]a|token|secret|clave|llave|authorization)\s*[:=]\s*['\"]?([^'\"\s&]+)", re.IGNORECASE),
    re.compile(r"Bearer\s+([a-zA-Z0-9_\-\.]+)", re.IGNORECASE),
]


class FiltroSanitizacion(logging.Filter):
    """Oculta credenciales y tokens accidentales en mensajes de registro."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitizar_texto(record.msg)
        if record.args:
            record.args = tuple(sanitizar_texto(str(a)) if isinstance(a, str) else a for a in record.args)
        return True


def sanitizar_texto(texto: str) -> str:
    """Reemplaza valores de secretos por [PROTEGIDO]."""
    resultado = texto
    for patron in _PATRONES_SECRETOS:
        resultado = patron.sub(r"\1: [PROTEGIDO]", resultado)
    return resultado


def obtener_ruta_log() -> Path:
    """Devuelve la ruta absoluta del archivo de registro principal."""
    config = Config()
    directorio = config.logs_dir
    try:
        directorio.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return directorio / "conxml.log"


def configurar_registro() -> logging.Logger:
    """Configura el logger raíz con rotación de archivos y captura de excepciones."""
    global _INICIALIZADO
    logger = logging.getLogger("conxml")
    if _INICIALIZADO:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    filtro = FiltroSanitizacion()
    formato = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    ruta_log = obtener_ruta_log()
    try:
        handler_archivo = logging.handlers.RotatingFileHandler(
            ruta_log, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        handler_archivo.setFormatter(formato)
        handler_archivo.addFilter(filtro)
        logger.addHandler(handler_archivo)
    except OSError:
        pass

    # Handler a consola si está disponible
    if sys.stderr and hasattr(sys.stderr, "write"):
        handler_consola = logging.StreamHandler(sys.stderr)
        handler_consola.setFormatter(formato)
        handler_consola.addFilter(filtro)
        logger.addHandler(handler_consola)

    _instalar_excepthook(logger, ruta_log)
    _INICIALIZADO = True
    return logger


def registrar_inicio(contexto: str = "GUI") -> None:
    """Registra datos del entorno al iniciar la aplicación."""
    logger = configurar_registro()
    config = Config()
    logger.info("=== ConXml v%s iniciado (%s) ===", __version__, contexto)
    logger.info("Plataforma: %s %s (%s)", sys.platform, platform.machine(), platform.platform())
    logger.info("Python: %s", sys.version.replace("\n", " "))
    logger.info("Ejecutable: %s (frozen=%s)", sys.executable, getattr(sys, "frozen", False))
    logger.info("Ruta datos: %s", config.base)
    logger.info("Ruta logs: %s", config.logs_dir)


def mostrar_error_fatal(titulo: str, mensaje: str) -> None:
    """Muestra un diálogo de error nativo legible sin depender del ciclo de eventos Tk."""
    logger = logging.getLogger("conxml")
    logger.critical("%s: %s", titulo, mensaje)

    # Intento 1: Diálogo nativo Windows sin inicializar Tk
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f"{mensaje}\n\nConsulta el registro en:\n{obtener_ruta_log()}", titulo, 0x10)
            return
        except Exception:
            pass

    # Intento 2: Tkinter si está disponible
    try:
        from tkinter import messagebox
        messagebox.showerror(titulo, f"{mensaje}\n\nConsulta el registro en:\n{obtener_ruta_log()}")
    except Exception:
        pass


def _instalar_excepthook(logger: logging.Logger, ruta_log: Path) -> None:
    """Captura excepciones no manejadas y las escribe en el archivo de registro."""
    def excepthook(exc_type: type[BaseException], exc_value: BaseException, exc_tb: Any) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        tb_texto = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.critical("Excepción no manejada:\n%s", tb_texto)
        if getattr(sys, "frozen", False) or not sys.stderr:
            mostrar_error_fatal("Error inesperado en ConXml", f"{exc_type.__name__}: {exc_value}")

    sys.excepthook = excepthook
