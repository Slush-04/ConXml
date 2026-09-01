"""Tokens de diseño Fluent Empresarial de ConXml sobre CustomTkinter.

Tokens de color sólidos (strings simples), sin transparencias ni tuplas de modo.
La aplicación funciona en modo Claro ("Light") fijo.
"""
from __future__ import annotations

import tkinter.font as tkfont
import customtkinter as ctk


def _tiene_fuente(nombre: str) -> bool:
    try:
        return nombre in tkfont.families()
    except Exception:
        return False


# Tipografía
FUENTE = "Segoe UI Variable" if _tiene_fuente("Segoe UI Variable") else "Segoe UI"
FUENTE_MONO = "Cascadia Code" if _tiene_fuente("Cascadia Code") else "Consolas"

TAM_H1 = 22
TAM_H2 = 15
TAM_H3 = 13
TAM_BODY = 12
TAM_NOTA = 11
TAM_TABLA = 10

# Alias compatibles
TAM_VALOR = TAM_H1
TAM_TITULO = TAM_H2
TAM_BASE = TAM_BODY

# Radios de esquina (sin sombras pronunciadas)
RADIO_PANEL = 8
RADIO_TARJETA = 8
RADIO_BOTON = 6
RADIO_CAMPO = 6
RADIO_BADGE = 50
RADIO_GRUPO = 5
RADIO_BORDE = 2

# Colores Principales (Flat / Fluent Empresarial)
PRIMARIO = "#2563EB"
PRIMARIO_HOVER = "#1D4ED8"
PRIMARIO_FONDO = "#EFF6FF"
PRIMARIO_TEXTO = "#1E40AF"

FONDO = "#F8FAFC"
FONDO_TARJETA = "#FFFFFF"
FONDO_SIDEBAR = "#1E293B"
FONDO_TABLA = "#FFFFFF"
FONDO_ENTRADA = "#F1F5F9"

BORDE = "#E2E8F0"
BORDE_FOCUS = "#2563EB"
BORDE_TARJETA = BORDE
BORDE_SUAVE = "#F1F5F9"

TEXTO = "#0F172A"
TEXTO_SECUNDARIO = "#475569"
TEXTO_DISABLED = "#94A3B8"
SUBTEXTO = TEXTO_SECUNDARIO

# Colores de Sidebar (Slate-800)
SIDEBAR_FONDO = "#1E293B"
SIDEBAR_TEXTO = "#94A3B8"
SIDEBAR_HOVER = "#334155"
SIDEBAR_TEXTO_ACTIVO = "#FFFFFF"
SIDEBAR_ACENTO = "#2563EB"

# Colores Semánticos (Estatus SAT y alertas)
VERDE = "#16A34A"
VERDE_FONDO = "#F0FDF4"
ROJO = "#DC2626"
ROJO_FONDO = "#FEF2F2"
AMBAR = "#D97706"
AMBAR_FONDO = "#FFFBEB"
GRIS = "#64748B"
GRIS_FONDO = "#F8FAFC"

PASO = 4

TONOS = {
    "verde": (VERDE, VERDE_FONDO),
    "rojo": (ROJO, ROJO_FONDO),
    "ambar": (AMBAR, AMBAR_FONDO),
    "gris": (GRIS, GRIS_FONDO),
    "azul": (PRIMARIO, PRIMARIO_FONDO),
}


def configurar_ctk() -> None:
    """Configura CTK: apariencia fija Light y tema de color azul."""
    ctk.set_appearance_mode("Light")
    ctk.set_default_color_theme("blue")
