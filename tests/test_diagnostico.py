import logging
import os
import sys
from pathlib import Path

import pytest

from conxml.config import Config
from conxml.diagnostico import (
    configurar_registro,
    obtener_ruta_log,
    registrar_inicio,
    sanitizar_texto,
    mostrar_error_fatal,
    FiltroSanitizacion,
)


def test_sanitizar_texto_oculta_secretos():
    texto = "Error connecting with password='Secret1234' and token=ghp_abcdef123456"
    sanitizado = sanitizar_texto(texto)
    assert "Secret1234" not in sanitizado
    assert "ghp_abcdef123456" not in sanitizado
    assert "[PROTEGIDO]" in sanitizado


def test_filtro_sanitizacion_en_registro(tmp_path):
    filtro = FiltroSanitizacion()
    record = logging.LogRecord("test", logging.INFO, "path", 1, "clave=SuperSecretKey", (), None)
    filtro.filter(record)
    assert "SuperSecretKey" not in record.msg
    assert "[PROTEGIDO]" in record.msg


def test_ruta_log_y_creacion_directorio(tmp_path, monkeypatch):
    monkeypatch.setenv("CONXML_LOG_DIR", str(tmp_path / "custom_logs"))
    ruta = obtener_ruta_log()
    assert ruta == tmp_path / "custom_logs" / "conxml.log"
    assert (tmp_path / "custom_logs").is_dir()


def test_registrar_inicio_escribe_en_archivo(tmp_path, monkeypatch):
    monkeypatch.setenv("CONXML_LOG_DIR", str(tmp_path / "logs"))
    registrar_inicio("TEST")
    ruta = obtener_ruta_log()
    assert ruta.is_file()
    contenido = ruta.read_text(encoding="utf-8")
    assert "=== ConXml v" in contenido
    assert "Plataforma:" in contenido
    assert "Ruta datos:" in contenido


def test_excepthook_captura_y_registra(tmp_path, monkeypatch):
    monkeypatch.setenv("CONXML_LOG_DIR", str(tmp_path / "logs"))
    logger = configurar_registro()
    ruta = obtener_ruta_log()

    try:
        raise ValueError("Error de prueba no manejado")
    except ValueError:
        exc_type, exc_val, exc_tb = sys.exc_info()
        sys.excepthook(exc_type, exc_val, exc_tb)

    contenido = ruta.read_text(encoding="utf-8")
    assert "Excepción no manejada:" in contenido
    assert "ValueError: Error de prueba no manejado" in contenido
