"""Sistema visual de ConXml sobre CustomTkinter.

Tokens de color sólidos (strings simples), sin transparencias ni tuplas de modo.
La aplicación funciona en modo Claro ("Light") fijo.
"""
from __future__ import annotations

import sys
from tkinter import ttk
import customtkinter as ctk



# Tipografía
FUENTE = "Helvetica Neue" if sys.platform == "darwin" else "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"
FUENTE_MONO = "Menlo" if sys.platform == "darwin" else "Consolas" if sys.platform == "win32" else "DejaVu Sans Mono"

TAM_H1 = 24
TAM_H2 = 16
TAM_H3 = 14
TAM_BODY = 13
TAM_NOTA = 12
TAM_TABLA = 10

# Alias compatibles
TAM_VALOR = TAM_H1
TAM_TITULO = TAM_H2
TAM_BASE = TAM_BODY

# Radios de esquina (sin sombras pronunciadas)
RADIO_PANEL = 12
RADIO_TARJETA = 12
RADIO_BOTON = 8
RADIO_CAMPO = 8
RADIO_BADGE = 50
RADIO_GRUPO = 8
RADIO_BORDE = 2

# Colores Principales (Flat / Fluent Empresarial)
PRIMARIO = "#3759C7"
PRIMARIO_HOVER = "#2946A8"
PRIMARIO_FONDO = "#EDF1FF"
PRIMARIO_TEXTO = "#304BA5"

FONDO = "#F5F6FA"
FONDO_TARJETA = "#FFFFFF"
FONDO_SIDEBAR = "#171F33"
FONDO_TABLA = "#FFFFFF"
FONDO_ENTRADA = "#F3F5F9"

BORDE = "#E0E5EE"
BORDE_FOCUS = "#3759C7"
BORDE_TARJETA = BORDE
BORDE_SUAVE = "#F3F5F9"

TEXTO = "#202A40"
TEXTO_SECUNDARIO = "#626E83"
TEXTO_DISABLED = "#9AA6BB"
SUBTEXTO = TEXTO_SECUNDARIO

# Navegación lateral
SIDEBAR_FONDO = "#171F33"
SIDEBAR_TEXTO = "#9AA6BB"
SIDEBAR_HOVER = "#27334D"
SIDEBAR_TEXTO_ACTIVO = "#FFFFFF"
SIDEBAR_ACENTO = "#3759C7"

# Colores Semánticos (Estatus SAT y alertas)
VERDE = "#16836A"
VERDE_FONDO = "#F0FDF4"
ROJO = "#C74354"
ROJO_FONDO = "#FEF2F2"
AMBAR = "#A76C14"
AMBAR_FONDO = "#FFFBEB"
GRIS = "#64748B"
GRIS_FONDO = "#F5F6FA"

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
    tema = ctk.ThemeManager.theme
    for nombre in ("CTk", "CTkToplevel"):
        tema[nombre]["fg_color"] = FONDO
    tema["CTkFrame"].update(fg_color=FONDO_TARJETA, top_fg_color=FONDO_ENTRADA,
                            border_color=BORDE, corner_radius=RADIO_PANEL)
    tema["CTkLabel"]["text_color"] = TEXTO
    for nombre in ("CTkEntry", "CTkComboBox"):
        tema[nombre].update(fg_color=FONDO_TARJETA, border_color=BORDE,
                            border_width=1, text_color=TEXTO, corner_radius=RADIO_CAMPO)
    tema["CTkEntry"]["placeholder_text_color"] = TEXTO_SECUNDARIO
    tema["CTkComboBox"].update(button_color=BORDE, button_hover_color=TEXTO_DISABLED)
    tema["CTkButton"].update(fg_color=PRIMARIO, hover_color=PRIMARIO_HOVER,
                             text_color="#FFFFFF", corner_radius=RADIO_BOTON)
    tema["CTkCheckBox"].update(fg_color=PRIMARIO, hover_color=PRIMARIO_HOVER,
                              text_color=TEXTO, border_color=TEXTO_DISABLED, border_width=2)
    tema["CTkScrollbar"].update(button_color="#CAD1DE", button_hover_color=TEXTO_DISABLED)
    tema["DropdownMenu"].update(fg_color=FONDO_TARJETA, hover_color=PRIMARIO_FONDO, text_color=TEXTO)
    tema["CTkFont"].update(family=FUENTE, size=TAM_BODY)



def configurar_tablas(master) -> None:
    """Tablas coherentes con CTk, también en selectores y diálogos."""
    estilo = ttk.Style(master)
    if estilo.theme_use() != "clam":
        estilo.theme_use("clam")
    for nombre in ("Treeview", "Tabla.Treeview", "Solicitudes.Treeview"):
        estilo.configure(nombre, background=FONDO_TABLA, fieldbackground=FONDO_TABLA,
                         foreground=TEXTO, borderwidth=0, relief="flat", rowheight=27,
                         font=(FUENTE, 10))
        estilo.configure(nombre + ".Heading", background=FONDO_ENTRADA,
                         foreground=TEXTO_SECUNDARIO, relief="flat", borderwidth=0,
                         padding=(8, 6), font=(FUENTE, 11, "bold"))
        estilo.map(nombre, background=[("selected", PRIMARIO_FONDO)],
                   foreground=[("selected", PRIMARIO_TEXTO)])
        estilo.map(nombre + ".Heading", background=[("active", BORDE_SUAVE)])
    estilo.configure("Clientes.Treeview", background=FONDO_TABLA, fieldbackground=FONDO_TABLA,
                     foreground=TEXTO, borderwidth=0, relief="flat", rowheight=25,
                     font=(FUENTE, 9))
    estilo.configure("Clientes.Treeview.Heading", background=FONDO_ENTRADA,
                     foreground=TEXTO_SECUNDARIO, relief="flat", borderwidth=0,
                     padding=(8, 5), font=(FUENTE, 10, "bold"))
    estilo.map("Clientes.Treeview", background=[("selected", PRIMARIO_FONDO)],
               foreground=[("selected", PRIMARIO_TEXTO)])
    estilo.map("Clientes.Treeview.Heading", background=[("active", BORDE_SUAVE)])
    estilo.configure("TScrollbar", background=BORDE, troughcolor=FONDO,
                     borderwidth=0, arrowsize=12, relief="flat")
