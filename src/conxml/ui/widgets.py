"""Componentes reutilizables de la interfaz ConXml sobre CustomTkinter (Fluent Empresarial)."""
from __future__ import annotations

import customtkinter as ctk

from conxml.ui import theme as th

PASO = th.PASO


class PanelCard(ctk.CTkFrame):
    """Panel contenedor con estilo Fluent: fondo blanco sólido, borde de 1px."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        *,
        fondo: str = th.FONDO_TARJETA,
        border_width: int = 1,
        border_color: str = th.BORDE,
        corner_radius: int = th.RADIO_TARJETA,
        **kwargs,
    ) -> None:
        super().__init__(
            parent,
            fg_color=fondo,
            border_width=border_width,
            border_color=border_color,
            corner_radius=corner_radius,
            **kwargs,
        )


# Alias para retrocompatibilidad
Card = PanelCard
PanelVidrio = PanelCard


class BotonPrimario(ctk.CTkButton):
    """Botón primario sólido estilo Fluent."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        texto: str,
        comando=None,
        **kwargs,
    ) -> None:
        super().__init__(
            parent,
            text=texto,
            command=comando,
            fg_color=th.PRIMARIO,
            hover_color=th.PRIMARIO_HOVER,
            text_color="#FFFFFF",
            border_width=0,
            height=36,
            corner_radius=th.RADIO_BOTON,
            font=(th.FUENTE, th.TAM_BODY, "bold"),
            **kwargs,
        )


class BotonSecundario(ctk.CTkButton):
    """Botón secundario outline estilo Fluent."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        texto: str,
        comando=None,
        **kwargs,
    ) -> None:
        super().__init__(
            parent,
            text=texto,
            command=comando,
            fg_color=th.FONDO_TARJETA,
            hover_color=th.PRIMARIO_FONDO,
            text_color=th.PRIMARIO,
            border_width=1,
            border_color=th.BORDE,
            height=36,
            corner_radius=th.RADIO_BOTON,
            font=(th.FUENTE, th.TAM_BODY),
            **kwargs,
        )


class BotonVidrio(BotonPrimario):
    """Alias para retrocompatibilidad."""
    pass


class Insignia(ctk.CTkLabel):
    """Insignia / Badge cápsula."""

    def __init__(self, parent: ctk.CTkFrame, texto: str, tono: str = "gris") -> None:
        color, fondo = th.TONOS[tono]
        super().__init__(
            parent,
            text=texto,
            fg_color=fondo,
            text_color=color,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
            corner_radius=th.RADIO_BADGE,
            padx=10,
            pady=3,
        )


class Metrica(PanelCard):
    """Métrica KPI limpia sin place() ni imágenes decorativas de fondo."""

    def __init__(self, parent: ctk.CTkFrame, etiqueta: str, valor: str, tono: str = "azul") -> None:
        super().__init__(parent, height=72)
        color, _fondo = th.TONOS[tono]

        # Barra lateral de color de acento
        self.barra = ctk.CTkFrame(self, fg_color=color, width=3, height=10, corner_radius=0)
        self.barra.pack(side="left", fill="y")

        # Contenido
        self.contenido = ctk.CTkFrame(self, fg_color="transparent")
        self.contenido.pack(side="left", fill="both", expand=True, padx=14, pady=10)

        self.lbl_etiqueta = ctk.CTkLabel(
            self.contenido,
            text=etiqueta.upper(),
            text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA, "bold"),
            anchor="w",
        )
        self.lbl_etiqueta.pack(anchor="w", fill="x")

        self.lbl_valor = ctk.CTkLabel(
            self.contenido,
            text=valor,
            text_color=color,
            font=(th.FUENTE, th.TAM_H1, "bold"),
            anchor="w",
        )
        self.lbl_valor.pack(anchor="w", fill="x", pady=(2, 0))


class TarjetaAccion(PanelCard):
    """Tarjeta de acción con hover de borde sutil."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        titulo: str,
        descripcion: str,
        numero: str,
        comando=None,
        wraplength: int = 420,
    ) -> None:
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self._comando = comando

        self.contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.contenedor.grid(row=0, column=0, sticky="nsew", padx=16, pady=14)
        self.contenedor.columnconfigure(0, weight=1)

        self.cabecera = ctk.CTkFrame(self.contenedor, fg_color="transparent")
        self.cabecera.grid(row=0, column=0, sticky="ew")

        self.insignia = Insignia(self.cabecera, numero, tono="azul")
        self.insignia.pack(side="left")

        self.lbl_titulo = ctk.CTkLabel(
            self.cabecera,
            text=titulo,
            text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_H3, "bold"),
            anchor="w",
        )
        self.lbl_titulo.pack(side="left", padx=(10, 0))

        self.lbl_desc = ctk.CTkLabel(
            self.contenedor,
            text=descripcion,
            text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA),
            wraplength=wraplength,
            justify="left",
            anchor="w",
        )
        self.lbl_desc.grid(row=1, column=0, sticky="w", pady=(8, 0))

        self._boton = BotonSecundario(self.contenedor, "Ir →", comando)
        self._boton.grid(row=2, column=0, sticky="w", pady=(12, 0))

        self._vincular_events(self)

    def _vincular_events(self, widget) -> None:
        if widget is self._boton:
            return
        widget.bind("<Button-1>", lambda _e: self._disparar())
        widget.bind("<Enter>", lambda _e: self.configure(border_color=th.PRIMARIO), add="+")
        widget.bind("<Leave>", lambda _e: self.configure(border_color=th.BORDE), add="+")
        for hijo in widget.winfo_children():
            self._vincular_events(hijo)

    def _disparar(self) -> None:
        if self._comando is not None:
            self._comando()


class Encabezado(ctk.CTkFrame):
    """Encabezado de sección con título, subtítulo y separador sutil."""

    def __init__(self, parent: ctk.CTkFrame, titulo: str, subtitulo: str) -> None:
        super().__init__(parent, fg_color="transparent")
        ctk.CTkLabel(
            self, text=titulo, text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_H1, "bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            self, text=subtitulo, text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_BODY),
        ).pack(anchor="w", pady=(2, 0))
        sep = ctk.CTkFrame(self, height=1, fg_color=th.BORDE)
        sep.pack(fill="x", pady=(10, 0))


class FilaEtiquetada(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, etiqueta: str, widget, nota: str | None = None) -> None:
        super().__init__(parent, fg_color="transparent")
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=etiqueta, text_color=th.TEXTO, font=(th.FUENTE, th.TAM_BODY)).grid(
            row=0, column=0, sticky="w", padx=(0, 10), pady=5
        )
        widget.grid(row=0, column=1, sticky="ew", pady=5)
        if nota:
            ctk.CTkLabel(self, text=nota, text_color=th.TEXTO_SECUNDARIO,
                         font=(th.FUENTE, th.TAM_NOTA)).grid(
                row=1, column=0, columnspan=2, sticky="w", pady=(0, 4)
            )


class FilaArchivo(ctk.CTkFrame):
    def __init__(
        self,
        parent: ctk.CTkFrame,
        variable,
        comando,
        etiqueta: str,
        boton: str = "Examinar…",
        comando_secundario=None,
        boton_secundario: str = "➕ Añadir",
        placeholder_text: str = "",
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self.columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=etiqueta, text_color=th.TEXTO, font=(th.FUENTE, th.TAM_BODY)).grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )
        self.entrada = ctk.CTkEntry(
            self,
            textvariable=variable,
            placeholder_text=placeholder_text,
            corner_radius=th.RADIO_CAMPO,
            border_width=1,
            border_color=th.BORDE,
            fg_color=th.FONDO_ENTRADA,
            text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_BODY),
        )
        self.entrada.grid(row=0, column=1, sticky="ew")
        BotonSecundario(self, boton, comando).grid(row=0, column=2, padx=(8, 0))
        if comando_secundario is not None:
            BotonSecundario(self, boton_secundario, comando_secundario).grid(
                row=0, column=3, padx=(6, 0)
            )


class ResumenOperacion(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame) -> None:
        super().__init__(parent, fg_color="transparent", corner_radius=th.RADIO_TARJETA)

        self.contenedor = ctk.CTkFrame(self, fg_color="transparent")
        self.contenedor.pack(fill="both", expand=True, padx=12, pady=10)

        self._linea = ctk.CTkFrame(self.contenedor, fg_color="transparent")
        self._linea.pack(anchor="w", fill="x")

        self._etiqueta = ctk.CTkLabel(
            self._linea, text="", text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_BODY, "bold"),
        )
        self._etiqueta.pack(side="left")

        self._accion = None

        self._detalle = ctk.CTkLabel(
            self.contenedor, text="", text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA), wraplength=620, justify="left", anchor="w",
        )
        self._detalle.pack(anchor="w", pady=(4, 0))

    def vaciar(self) -> None:
        self.configure(fg_color="transparent", border_width=0)
        self._etiqueta.configure(text="", text_color=th.TEXTO)
        self._detalle.configure(text="", text_color=th.TEXTO_SECUNDARIO)
        self._quitar_accion()

    def _quitar_accion(self) -> None:
        if self._accion is not None:
            self._accion.destroy()
            self._accion = None

    def mostrar(self, texto: str, tono: str | None = None, detalle: str = "",
                accion: tuple[str, object] | None = None) -> None:
        self._quitar_accion()

        if tono:
            color, fondo = th.TONOS[tono]
            self.configure(fg_color=fondo, border_color=color, border_width=1)
            self._etiqueta.configure(text=texto, text_color=color)
            self._detalle.configure(text=detalle, text_color=th.TEXTO)
        else:
            self.configure(fg_color="transparent", border_width=0)
            self._etiqueta.configure(text=texto, text_color=th.TEXTO)
            self._detalle.configure(text=detalle, text_color=th.TEXTO_SECUNDARIO)

        if accion is not None:
            self._accion = BotonSecundario(self._linea, accion[0], accion[1])
            self._accion.pack(side="left", padx=(12, 0))
