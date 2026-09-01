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

from conxml.config import Config
from conxml.ui import theme as th
from conxml.ui.pantalla_admin import (
    MODO_CFDI40,
    MODO_NOMINA,
    MODO_PAGOS,
    PantallaAdministracion,
)
from conxml.ui.pantalla_ajustes import PantallaAjustes
from conxml.ui.pantalla_resumen import PantallaResumen
from conxml.ui.widgets import PanelCard

SECCIONES = [
    ("admin_xml", "ADMINISTRACIÓN XML", [
        ("admin40", "📄 XML 4.0 (Ingr/Egr/Tras)"),
        ("pagos", "💸 Conciliación de Pagos"),
        ("nomina", "👔 Recibos de Nómina"),
    ]),
    ("sistema", "SISTEMA", [
        ("ajustes", "⚙️ Configuración y Ajustes"),
    ]),
]

NOMBRE_ICONO = "logo_conxml"


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
    def __init__(self, master: ctk.CTk) -> None:
        super().__init__(master, fg_color=th.FONDO, corner_radius=0)
        self.master = master
        self.db_path = Config().db_path
        self._cola: queue.Queue = queue.Queue()
        self._ocupada = False
        self._detalles_visibles = True

        master.title("ConXml — Gestor CFDI")
        master.geometry("1020x680")
        master.minsize(860, 580)
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)
        self.grid(sticky="nsew", padx=0, pady=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Panel lateral oscuro (Sidebar)
        self._panel_lateral = ctk.CTkFrame(
            self,
            width=240,
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
        ctk.CTkLabel(
            self._panel_lateral, text="Gestor CFDI del despacho",
            text_color=th.SIDEBAR_TEXTO,
            font=(th.FUENTE, th.TAM_NOTA),
        ).pack(anchor="w", padx=16, pady=(0, 20))

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

        self._grupos: dict[str, dict] = {}
        self._grupo_de: dict[str, str] = {}
        fila = 1
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

                sub = self._crear_boton_nav(self._nav, texto, lambda c=clave: self.navegar(c))
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
        ctk.CTkLabel(
            marco_bd, text="Carpeta de datos",
            text_color=th.SIDEBAR_TEXTO, font=(th.FUENTE, th.TAM_NOTA),
        ).pack(anchor="w")
        ruta = str(self.db_path.parent)
        ctk.CTkLabel(
            marco_bd, text=ruta, text_color=th.SIDEBAR_TEXTO,
            font=(th.FUENTE, th.TAM_NOTA), wraplength=200, justify="left",
        ).pack(anchor="w", pady=(2, 0))

        # Área de contenido
        self._contenido = ctk.CTkFrame(self, fg_color=th.FONDO, corner_radius=0)
        self._contenido.grid(row=0, column=1, sticky="nsew")

        self._pantallas: dict[str, ctk.CTkFrame | tk.Frame] = {}
        self._pantallas["resumen"] = PantallaResumen(self._contenido, self)
        self._pantallas["admin40"] = PantallaAdministracion(self._contenido, self, modo=MODO_CFDI40)
        self._pantallas["pagos"] = PantallaAdministracion(self._contenido, self, modo=MODO_PAGOS)
        self._pantallas["nomina"] = PantallaAdministracion(self._contenido, self, modo=MODO_NOMINA)
        self._pantallas["ajustes"] = PantallaAjustes(self._contenido, self)
        # La pantalla inicial activa se define al llamar a navegar("resumen")

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
        self.navegar("resumen", primero=True)

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
        grupo["boton"].configure(
            text=f"{'▾' if grupo['abierto'] else '▸'} {grupo['titulo']}"
        )

    def _expandir_grupo(self, clave_grupo: str) -> None:
        grupo = self._grupos[clave_grupo]
        if not grupo["abierto"]:
            grupo["abierto"] = True
            for clave in grupo["hijos"]:
                self._botones[clave].grid()
                self._indicadores[clave].grid()
            grupo["boton"].configure(text=f"▾ {grupo['titulo']}")

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

    @property
    def detalles_visibles(self) -> bool:
        return self._detalles_visibles

    def alternar_detalles(self) -> None:
        self.mostrar_detalles(not self._detalles_visibles)

    def mostrar_detalles(self, visible: bool, forzar: bool = False) -> None:
        """Muestra/oculta el panel de detalles (resumen de operación + registro)."""
        if not forzar and visible == self._detalles_visibles:
            return
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
    ConXmlApp(raiz)
    raiz.mainloop()
