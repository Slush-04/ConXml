"""Ventana principal de ConXml: navegación por secciones, tareas en segundo plano."""
from __future__ import annotations

import queue
import sys
import threading
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext

import customtkinter as ctk

from conxml.boveda import inicializar_boveda
from conxml.catalog.db import Catalogo
from conxml.config import Config
from conxml.ui import responsive as resp
from conxml.ui import theme as th
from conxml.ui.pantalla_admin import (
    MODO_CFDI40,
    MODO_NOMINA,
    MODO_PAGOS,
    PantallaAdministracion,
)
from conxml.ui.pantalla_ajustes import PantallaAjustes
from conxml.ui.pantalla_boveda import PantallaBoveda
from conxml.ui.pantalla_clientes import PantallaClientes
from conxml.ui.pantalla_descargas import PantallaDescargas
from conxml.ui.pantalla_resumen import PantallaResumen
from conxml.ui.widgets import PanelCard

SECCIONES = [
    ("admin_xml", "ADMINISTRACIÓN XML", [
        ("descargas", "⬇ Descarga de XML"),
        ("admin40", "📄 XML 4.0 (Ingr/Egr/Tras)"),
        ("pagos", "💸 Conciliación de Pagos"),
        ("nomina", "👔 Recibos de Nómina"),
    ]),
    ("sistema", "SISTEMA", [
        ("clientes", "👥 Cambiar cliente"),
        ("ajustes", "⚙️ Configuración y Ajustes"),
    ]),
]

NOMBRE_ICONO = "logo_conxml"

# Textos completos y breves del sidebar (compacto legible, no solo emojis).
TEXTO_NAV_COMPLETO = {
    "descargas": "⬇ Descarga de XML",
    "resumen": "📊 Resumen",
    "admin40": "📄 XML 4.0 (Ingr/Egr/Tras)",
    "pagos": "💸 Conciliación de Pagos",
    "nomina": "👔 Recibos de Nómina",
    "ajustes": "⚙️ Configuración y Ajustes",
    "clientes": "Cambiar cliente",
    "boveda": "🗄️ Bóveda",
}
TEXTO_NAV_BREVE = {
    "descargas": "Descargas",
    "resumen": "Resumen",
    "admin40": "XML 4.0",
    "pagos": "Pagos",
    "nomina": "Nómina",
    "ajustes": "Ajustes",
    "clientes": "Cliente",
    "boveda": "Bóveda",
}
TITULO_GRUPO_COMPLETO = {
    "admin_xml": "ADMINISTRACIÓN XML",
    "sistema": "SISTEMA",
}
TITULO_GRUPO_BREVE = {
    "admin_xml": "XML",
    "sistema": "SIST",
}


def _ruta_icono(extension: str) -> Path | None:
    """Localiza el icono tanto en desarrollo como dentro del .exe de PyInstaller."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", "."))
    else:
        base = Path(__file__).resolve().parent
    ruta = base / "assets" / f"{NOMBRE_ICONO}.{extension}"
    return ruta if ruta.is_file() else None


def _aplicar_icono(raiz: ctk.CTk) -> None:
    """Icono nítido en barra de tareas: iconphoto con PNG grande (issue #2790 de CTk)."""
    ruta_png = _ruta_icono("png")
    ruta_ico = _ruta_icono("ico")
    try:
        if ruta_png is not None:
            foto = tk.PhotoImage(file=str(ruta_png))
            raiz._icono_conxml = foto
            raiz.wm_iconbitmap()
            raiz.iconphoto(True, foto)
            return
        if ruta_ico is not None:
            raiz.wm_iconbitmap(str(ruta_ico))
            raiz.tk.call("wm", "iconbitmap", raiz._w, "-default", str(ruta_ico))
    except tk.TclError:
        pass


class ConXmlApp(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, cliente_actual: str | None = None) -> None:
        super().__init__(master, fg_color=th.FONDO, corner_radius=0)
        self.master = master
        self.db_path = Config().db_path
        self._cola: queue.Queue = queue.Queue()
        self._ocupada = False
        self._detalles_visibles = True
        # Estado adaptable (no recrea tablas ni pierde selección/datos).
        self._ancho_compacto = False
        self._alto_compacto = False
        self._registro_oculto_auto = False
        self._resize_after: str | None = None
        self._sidebar_visible = True
        self.cliente_actual: str | None = cliente_actual

        master.title("ConXml — Gestor CFDI")
        try:
            master.geometry(resp.geometria_inicial(master))
        except Exception:
            master.geometry("1020x680")
        escala = resp.escalado_widget(master, ventana=True)
        master.minsize(min(resp.MIN_ANCHO, max(1, int(master.winfo_screenwidth() / escala - 40))),
                       min(resp.MIN_ALTO, max(1, int(master.winfo_screenheight() / escala - 60))))
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)
        self.grid(sticky="nsew", padx=0, pady=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Panel lateral oscuro (Sidebar)
        self._panel_lateral = ctk.CTkFrame(
            self,
            width=resp.ANCHO_SIDEBAR,
            fg_color=th.FONDO_SIDEBAR,
            corner_radius=0,
            border_width=0,
        )
        self._panel_lateral.grid(row=0, column=0, sticky="ns", rowspan=2)
        self._panel_lateral.grid_propagate(False)

        ctk.CTkLabel(
            self._panel_lateral, text="CONXML",
            text_color=th.SIDEBAR_TEXTO_ACTIVO,
            font=(th.FUENTE, th.TAM_H1, "bold"),
        ).pack(anchor="w", padx=16, pady=(24, 4))
        self._lbl_subtitulo = ctk.CTkLabel(
            self._panel_lateral, text="Gestor CFDI del despacho",
            text_color=th.SIDEBAR_TEXTO,
            font=(th.FUENTE, th.TAM_NOTA),
        )
        self._lbl_subtitulo.pack(anchor="w", padx=16, pady=(0, 20))

        self._marco_cliente = ctk.CTkFrame(
            self._panel_lateral, fg_color=th.SIDEBAR_HOVER, corner_radius=6
        )
        self._marco_cliente.pack(fill="x", padx=10, pady=(0, 14))
        ctk.CTkLabel(
            self._marco_cliente, text="CLIENTE ACTIVO", text_color=th.SIDEBAR_TEXTO,
            font=(th.FUENTE, 9, "bold"), anchor="w",
        ).pack(anchor="w", padx=10, pady=(7, 0))
        self._lbl_cliente = ctk.CTkLabel(
            self._marco_cliente, text="Selecciona un cliente",
            text_color=th.SIDEBAR_TEXTO_ACTIVO, font=(th.FUENTE, th.TAM_NOTA, "bold"),
            anchor="w", justify="left", wraplength=190,
        )
        self._lbl_cliente.pack(anchor="w", fill="x", padx=10, pady=(1, 8))

        # Menú de navegación sin frames intermedios
        self._nav = ctk.CTkFrame(self._panel_lateral, fg_color="transparent")
        self._nav.pack(fill="x", padx=4)
        self._nav.columnconfigure(0, minsize=4)
        self._nav.columnconfigure(1, weight=1)

        self._botones: dict[str, ctk.CTkButton] = {}
        self._indicadores: dict[str, ctk.CTkFrame] = {}

        # Botón Resumen
        resumen_indicator = ctk.CTkFrame(
            self._nav, width=4, height=32, fg_color="transparent", corner_radius=2
        )
        resumen_indicator.grid(row=0, column=0, sticky="ns", padx=(4, 0), pady=1)

        boton_resumen = self._crear_boton_nav(
            self._nav, "📊 Resumen", lambda: self.navegar("resumen")
        )
        boton_resumen.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=1)
        self._botones["resumen"] = boton_resumen
        self._indicadores["resumen"] = resumen_indicator

        boveda_indicator = ctk.CTkFrame(
            self._nav, width=4, height=32, fg_color="transparent", corner_radius=2
        )
        boveda_indicator.grid(row=1, column=0, sticky="ns", padx=(4, 0), pady=1)
        boton_boveda = self._crear_boton_nav(self._nav, "🗄️ Bóveda", lambda: self.navegar("boveda"))
        boton_boveda.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=1)
        self._botones["boveda"] = boton_boveda
        self._indicadores["boveda"] = boveda_indicator

        self._grupos: dict[str, dict] = {}
        self._grupo_de: dict[str, str] = {}
        fila = 2
        for clave_grupo, titulo, hijos in SECCIONES:
            boton_grupo = ctk.CTkButton(
                self._nav,
                text=f"▾ {titulo}",
                command=lambda g=clave_grupo: self._alternar_grupo(g),
                fg_color="transparent",
                hover_color=th.SIDEBAR_HOVER,
                text_color=th.SIDEBAR_TEXTO,
                anchor="w",
                corner_radius=th.RADIO_GRUPO,
                font=(th.FUENTE, th.TAM_NOTA, "bold"),
                height=28,
            )
            boton_grupo.grid(row=fila, column=0, columnspan=2, sticky="ew", padx=4, pady=(12, 2))
            fila += 1

            for clave, texto in hijos:
                indicator = ctk.CTkFrame(
                    self._nav, width=4, height=32, fg_color="transparent", corner_radius=2
                )
                indicator.grid(row=fila, column=0, sticky="ns", padx=(4, 0), pady=1)

                comando = self.cambiar_cliente if clave == "clientes" else lambda c=clave: self.navegar(c)
                sub = self._crear_boton_nav(self._nav, texto, comando)
                sub.grid(row=fila, column=1, sticky="ew", padx=(0, 6), pady=1)

                self._botones[clave] = sub
                self._indicadores[clave] = indicator
                self._grupo_de[clave] = clave_grupo
                fila += 1

            self._grupos[clave_grupo] = {
                "boton": boton_grupo,
                "hijos": [c for c, _ in hijos],
                "abierto": True,
                "titulo": titulo,
            }

        # Información de Base de Datos en el pie del Sidebar
        marco_bd = ctk.CTkFrame(self._panel_lateral, fg_color="transparent")
        marco_bd.pack(fill="x", side="bottom", padx=16, pady=16)
        self._marco_bd = marco_bd
        self._lbl_db_titulo = ctk.CTkLabel(
            marco_bd, text="Carpeta de datos",
            text_color=th.SIDEBAR_TEXTO, font=(th.FUENTE, th.TAM_NOTA),
        )
        self._lbl_db_titulo.pack(anchor="w")
        ruta = str(self.db_path.parent)
        self._lbl_db_ruta = ctk.CTkLabel(
            marco_bd, text=ruta, text_color=th.SIDEBAR_TEXTO,
            font=(th.FUENTE, th.TAM_NOTA), wraplength=200, justify="left",
        )
        self._lbl_db_ruta.pack(anchor="w", pady=(2, 0))

        # Área de contenido
        self._contenido = ctk.CTkFrame(self, fg_color=th.FONDO, corner_radius=0)
        self._contenido.grid(row=0, column=1, sticky="nsew")

        self._pantallas: dict[str, ctk.CTkFrame | tk.Frame] = {}
        self._pantallas["clientes"] = PantallaClientes(self._contenido, self)
        self._pantallas["resumen"] = PantallaResumen(self._contenido, self)
        self._pantallas["boveda"] = PantallaBoveda(self._contenido, self)
        self._pantallas["descargas"] = PantallaDescargas(self._contenido, self)
        self._pantallas["admin40"] = PantallaAdministracion(self._contenido, self, modo=MODO_CFDI40)
        self._pantallas["pagos"] = PantallaAdministracion(self._contenido, self, modo=MODO_PAGOS)
        self._pantallas["nomina"] = PantallaAdministracion(self._contenido, self, modo=MODO_NOMINA)
        self._pantallas["ajustes"] = PantallaAjustes(self._contenido, self)
        # La pantalla inicial activa se define al llamar a navegar("resumen")

        # Control flotante para recuperar el menú aunque esté oculto.
        self._btn_sidebar = ctk.CTkButton(
            self._contenido,
            text="☰ Menú",
            width=76,
            height=30,
            fg_color=th.FONDO_TARJETA,
            hover_color=th.PRIMARIO_FONDO,
            text_color=th.TEXTO_SECUNDARIO,
            border_width=1,
            border_color=th.BORDE,
            corner_radius=5,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
            command=self.alternar_sidebar,
        )
        self._btn_sidebar.place(x=4, y=4)

        # Consola de Registro inferior (ocultable con "Ocultar detalles")
        self._barra = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self._barra.grid(row=1, column=1, sticky="ew", padx=24, pady=(0, 16))

        cabecera_barra = ctk.CTkFrame(self._barra, fg_color="transparent")
        cabecera_barra.pack(side="top", fill="x", pady=(0, 6))

        self._lbl_registro = ctk.CTkLabel(
            cabecera_barra, text="Registro de actividad",
            text_color=th.TEXTO_SECUNDARIO, font=(th.FUENTE, th.TAM_NOTA),
        )
        self._lbl_registro.pack(side="left")

        self._btn_detalles = ctk.CTkButton(
            cabecera_barra, text="Ocultar detalles  ▾", width=160, height=26,
            fg_color="transparent", hover_color=th.FONDO_ENTRADA,
            text_color=th.TEXTO_SECUNDARIO, corner_radius=th.RADIO_GRUPO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
            command=self.alternar_detalles,
        )
        self._btn_detalles.pack(side="right")

        self.marco_consola = PanelCard(
            self._barra,
            fondo=th.FONDO_TARJETA,
            border_width=1,
            border_color=th.BORDE,
            corner_radius=th.RADIO_PANEL,
        )
        self.marco_consola.pack(side="top", fill="both", expand=True)

        self._registro = scrolledtext.ScrolledText(
            self.marco_consola, height=5, wrap="word", state="disabled",
            background=th.FONDO_ENTRADA, foreground=th.TEXTO,
            insertbackground=th.TEXTO, font=(th.FUENTE_MONO, 9),
            bd=0, highlightthickness=0
        )
        self._registro.pack(fill="both", expand=True, padx=8, pady=6)

        self._registro.tag_configure("comando", foreground=th.PRIMARIO, font=(th.FUENTE_MONO, 9, "bold"))
        self._registro.tag_configure("error", foreground=th.ROJO)
        self._registro.tag_configure("detalle", foreground=th.TEXTO_SECUNDARIO)

        master.protocol("WM_DELETE_WINDOW", self._al_cerrar)
        self.after(80, self._procesar_cola)
        self._pantalla_actual: ctk.CTkFrame | tk.Frame | None = None
        self.navegar("resumen" if self.cliente_actual else "clientes", primero=True)
        if self.cliente_actual:
            inicializar_boveda(Config(), self.cliente_actual)
        self._actualizar_cliente_sidebar()
        # Adaptación al tamaño de ventana: debounce + filtrado de hijos.
        try:
            master.bind("<Configure>", self._al_configurar_ventana, add="+")
        except Exception:
            pass
        self.after(250, self._aplicar_responsive_inicial)

    def _crear_boton_nav(self, parent, texto: str, comando) -> ctk.CTkButton:
        boton = ctk.CTkButton(
            parent,
            text=texto,
            command=comando,
            fg_color="transparent",
            hover_color=th.SIDEBAR_HOVER,
            text_color=th.SIDEBAR_TEXTO,
            anchor="w",
            corner_radius=th.RADIO_GRUPO,
            font=(th.FUENTE, th.TAM_BODY),
            height=32,
        )
        return boton

    def _alternar_grupo(self, clave_grupo: str) -> None:
        grupo = self._grupos[clave_grupo]
        grupo["abierto"] = not grupo["abierto"]
        for clave in grupo["hijos"]:
            if grupo["abierto"]:
                self._botones[clave].grid()
                self._indicadores[clave].grid()
            else:
                self._botones[clave].grid_remove()
                self._indicadores[clave].grid_remove()
        titulo = self._titulo_grupo(clave_grupo)
        grupo["boton"].configure(
            text=f"{'▾' if grupo['abierto'] else '▸'} {titulo}"
        )

    def _expandir_grupo(self, clave_grupo: str) -> None:
        grupo = self._grupos[clave_grupo]
        if not grupo["abierto"]:
            grupo["abierto"] = True
            for clave in grupo["hijos"]:
                self._botones[clave].grid()
                self._indicadores[clave].grid()
            grupo["boton"].configure(text=f"▾ {self._titulo_grupo(clave_grupo)}")

    def _titulo_grupo(self, clave_grupo: str) -> str:
        base = TITULO_GRUPO_COMPLETO.get(clave_grupo, clave_grupo)
        if self._ancho_compacto:
            return TITULO_GRUPO_BREVE.get(clave_grupo, base)
        return base

    def navegar(self, clave: str, primero: bool = False) -> None:
        if clave in self._grupo_de:
            self._expandir_grupo(self._grupo_de[clave])

        for k, boton in self._botones.items():
            boton.configure(
                fg_color="transparent", text_color=th.SIDEBAR_TEXTO,
                font=(th.FUENTE, th.TAM_BODY),
            )
            if k in self._indicadores:
                self._indicadores[k].configure(fg_color="transparent")

        if clave in self._botones:
            self._botones[clave].configure(
                fg_color=th.SIDEBAR_HOVER, text_color=th.SIDEBAR_TEXTO_ACTIVO,
                font=(th.FUENTE, th.TAM_BODY, "bold"),
            )
            if clave in self._indicadores:
                self._indicadores[clave].configure(fg_color=th.SIDEBAR_ACENTO)

        for p in self._pantallas.values():
            p.place_forget()
        self._pantalla_actual = self._pantallas[clave]
        self._pantalla_actual.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._pantalla_actual.tkraise()
        if hasattr(self._pantalla_actual, "al_mostrar"):
            self._pantalla_actual.al_mostrar()
        if hasattr(self._pantalla_actual, "al_alternar_detalles"):
            self._pantalla_actual.al_alternar_detalles(self._detalles_visibles)
        # La pantalla usa tkraise(); volver a elevar el control mantiene
        # accesible el botón de menú en todas las vistas.
        try:
            self._btn_sidebar.lift()
        except Exception:
            pass

    def seleccionar_cliente(self, clave: str) -> None:
        """Fija el cliente de trabajo y entra al resumen principal."""
        self.cliente_actual = clave
        inicializar_boveda(Config(), clave)
        self._actualizar_cliente_sidebar()
        self.navegar("resumen")

    def _actualizar_cliente_sidebar(self) -> None:
        texto = self.cliente_actual or "Selecciona un cliente"
        if self.cliente_actual:
            try:
                with Catalogo(self.db_path) as catalogo:
                    cliente = catalogo.obtener_cliente(self.cliente_actual)
                if cliente:
                    texto = f"{cliente['nombre']}\n{cliente['clave']}"
            except Exception:
                pass
        try:
            self._lbl_cliente.configure(text=texto)
        except Exception:
            pass

    def cambiar_cliente(self) -> None:
        self._selector_clientes = _mostrar_selector_clientes(
            self.master,
            self.seleccionar_cliente,
            self.db_path,
        )

    @property
    def detalles_visibles(self) -> bool:
        return self._detalles_visibles

    @property
    def sidebar_compacto(self) -> bool:
        return self._ancho_compacto

    @property
    def baja_altura(self) -> bool:
        return self._alto_compacto

    @property
    def ancho_sidebar(self) -> int:
        try:
            return int(self._panel_lateral.cget("width"))
        except Exception:
            return resp.ANCHO_SIDEBAR if not self._ancho_compacto else resp.ANCHO_SIDEBAR_COMPACTO

    @property
    def sidebar_visible(self) -> bool:
        return self._sidebar_visible

    def alternar_sidebar(self) -> None:
        """Oculta o muestra el menú lateral sin alterar la pantalla activa."""
        self._sidebar_visible = not self._sidebar_visible
        try:
            if self._sidebar_visible:
                self.columnconfigure(0, weight=0, minsize=0)
                self._panel_lateral.grid()
            else:
                self.columnconfigure(0, weight=0, minsize=0)
                self._panel_lateral.grid_remove()
            self.after_idle(self._aplicar_responsive_inicial)
        except Exception:
            self._sidebar_visible = not self._sidebar_visible

    def alternar_detalles(self) -> None:
        self._registro_oculto_auto = False
        self.mostrar_detalles(not self._detalles_visibles)

    def mostrar_detalles(self, visible: bool, forzar: bool = False) -> None:
        """Muestra/oculta el panel de detalles (resumen de operación + registro)."""
        if not forzar and visible == self._detalles_visibles:
            return
        # Llamada explícita: el usuario (o la operación en altura normal)
        # toma el control; se limpia la marca de auto-ocultado.
        self._registro_oculto_auto = False
        self._detalles_visibles = visible
        self._btn_detalles.configure(
            text="Ocultar detalles  ▾" if visible else "Mostrar detalles  ▸"
        )
        if visible:
            self.marco_consola.pack(side="top", fill="both", expand=True)
            self._lbl_registro.pack(side="left")
        else:
            self.marco_consola.pack_forget()
            self._lbl_registro.pack_forget()
        for pantalla in self._pantallas.values():
            if hasattr(pantalla, "al_alternar_detalles"):
                pantalla.al_alternar_detalles(visible)

    # ── Interfaz adaptable ──────────────────────────────────────────────

    def _al_configurar_ventana(self, event) -> None:
        # Filtrar eventos de hijos: solo la ventana raíz redimensiona el layout.
        if getattr(event, "widget", None) is not self.master:
            return
        if self._resize_after is not None:
            try:
                self.after_cancel(self._resize_after)
            except Exception:
                pass
        try:
            self._resize_after = self.after(resp.RETARDO_DEBOUNCE_MS, self._aplicar_responsive_inicial)
        except Exception:
            self._resize_after = None

    def _aplicar_responsive_inicial(self) -> None:
        self._resize_after = None
        try:
            escala = resp.escalado_widget(self.master)
            ancho = int(self.master.winfo_width() / escala)
            alto = int(self.master.winfo_height() / escala)
        except Exception:
            return
        # Al arrancar, winfo puede devolver 1x1 antes del primer layout.
        if ancho <= 1 or alto <= 1:
            try:
                self.after(250, self._aplicar_responsive_inicial)
            except Exception:
                pass
            return
        self.aplicar_responsive(ancho, alto)

    def aplicar_responsive(self, ancho: int, alto: int) -> None:
        """Adapta sidebar, registro y totales sin recrear tablas ni perder datos."""
        try:
            ancho = int(ancho)
            alto = int(alto)
        except Exception:
            return
        estrecha = resp.debe_usar_sidebar_compacto(ancho)
        baja = resp.debe_usar_modo_baja_altura(alto)
        if estrecha != self._ancho_compacto:
            self._ancho_compacto = estrecha
            self._aplicar_sidebar(estrecha)
        if baja != self._alto_compacto:
            self._alto_compacto = baja
            self._aplicar_modo_altura(baja)
        # Propagar modo compacto a las pantallas (márgenes, selector REP, etc.)
        for pantalla in self._pantallas.values():
            aplicar = getattr(pantalla, "aplicar_modo_compacto", None)
            if callable(aplicar):
                try:
                    aplicar(self._ancho_compacto, self._alto_compacto)
                except Exception:
                    pass

    def _aplicar_sidebar(self, compacto: bool) -> None:
        ancho = resp.ANCHO_SIDEBAR_COMPACTO if compacto else resp.ANCHO_SIDEBAR
        try:
            self._panel_lateral.configure(width=ancho)
        except Exception:
            pass
        for clave, boton in self._botones.items():
            texto = (TEXTO_NAV_BREVE if compacto else TEXTO_NAV_COMPLETO).get(clave)
            if texto is not None:
                try:
                    boton.configure(text=texto)
                except Exception:
                    pass
        for clave_grupo, grupo in self._grupos.items():
            titulo = (TITULO_GRUPO_BREVE if compacto else TITULO_GRUPO_COMPLETO).get(
                clave_grupo, grupo.get("titulo", clave_grupo)
            )
            marca = "▾" if grupo.get("abierto", True) else "▸"
            try:
                grupo["boton"].configure(text=f"{marca} {titulo}")
            except Exception:
                pass
        try:
            if compacto:
                self._lbl_subtitulo.pack_forget()
                self._marco_cliente.pack_forget()
                self._lbl_db_ruta.configure(wraplength=ancho - 32)
            else:
                self._lbl_subtitulo.pack(anchor="w", padx=16, pady=(0, 20))
                self._marco_cliente.pack(fill="x", padx=10, pady=(0, 14), before=self._nav)
                self._lbl_db_ruta.configure(wraplength=200)
        except Exception:
            pass

    def _aplicar_modo_altura(self, baja: bool) -> None:
        if baja:
            # Poca altura: ocultar el registro para dar prioridad a la tabla.
            # Se marca como auto-ocultado para restaurarlo al ampliar.
            if self._detalles_visibles:
                self._registro_oculto_auto = False
                self.mostrar_detalles(False)
                self._registro_oculto_auto = True
        else:
            if self._registro_oculto_auto:
                self._registro_oculto_auto = False
                self.mostrar_detalles(True)

    def actualizar_resumen(self) -> None:
        self._pantallas["resumen"].actualizar_metricas()

    def registro(self, texto: str) -> None:
        self._registro.configure(state="normal")
        if texto.startswith("==>"):
            self._registro.insert("end", texto + "\n", "comando")
        elif (texto.startswith("ERROR:") or "traceback" in texto.lower()
              or "exception" in texto.lower() or "falló" in texto.lower()):
            self._registro.insert("end", texto + "\n", "error")
        elif texto.startswith("  "):
            self._registro.insert("end", texto + "\n", "detalle")
        else:
            self._registro.insert("end", texto + "\n")
        self._registro.see("end")
        self._registro.configure(state="disabled")

    def ejecutar(self, fn, al_terminar, texto: str, con_progreso: bool = False) -> bool:
        if self._ocupada:
            messagebox.showinfo(
                "Operación en curso",
                "Espera a que termine la operación actual antes de lanzar otra.",
                parent=self,
            )
            return False
        self._ocupada = True
        for pantalla in self._pantallas.values():
            for boton in getattr(pantalla, "botones", []):
                boton.configure(state="disabled")
        self.registro(f"==> {texto}")

        def trabajo() -> None:
            try:
                if con_progreso:
                    progreso = lambda a, t: self._cola.put(("progreso", a, t))
                    resultado = fn(progreso)
                else:
                    resultado = fn()
            except Exception:
                self._cola.put(("error", traceback.format_exc()))
                return
            self._cola.put(("listo", al_terminar, resultado))

        threading.Thread(target=trabajo, daemon=True).start()
        return True

    def _procesar_cola(self) -> None:
        try:
            while True:
                item = self._cola.get_nowait()
                tipo = item[0]
                if tipo == "progreso":
                    pantalla = self._pantalla_actual
                    if pantalla is not None and hasattr(pantalla, "on_progreso"):
                        pantalla.on_progreso(item[1], item[2])
                elif tipo == "error":
                    self._terminar_operacion()
                    self.registro("ERROR:")
                    for linea in item[1].rstrip().splitlines():
                        self.registro(f"  {linea}")
                    messagebox.showerror(
                        "Error", "Falló la operación. Revisa el detalle en el registro.",
                        parent=self,
                    )
                elif tipo == "listo":
                    self._terminar_operacion()
                    _, al_terminar, resultado = item
                    al_terminar(resultado)
        except queue.Empty:
            pass
        self.after(80, self._procesar_cola)

    def _terminar_operacion(self) -> None:
        self._ocupada = False
        for pantalla in self._pantallas.values():
            for boton in getattr(pantalla, "botones", []):
                boton.configure(state="normal")

    def _al_cerrar(self) -> None:
        if self._ocupada:
            messagebox.showwarning(
                "Operación en curso",
                "Hay una operación en curso. Espera a que termine antes de cerrar.",
                parent=self,
            )
            return
        self.master.destroy()


def main() -> None:
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    th.configurar_ctk()
    raiz = ctk.CTk()
    raiz.configure(fg_color=th.FONDO)
    _aplicar_icono(raiz)
    # La selección de cliente es la primera ventana. La ventana principal se
    # construye después de seleccionar para que siempre arranque con contexto.
    raiz.withdraw()

    def abrir_programa(clave: str) -> None:
        raiz.deiconify()
        raiz._conxml_app = ConXmlApp(raiz, cliente_actual=clave)

    selector = _mostrar_selector_clientes(
        raiz,
        abrir_programa,
        Config().db_path,
        on_close=raiz.destroy,
    )
    raiz._selector_clientes = selector
    raiz.mainloop()


def _mostrar_selector_clientes(parent, on_selected, db_path, on_close=None):
    """Abre el catálogo de clientes como ventana modal reutilizable."""
    selector = ctk.CTkToplevel(parent)
    selector.title("ConXml — Seleccionar cliente")
    selector.geometry("900x650")
    selector.minsize(760, 520)
    selector.configure(fg_color=th.FONDO)
    _aplicar_icono(selector)
    selector.transient(parent)

    cerrado = False

    def cerrar() -> None:
        nonlocal cerrado
        if cerrado:
            return
        cerrado = True
        try:
            selector.grab_release()
        except tk.TclError:
            pass
        try:
            selector.destroy()
        finally:
            if on_close is not None:
                on_close()

    def seleccionar(clave: str) -> None:
        cerrar_sin_callback()
        on_selected(clave)

    def cerrar_sin_callback() -> None:
        nonlocal cerrado
        if cerrado:
            return
        cerrado = True
        try:
            selector.grab_release()
        except tk.TclError:
            pass
        selector.destroy()

    selector.protocol("WM_DELETE_WINDOW", cerrar)
    pantalla = PantallaClientes(selector, app=None, on_selected=seleccionar, db_path=db_path)
    pantalla.pack(fill="both", expand=True)
    pantalla.al_mostrar()
    try:
        # En macOS, un Toplevel cuyo padre está oculto puede nacer como
        # ``withdrawn``; mostrarlo explícitamente evita un proceso sin ventana.
        selector.deiconify()
        selector.grab_set()
        selector.focus_force()
    except tk.TclError:
        pass
    return selector
