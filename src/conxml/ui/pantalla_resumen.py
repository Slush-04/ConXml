"""Inicio del cliente: catálogo local, pendientes, accesos y ayuda contextual."""
from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from conxml.catalog.db import Catalogo
from conxml.ui import theme as th
from conxml.ui.responsive import escalado_widget
from conxml.ui.scroll import PaginaDesplazable
from conxml.ui.widgets import (
    BarraAdaptable, BotonPrimario, BotonSecundario, Card, Encabezado,
    Metrica, TarjetaAccion, texto_adaptable,
)

ACCIONES = [
    ("boveda", "Organizar XML", "Elige una carpeta o un periodo y carga los XML del cliente al catálogo."),
    ("descargas", "Descargar del SAT", "Solicita XML con la e.firma del cliente y recupera los paquetes disponibles."),
    ("admin40", "Revisar comprobantes", "Busca por UUID, RFC, serie o folio; abre PDF, consulta SAT y exporta Excel."),
    ("pagos", "Conciliar pagos", "Revisa complementos REP y exporta el detalle de pagos y documentos relacionados."),
    ("nomina", "Consultar nómina", "Consulta los recibos de nómina cargados y prepara su reporte en Excel."),
    ("ajustes", "Respaldos y ajustes", "Crea o restaura un respaldo local y configura tu espacio de trabajo."),
]

AYUDAS = [
    ("¿Cómo empiezo con este cliente?",
     "1. Abre Bóveda para elegir XML locales o Descargas SAT para solicitarlos.\n"
     "2. En Bóveda, elige el periodo y pulsa Cargar selección.\n"
     "3. Revisa los comprobantes, consulta su estatus y exporta el reporte que necesitas.", "boveda", "Ir a Bóveda"),
    ("¿Qué incluyen las cifras de este inicio?",
     "Incluyen todos los XML del catálogo local asociados al cliente activo, sin aplicar los filtros de otras pantallas. "
     "Los archivos que solo están en Bóveda todavía deben cargarse. El rango de fechas no garantiza que el periodo esté completo.", None, None),
    ("¿Qué significa el estatus SAT?",
     "Vigente, Cancelado y No Encontrado muestran la respuesta guardada de una consulta anterior. "
     "Sin validar indica que no hay un estatus guardado. Actualizar resumen vuelve a leer el catálogo; "
     "para consultar al SAT abre el módulo correspondiente y usa su acción de validación.", "admin40", "Ir a comprobantes"),
    ("¿Dónde obtengo Excel o PDF?",
     "En Comprobantes puedes exportar el listado a Excel y abrir el PDF con doble clic en una fila. "
     "Pagos y Nómina tienen sus propios reportes. Revisa los filtros de cada módulo antes de exportar.", "admin40", "Ver comprobantes"),
    ("¿Cómo protejo mi trabajo?",
     "En Ajustes puedes crear un respaldo local con clientes, catálogo, XML y preferencias. "
     "Guarda una copia en otra ubicación para poder recuperarlo si cambia o falla el equipo.", "ajustes", "Ir a respaldos"),
]


def _fecha(valor: str | None) -> str:
    if not valor:
        return "Sin registro"
    try:
        return datetime.fromisoformat(valor).strftime("%d/%m/%Y")
    except ValueError:
        return valor[:10]


class PantallaResumen(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.botones: list = []
        self._lectura = 0
        self._contenedor = PaginaDesplazable(self, fg_color="transparent")
        self._contenedor.pack(fill="both", expand=True, padx=16, pady=16)
        # La barra nativa evita el update_idletasks recursivo de CTkScrollbar
        # cuando se redistribuyen muchas tarjetas y etiquetas adaptables.
        barra_anterior = self._contenedor._scrollbar
        posicion_barra = barra_anterior.grid_info()
        barra_anterior.grid_remove()
        self._barra_scroll = ttk.Scrollbar(
            self._contenedor._parent_frame, orient="vertical",
            command=self._contenedor._parent_canvas.yview,
        )
        self._barra_scroll.grid(**posicion_barra)
        self._contenedor._parent_canvas.configure(yscrollcommand=self._barra_scroll.set)

        self._encabezado = Encabezado(
            self._contenedor, "Tu espacio de trabajo",
            "El catálogo del cliente, sus pendientes y las herramientas para continuar.",
        )
        self._encabezado.pack(fill="x")
        barra = BarraAdaptable(self._contenedor)
        barra.pack(fill="x", pady=(12, 8))
        self._btn_actualizar = barra.agregar(BotonSecundario(barra, "Actualizar resumen", self.actualizar_metricas))
        barra.agregar(BotonSecundario(barra, "Cambiar cliente", self.app.cambiar_cliente))
        self.botones.append(self._btn_actualizar)
        self._actualizado = self._texto(self._contenedor, "Selecciona un cliente para ver su catálogo.")
        self._actualizado.pack(fill="x", pady=(0, 12))

        self._metricas = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        self._metricas.pack(fill="x")
        self._tarjetas_metrica = [
            Metrica(self._metricas, etiqueta, "—", tono)
            for etiqueta, tono in (("Comprobantes", "azul"), ("Vigentes", "verde"),
                                   ("Cancelados", "rojo"), ("Sin validar", "ambar"))
        ]
        self._rejilla(self._metricas, self._tarjetas_metrica, maximo=4, minimo=170)

        self._seccion("Para continuar", "Acciones sugeridas según la información guardada.")
        self._estado = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        self._estado.pack(fill="x")
        self._seccion("Qué tienes cargado", "Cobertura del catálogo local de este cliente.")
        self._cobertura = Card(self._contenedor)
        self._cobertura.pack(fill="x")
        self._seccion("Herramientas de trabajo", "Entra directamente al módulo que necesitas.")
        self._acciones = ctk.CTkFrame(self._contenedor, fg_color="transparent")
        self._acciones.pack(fill="x")
        self._tarjetas_accion = [
            TarjetaAccion(self._acciones, titulo, descripcion, f"{i + 1:02}",
                          lambda c=clave: self.app.navegar(c))
            for i, (clave, titulo, descripcion) in enumerate(ACCIONES)
        ]
        self._rejilla(self._acciones, self._tarjetas_accion, maximo=3, minimo=290)
        self._seccion("Ayuda rápida", "Resuelve dudas sin salir de tu espacio de trabajo.")
        self._ayudas = []
        for pregunta, respuesta, destino, accion in AYUDAS:
            self._crear_ayuda(pregunta, respuesta, destino, accion)

    def _texto(self, padre, texto, *, destacado=False, color=None):
        etiqueta = ctk.CTkLabel(
            padre, text=texto, text_color=color or (th.TEXTO if destacado else th.TEXTO_SECUNDARIO),
            font=(th.FUENTE, th.TAM_H3 if destacado else th.TAM_BODY, "bold" if destacado else "normal"),
            anchor="w", justify="left", wraplength=500,
        )
        texto_adaptable(etiqueta, padre)
        return etiqueta

    def _seccion(self, titulo, descripcion):
        self._texto(self._contenedor, titulo, destacado=True).pack(fill="x", pady=(18, 0))
        self._texto(self._contenedor, descripcion).pack(fill="x", pady=(0, 8))

    def _rejilla(self, marco, tarjetas, *, maximo, minimo):
        columnas_previas = None

        def distribuir(event=None):
            nonlocal columnas_previas
            if event is not None and event.widget is not marco:
                return
            ancho = marco.winfo_width() / escalado_widget(marco)
            columnas = max(1, min(maximo, int(ancho // minimo)))
            if columnas == columnas_previas:
                return
            columnas_previas = columnas
            for col in range(maximo):
                marco.columnconfigure(col, weight=1 if col < columnas else 0,
                                      uniform="tarjetas" if col < columnas else "")
            for i, tarjeta in enumerate(tarjetas):
                tarjeta.grid(row=i // columnas, column=i % columnas, sticky="nsew",
                             padx=(0, 10 if i % columnas < columnas - 1 else 0), pady=(0, 10))

        tk.Misc.bind(marco, "<Configure>", distribuir, add="+")
        distribuir()

    def _crear_ayuda(self, pregunta, respuesta, destino, accion):
        tarjeta = Card(self._contenedor)
        tarjeta.pack(fill="x", pady=(0, 8))
        detalle = ctk.CTkFrame(tarjeta, fg_color="transparent")
        self._texto(detalle, respuesta).pack(fill="x")
        if destino:
            BotonSecundario(detalle, accion, lambda c=destino: self.app.navegar(c)).pack(anchor="w", pady=(10, 0))

        def alternar():
            abierto = bool(detalle.winfo_manager())
            if abierto:
                detalle.pack_forget()
            else:
                detalle.pack(fill="x", padx=16, pady=(0, 14))
            boton.configure(text=f"{'＋' if abierto else '−'}  {pregunta}")

        boton = ctk.CTkButton(
            tarjeta, text=f"＋  {pregunta}", command=alternar, anchor="w",
            fg_color="transparent", hover_color=th.PRIMARIO_FONDO, text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_BODY, "bold"), height=40,
        )
        boton.pack(fill="x", padx=8, pady=4)
        self._ayudas.append((boton, detalle))

    def aplicar_modo_compacto(self, ancho_compacto: bool, alto_compacto: bool) -> None:
        margen = 8 if ancho_compacto or alto_compacto else 16
        self._contenedor.pack(padx=margen, pady=margen)

    def al_mostrar(self) -> None:
        self.actualizar_metricas()

    def actualizar_metricas(self) -> None:
        self._lectura += 1
        lectura = self._lectura
        cliente = self.app.cliente_actual
        # Limpiar inmediatamente: nunca mostrar las cifras de otro cliente.
        if cliente != getattr(self, "_cliente_presentado", None):
            self._cliente_presentado = cliente
            self._encabezado._lbl_sub.configure(text=f"Cliente: {cliente}" if cliente else "Selecciona un cliente para empezar.")
            for tarjeta in self._tarjetas_metrica:
                tarjeta.lbl_valor.configure(text="—")
            for marco in (self._estado, self._cobertura):
                for hijo in marco.winfo_children():
                    hijo.destroy()
        if not cliente:
            self._actualizado.configure(text="Selecciona un cliente para ver su catálogo.")
            for hijo in self._estado.winfo_children():
                hijo.destroy()
            self._fila_accion("Elige tu cliente de trabajo", "Sus XML e indicadores aparecerán aquí.",
                              "Seleccionar cliente", comando=self.app.cambiar_cliente)
            return
        if getattr(self.app, "_ocupada", False):
            self._actualizado.configure(text="Hay una operación en curso. Actualiza el resumen cuando termine.")
            return
        self._actualizado.configure(text="Leyendo catálogo local…")

        def leer():
            with Catalogo(self.app.db_path) as catalogo:
                return catalogo.resumen_cliente(cliente)

        def presentar(datos):
            if lectura == self._lectura and cliente == self.app.cliente_actual:
                self._presentar(datos)

        def error(_exc):
            if lectura == self._lectura and cliente == self.app.cliente_actual:
                self._actualizado.configure(text="No se pudo leer el catálogo. Pulsa Actualizar resumen para reintentar.")

        self.app.ejecutar(leer, presentar, "Leyendo inicio del cliente", al_error=error)

    def _presentar(self, datos: dict) -> None:
        for marco in (self._estado, self._cobertura):
            for hijo in marco.winfo_children():
                hijo.destroy()
        cliente = datos.get("cliente")
        if cliente:
            self._encabezado._lbl_sub.configure(
                text=f"{cliente['nombre']} · {cliente['clave']} · RFC: {cliente['rfc'] or 'Sin registrar'}")
        self._actualizado.configure(text=f"Catálogo local · Todos los periodos · Actualizado a las {datetime.now():%H:%M:%S}")
        est = datos["estatus"]
        for tarjeta, valor in zip(self._tarjetas_metrica,
                                   (datos["total"], est["Vigente"], est["Cancelado"], est["Sin validar"])):
            tarjeta.lbl_valor.configure(text=f"{valor:,}")
        self._presentar_estado(datos)
        tipos = datos.get("tipos", {})
        lineas = [
            f"Fechas de emisión: {_fecha(datos.get('desde'))} al {_fecha(datos.get('hasta'))}" if datos["total"] else "Aún no hay XML cargados para este cliente.",
            "   ·   ".join(f"{nombre}: {tipos.get(tipo, 0):,}" for tipo, nombre in
                           (("I", "Ingresos"), ("E", "Egresos"), ("P", "Pagos"), ("N", "Nómina"), ("T", "Traslados"))),
            f"Última consulta SAT guardada: {_fecha(datos.get('ultima_validacion'))} · No encontrados: {est['No Encontrado']:,}",
            "Estas cifras no confirman que un periodo esté completo. Los estatus muestran la última respuesta guardada por XML.",
        ]
        for i, linea in enumerate(lineas):
            self._texto(self._cobertura, linea, destacado=i == 0).pack(fill="x", padx=16, pady=(10 if i == 0 else 2, 12 if i == len(lineas) - 1 else 0))

    def _fila_accion(self, titulo, descripcion, accion, destino=None, *, tono="azul", comando=None):
        tarjeta = Card(self._estado, fondo=th.TONOS[tono][1], border_color=th.TONOS[tono][1])
        tarjeta.pack(fill="x", pady=(0, 8))
        self._texto(tarjeta, titulo, destacado=True, color=th.TONOS[tono][0]).pack(fill="x", padx=16, pady=(12, 0))
        self._texto(tarjeta, descripcion).pack(fill="x", padx=16, pady=(2, 8))
        if accion:
            BotonPrimario(tarjeta, accion, comando or (lambda: self.app.navegar(destino))).pack(anchor="w", padx=16, pady=(0, 12))

    def _presentar_estado(self, datos: dict) -> None:
        total, est = datos["total"], datos["estatus"]
        tipos = set(datos.get("tipos", {}))
        destino_revision = "pagos" if tipos == {"P"} else "nomina" if tipos == {"N"} else "admin40"
        hay_pendientes = False
        if not total:
            self._fila_accion("Empieza cargando los XML del cliente", "En Bóveda, elige una carpeta o periodo y pulsa Cargar selección.", "Abrir Bóveda", "boveda")
            hay_pendientes = True
        for campo, titulo, descripcion in (
            ("descargas_listas", "solicitudes listas para revisar", "El SAT indicó que terminaron. Abre Descargas SAT para revisar y recuperar sus paquetes."),
            ("descargas_pendientes", "solicitudes en proceso", "El último estado guardado indica que el SAT sigue procesándolas. Consulta su avance en Descargas SAT."),
        ):
            if datos.get(campo):
                self._fila_accion(f"{datos[campo]:,} {titulo}", descripcion, "Abrir Descargas SAT", "descargas", tono="azul")
                hay_pendientes = True
        for estado, titulo, descripcion, tono in (
            ("Sin validar", "XML sin validar", "Abre el módulo correspondiente: Comprobantes, Pagos o Nómina, y consulta su estatus SAT.", "ambar"),
            ("Cancelado", "XML con estatus Cancelado", "Revisa estos comprobantes y su última consulta antes de preparar tus reportes.", "rojo"),
            ("No Encontrado", "XML no encontrados en la última consulta", "Revisa los datos del comprobante y vuelve a consultar su estatus desde el módulo correspondiente.", "ambar"),
        ):
            if est[estado]:
                self._fila_accion(f"{est[estado]:,} {titulo}", descripcion, "Revisar XML", destino_revision, tono=tono)
                hay_pendientes = True
        if not hay_pendientes:
            self._fila_accion("Sin pendientes en los indicadores del inicio", "Puedes continuar revisando tus XML y preparando reportes. Los estatus corresponden a consultas guardadas.", "Revisar XML", "admin40", tono="verde")
