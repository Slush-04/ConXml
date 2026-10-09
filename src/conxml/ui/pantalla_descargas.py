"""Interfaz de solicitudes, seguimiento y recuperación del SAT."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from conxml.catalog.db import Catalogo
from conxml.config import Config
from conxml.sat.boveda_firma import archivos_guardados, guardar_archivos, quitar_archivos, carpeta_firma
from conxml.sat.descarga_masiva import (
    ClienteDescargaSAT,
    CredencialEFirma,
    ErrorDescargaSAT,
    FiltroDescarga,
    RespuestaSAT,
)
from conxml.sat.seguimiento import ResultadoSeguimiento, procesar_solicitud
from conxml.ui import responsive as resp
from conxml.ui import theme as th
from conxml.ui.selector_fecha import SelectorFecha
from conxml.ui.scroll import PaginaDesplazable
from conxml.ui.widgets import (
    BotonPrimario, BotonSecundario, Encabezado, Insignia, PanelCard,
    texto_adaptable,
)

ESTADOS = {
    0: "Token inválido", 1: "Aceptada", 2: "En proceso", 3: "Terminada",
    4: "Error", 5: "Rechazada", 6: "Vencida",
}
TIPOS = {"Todos": "", "Ingreso": "I", "Egreso": "E", "Traslado": "T", "Nómina": "N", "Pago": "P"}
INTERVALO_SEGUIMIENTO_MS = 60_000


class PantallaDescargas(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._firmas_activas: dict[str, CredencialEFirma] = {}
        self._revision_after: str | None = None
        self._rfc_visible = ""
        self._cliente_firma_visible: str | None = None
        self._modo_formulario_apilado: bool | None = None
        self._contenedor = PaginaDesplazable(self, fg_color="transparent")
        self._contenedor.pack(fill="both", expand=True, padx=16, pady=16)
        Encabezado(
            self._contenedor, "Descarga SAT",
            "Solicita CFDI por cliente y periodo; después consulta y recupera los paquetes del SAT.",
        ).pack(fill="x")
        self._cliente_lbl = ctk.CTkLabel(
            self._contenedor, text="Cliente activo: —", text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_BODY, "bold"), anchor="w",
        )
        self._cliente_lbl.pack(fill="x", padx=8, pady=(12, 4))
        self._destino_lbl = ctk.CTkLabel(self._contenedor, text="", anchor="w", justify="left", wraplength=650, text_color=th.TEXTO_SECUNDARIO)
        self._destino_lbl.pack(fill="x", padx=8, pady=(0, 8))

        formulario = PanelCard(self._contenedor)
        formulario.pack(fill="x", pady=(8, 10))
        formulario.columnconfigure(0, weight=1, uniform="formularios")
        formulario.columnconfigure(2, weight=1, uniform="formularios")
        self._formulario = formulario
        cred = ctk.CTkFrame(formulario, fg_color="transparent")
        cred.grid(row=0, column=0, sticky="nsew", padx=(16, 12), pady=14)
        cred.columnconfigure(0, weight=1)
        self._panel_cred = cred
        self._separador_formulario = ctk.CTkFrame(formulario, width=1, fg_color=th.BORDE)
        self._separador_formulario.grid(row=0, column=1, sticky="ns", pady=16)
        ctk.CTkLabel(cred, text="01  ·  Acceso con e.firma", font=(th.FUENTE, th.TAM_H3, "bold"), anchor="w").grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self._cer = tk.StringVar()
        self._key = tk.StringVar()
        self._password = tk.StringVar()
        ctk.CTkLabel(cred, text="Certificado e.firma (.cer)", text_color=th.TEXTO, anchor="w").grid(row=1, column=0, columnspan=2, sticky="ew")
        ctk.CTkEntry(cred, textvariable=self._cer, placeholder_text="Selecciona el archivo .cer").grid(row=2, column=0, padx=(0, 8), pady=(2, 8), sticky="ew")
        BotonSecundario(cred, "Examinar", self._elegir_cer).grid(row=2, column=1, pady=(2, 8))
        ctk.CTkLabel(cred, text="Llave privada (.key)", text_color=th.TEXTO, anchor="w").grid(row=3, column=0, columnspan=2, sticky="ew")
        ctk.CTkEntry(cred, textvariable=self._key, placeholder_text="Selecciona el archivo .key").grid(row=4, column=0, padx=(0, 8), pady=(2, 8), sticky="ew")
        BotonSecundario(cred, "Examinar", self._elegir_key).grid(row=4, column=1, pady=(2, 8))
        ctk.CTkLabel(cred, text="Contraseña de .key", text_color=th.TEXTO, anchor="w").grid(row=5, column=0, columnspan=2, sticky="ew")
        ctk.CTkEntry(cred, textvariable=self._password, show="●", placeholder_text="Se usa solo durante la operación").grid(row=6, column=0, columnspan=2, pady=(2, 8), sticky="ew")
        acciones_firma = ctk.CTkFrame(cred, fg_color="transparent")
        acciones_firma.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        self._btn_guardar_firma = BotonSecundario(acciones_firma, "Guardar e.firma", self._guardar_archivos_firma)
        self._btn_guardar_firma.pack(side="left", padx=(0, 8))
        self._btn_quitar_firma = BotonSecundario(acciones_firma, "Quitar guardada", self._quitar_archivos_firma)
        self._btn_quitar_firma.pack(side="left", padx=(0, 8))
        self._btn_seguimiento = BotonSecundario(
            acciones_firma, "Activar seguimiento", self._alternar_seguimiento,
        )
        self._btn_seguimiento.pack(side="left")

        solicitud = ctk.CTkFrame(formulario, fg_color="transparent")
        solicitud.grid(row=0, column=2, sticky="nsew", padx=(12, 16), pady=14)
        solicitud.columnconfigure(0, weight=1)
        self._panel_solicitud = solicitud
        ctk.CTkLabel(solicitud, text="02  ·  Periodo y comprobantes", font=(th.FUENTE, th.TAM_H3, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 10))
        self._direccion = tk.StringVar(value="Emitidos")
        self._desde = tk.StringVar(value=date.today().replace(day=1).strftime("%d/%m/%Y"))
        self._hasta = tk.StringVar(value=date.today().strftime("%d/%m/%Y"))
        self._tipo = tk.StringVar(value="Todos")
        campos = ctk.CTkFrame(solicitud, fg_color="transparent")
        campos.grid(row=1, column=0, sticky="ew")
        campos.columnconfigure((0, 1), weight=1, uniform="campos_sat")
        for indice, (etiqueta, variable, valores) in enumerate((("Dirección", self._direccion, ["Emitidos", "Recibidos"]),
                                            ("Tipo CFDI", self._tipo, list(TIPOS)),
                                            ("Desde · DD/MM/AAAA", self._desde, None),
                                            ("Hasta · DD/MM/AAAA", self._hasta, None))):
            grupo = ctk.CTkFrame(campos, fg_color="transparent")
            grupo.grid(row=indice // 2, column=indice % 2, sticky="ew", padx=(0, 8) if indice % 2 == 0 else (8, 0), pady=(0, 10))
            ctk.CTkLabel(grupo, text=etiqueta, text_color=th.TEXTO_SECUNDARIO,
                         font=(th.FUENTE, th.TAM_NOTA)).pack(anchor="w")
            if valores:
                entrada = ctk.CTkComboBox(grupo, variable=variable, values=valores, height=34)
            else:
                entrada = SelectorFecha(grupo, variable=variable, anio_completo=True)
            entrada.pack(fill="x", pady=(2, 0))
        self._btn_solicitar = BotonPrimario(solicitud, "Solicitar al SAT", self._solicitar)
        self._btn_solicitar.grid(row=2, column=0, pady=(4, 0), sticky="")

        historial = PanelCard(self._contenedor)
        historial.pack(fill="both", expand=True, pady=(0, 8))
        historial.rowconfigure(1, weight=1)
        historial.columnconfigure(0, weight=1)
        cabecera = ctk.CTkFrame(historial, fg_color="transparent")
        cabecera.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 8))
        self._estado_lbl = ctk.CTkLabel(cabecera, text="Solicitudes de este cliente", text_color=th.TEXTO_SECUNDARIO, font=(th.FUENTE, th.TAM_NOTA))
        cabecera.columnconfigure(0, weight=1)
        self._estado_lbl.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self._estado_lbl.configure(anchor="w", justify="left", wraplength=380)
        texto_adaptable(self._estado_lbl, cabecera, margen=200)
        self._btn_verificar = BotonSecundario(cabecera, "Consultar / descargar", self._verificar)
        self._btn_verificar.grid(row=0, column=1, sticky="e")
        marco = ctk.CTkFrame(historial, fg_color="transparent")
        marco.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        marco.rowconfigure(0, weight=1); marco.columnconfigure(0, weight=1)
        self._tabla = ttk.Treeview(
            marco, columns=("id", "direccion", "periodo", "estado", "cfdis", "mensaje"),
            show="headings", selectmode="browse", height=12, style="Solicitudes.Treeview",
        )
        for col, titulo, ancho in (
            ("id", "Solicitud SAT", 165), ("direccion", "Tipo", 76),
            ("periodo", "Periodo", 132), ("estado", "Estado", 90),
            ("cfdis", "CFDI", 58), ("mensaje", "Respuesta SAT", 210),
        ):
            self._tabla.heading(col, text=titulo)
            self._tabla.column(
                col, width=ancho, minwidth=70 if col == "mensaje" else 48,
                anchor="w", stretch=(col == "mensaje"),
            )
        self._tabla.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(marco, orient="vertical", command=self._tabla.yview)
        scroll.grid(row=0, column=1, sticky="ns"); self._tabla.configure(yscrollcommand=scroll.set)
        scroll_x = ttk.Scrollbar(marco, orient="horizontal", command=self._tabla.xview)
        scroll_x.grid(row=1, column=0, sticky="ew")
        self._tabla.configure(xscrollcommand=scroll_x.set)
        texto_adaptable(self._cliente_lbl, self._contenedor)
        texto_adaptable(self._destino_lbl, self._contenedor)
        self.botones = [self._btn_solicitar, self._btn_verificar, self._btn_seguimiento]
        self.bind("<Configure>", lambda evento: self._acomodar_formulario(evento.width), add="+")

    def aplicar_modo_compacto(self, ancho_compacto: bool, alto_compacto: bool) -> None:
        compacto = ancho_compacto or alto_compacto
        self._contenedor.pack(padx=8 if compacto else 16, pady=8 if compacto else 16)
        self._acomodar_formulario(self.winfo_width())

    def _acomodar_formulario(self, ancho: int) -> None:
        apilado = ancho < 1060
        if apilado == self._modo_formulario_apilado:
            return
        self._modo_formulario_apilado = apilado
        if apilado:
            self._formulario.columnconfigure(0, weight=1, uniform="")
            self._formulario.columnconfigure(2, weight=0, uniform="")
            self._panel_cred.grid_configure(row=0, column=0, columnspan=3, padx=16, pady=(14, 8))
            self._separador_formulario.grid_remove()
            self._panel_solicitud.grid_configure(row=1, column=0, columnspan=3, padx=16, pady=(8, 14))
        else:
            self._formulario.columnconfigure(0, weight=1, uniform="formularios")
            self._formulario.columnconfigure(2, weight=1, uniform="formularios")
            self._panel_cred.grid_configure(row=0, column=0, columnspan=1, padx=(16, 12), pady=14)
            self._separador_formulario.grid(row=0, column=1, sticky="ns", pady=16)
            self._panel_solicitud.grid_configure(row=0, column=2, columnspan=1, padx=(12, 16), pady=14)

    def al_mostrar(self) -> None:
        cliente = self.app.cliente_actual
        if not cliente:
            self.app.cambiar_cliente()
            return
        with Catalogo(self.app.db_path) as catalogo:
            detalle = catalogo.obtener_cliente(cliente)
            rfc = detalle["rfc"] if detalle else ""
            solicitudes = catalogo.solicitudes_descarga_cliente(cliente)
        self._cliente_lbl.configure(text=f"Cliente activo: {detalle['nombre'] if detalle else cliente} · RFC: {rfc or 'falta registrar'}")
        self._rfc_visible = rfc
        self._mostrar_firma_cliente(cliente)
        self._actualizar_aviso_seguimiento()
        config = Config()
        modo = "ZIP sin extraer" if config.modo_descarga_sat == "zip" else "XML organizados e importados"
        destino = config.carpeta_zip_sat if config.modo_descarga_sat == "zip" else config.carpeta_boveda
        self._destino_lbl.configure(text=f"Guardado: {modo}\nDestino: {destino}\nPuedes cambiarlo en Configuración.")
        self._renderizar_historial(solicitudes)

    def _actualizar_aviso_seguimiento(self) -> None:
        activo = self._rfc_visible in self._firmas_activas
        self._btn_seguimiento.configure(text="Detener seguimiento" if activo else "Activar seguimiento")

    def _guardar_firma(self, fiel: CredencialEFirma) -> None:
        self._firmas_activas[fiel.rfc] = fiel
        self._actualizar_aviso_seguimiento()
        self._programar_revision(1_000)

    def _programar_revision(self, demora_ms: int = INTERVALO_SEGUIMIENTO_MS) -> None:
        if self._revision_after is not None:
            self.after_cancel(self._revision_after)
            self._revision_after = None
        if self._firmas_activas:
            self._revision_after = self.after(demora_ms, self._revision_automatica)

    def _alternar_seguimiento(self) -> None:
        try:
            _, rfc = self._datos_cliente()
            if rfc in self._firmas_activas:
                self._firmas_activas.pop(rfc)
                self._programar_revision()
                self._actualizar_aviso_seguimiento()
                return
            cer, key, password = self._credenciales()
        except ErrorDescargaSAT as exc:
            messagebox.showerror("Descarga SAT", str(exc), parent=self)
            return

        def trabajo():
            fiel = CredencialEFirma.cargar(cer, key, password)
            if fiel.rfc != rfc:
                raise ErrorDescargaSAT("La e.firma no corresponde al RFC del cliente activo.")
            return fiel

        self.app.ejecutar(trabajo, self._guardar_firma, "Activando seguimiento SAT", al_error=self._presentar_error)
        self._password.set("")

    def _revision_automatica(self) -> None:
        self._revision_after = None
        if not self._firmas_activas:
            return
        if self.app._ocupada:
            self._programar_revision()
            return
        firmas = dict(self._firmas_activas)
        with Catalogo(self.app.db_path) as catalogo:
            pendientes = [dict(fila) for fila in catalogo.solicitudes_descarga_pendientes(set(firmas))]
        if not pendientes:
            self._programar_revision()
            return
        # Un lote acotado deja la interfaz disponible entre consultas.
        lote = pendientes[:3]
        config = Config()

        def trabajo():
            resultados = []
            for datos in lote:
                sat = None
                try:
                    sat = ClienteDescargaSAT(firmas[datos["rfc"]])
                    resultado = procesar_solicitud(sat, self.app.db_path, datos, config)
                    resultados.append((datos, resultado, ""))
                except Exception as exc:
                    from conxml.diagnostico import sanitizar_texto

                    mensaje = sanitizar_texto(str(exc)) if isinstance(exc, ErrorDescargaSAT) else "Error inesperado; consulta el diagnóstico."
                    with Catalogo(self.app.db_path) as catalogo:
                        catalogo.registrar_error_solicitud(datos["id_sat"], mensaje)
                    resultados.append((datos, None, mensaje))
                finally:
                    if sat is not None:
                        sat.cerrar()
            return resultados

        iniciado = self.app.ejecutar(
            trabajo, self._presentar_revision_automatica, "Consultando solicitudes SAT pendientes",
            al_error=self._error_revision_automatica,
        )
        if not iniciado:
            self._programar_revision()

    def _presentar_revision_automatica(self, resultados) -> None:
        recuperados = sum(bool(resultado and resultado.recuperada) for _, resultado, _ in resultados)
        errores = [mensaje for _, _, mensaje in resultados if mensaje]
        if errores:
            self.app.registro(f"Seguimiento SAT: {len(errores)} solicitud(es) con error; {errores[0]}")
        with Catalogo(self.app.db_path) as catalogo:
            filas = catalogo.solicitudes_descarga_cliente(self.app.cliente_actual) if self.app.cliente_actual else []
        if self.app.cliente_actual:
            self._renderizar_historial(filas)
        if recuperados:
            self.app.actualizar_resumen()
            admin = self.app._pantallas.get("admin40")
            if admin:
                admin._cargar_tabla()
            self._estado_lbl.configure(text=f"Seguimiento automático: {recuperados} solicitud(es) recuperada(s).")
        elif errores:
            self._estado_lbl.configure(text=f"Seguimiento automático: {errores[0]}")
        self._programar_revision()

    def _error_revision_automatica(self, error: Exception) -> None:
        self.app.registro(f"Seguimiento SAT: {type(error).__name__}")
        self._estado_lbl.configure(text="No se pudo completar la revisión automática; se reintentará.")
        self._programar_revision()

    def destroy(self) -> None:
        if self._revision_after is not None:
            self.after_cancel(self._revision_after)
            self._revision_after = None
        self._firmas_activas.clear()
        super().destroy()

    def _elegir_cer(self) -> None:
        ruta = filedialog.askopenfilename(parent=self, title="Seleccionar certificado e.firma", filetypes=[("Certificado SAT", "*.cer *.crt"), ("Todos los archivos", "*.*")])
        if ruta:
            self._cer.set(ruta)

    def _elegir_key(self) -> None:
        ruta = filedialog.askopenfilename(parent=self, title="Seleccionar llave privada e.firma", filetypes=[("Llave privada SAT", "*.key"), ("Todos los archivos", "*.*")])
        if ruta:
            self._key.set(ruta)

    def _mostrar_firma_cliente(self, cliente: str) -> None:
        if cliente != self._cliente_firma_visible:
            self._cliente_firma_visible = cliente
            self._password.set("")
            guardados = archivos_guardados(Config(), cliente)
            self._cer.set(str(guardados[0]) if guardados else "")
            self._key.set(str(guardados[1]) if guardados else "")
        guardados = archivos_guardados(Config(), cliente)
        self._btn_quitar_firma.configure(state="normal" if guardados else "disabled")

    def _guardar_archivos_firma(self) -> None:
        try:
            cliente, rfc = self._datos_cliente()
            cer, key, password = self._credenciales()
            fiel = CredencialEFirma.cargar(cer, key, password)
            if fiel.rfc != rfc:
                raise ErrorDescargaSAT("El RFC del certificado no corresponde al cliente activo.")
            cer_local, key_local = guardar_archivos(Config(), cliente, cer, key)
        except (ErrorDescargaSAT, ValueError, OSError) as exc:
            messagebox.showerror("e.firma local", str(exc), parent=self)
            return
        self._cer.set(str(cer_local))
        self._key.set(str(key_local))
        self._mostrar_firma_cliente(cliente)
        messagebox.showinfo("e.firma local", f"Archivos guardados para este cliente en:\n{carpeta_firma(Config(), cliente)}\n\nLa contraseña no se guardó.", parent=self)

    def _quitar_archivos_firma(self) -> None:
        cliente = self.app.cliente_actual
        if not cliente:
            return
        guardados = archivos_guardados(Config(), cliente)
        if not guardados:
            return
        if not messagebox.askyesno("e.firma local", "¿Quitar el certificado y la llave privada guardados para este cliente?", parent=self):
            return
        try:
            quitar_archivos(Config(), cliente)
        except OSError as exc:
            messagebox.showerror("e.firma local", str(exc), parent=self)
            return
        if self._cer.get() == str(guardados[0]):
            self._cer.set("")
        if self._key.get() == str(guardados[1]):
            self._key.set("")
        self._mostrar_firma_cliente(cliente)

    def _credenciales(self) -> tuple[str, str, str]:
        cer, key, password = self._cer.get().strip(), self._key.get().strip(), self._password.get()
        if not cer or not key or not password:
            raise ErrorDescargaSAT("Selecciona el .cer, el .key e ingresa la contraseña de la e.firma.")
        return cer, key, password

    def _datos_cliente(self) -> tuple[str, str]:
        cliente = self.app.cliente_actual
        if not cliente:
            raise ErrorDescargaSAT("Primero selecciona un cliente.")
        with Catalogo(self.app.db_path) as catalogo:
            detalle = catalogo.obtener_cliente(cliente)
        rfc = (detalle["rfc"] if detalle else "").strip().upper()
        if not rfc:
            raise ErrorDescargaSAT("Registra el RFC del cliente antes de solicitar CFDI.")
        return cliente, rfc

    def _solicitar(self) -> None:
        try:
            cliente, rfc = self._datos_cliente()
            cer, key, password = self._credenciales()
            desde = SelectorFecha._parsear(self._desde.get())
            hasta = SelectorFecha._parsear(self._hasta.get())
            if desde is None or hasta is None:
                raise ErrorDescargaSAT("Revisa las fechas Desde y Hasta. Usa DD/MM/AAAA o selecciónalas en el calendario.")
            filtro = FiltroDescarga(
                rfc=rfc, direccion=self._direccion.get(),
                fecha_inicial=desde, fecha_final=hasta,
                tipo_comprobante=TIPOS[self._tipo.get()],
            )
            filtro.validar()
            with Catalogo(self.app.db_path) as catalogo:
                anteriores = catalogo.solicitudes_descarga_cliente(cliente)
            existente = next((fila for fila in anteriores if (
                fila["rfc"] == filtro.rfc
                and fila["direccion"] == filtro.direccion
                and fila["fecha_inicial"] == filtro.fecha_inicial.isoformat()
                and fila["fecha_final"] == filtro.fecha_final.isoformat()
                and fila["tipo_comprobante"] == filtro.tipo_comprobante
                and fila["estado"] in (None, 1, 2)
            )), None)
            if existente is not None:
                self._tabla.selection_set(existente["id_sat"])
                self._tabla.focus(existente["id_sat"])
                messagebox.showinfo(
                    "Descarga SAT",
                    "Ya existe una solicitud pendiente con ese cliente y periodo. "
                    "Consulta la solicitud del historial en lugar de volver a enviarla.",
                    parent=self,
                )
                return
        except (ErrorDescargaSAT, ValueError, KeyError) as exc:
            messagebox.showerror("Descarga SAT", str(exc), parent=self)
            return
        self._estado_lbl.configure(text="Enviando solicitud al SAT…")

        def trabajo():
            fiel = CredencialEFirma.cargar(cer, key, password)
            sat = ClienteDescargaSAT(fiel)
            try:
                return sat.solicitar(filtro), fiel
            finally:
                sat.cerrar()

        self.app.ejecutar(
            trabajo, lambda resultado: self._presentar_solicitud(cliente, filtro, *resultado),
            "Solicitando CFDI al SAT", al_error=self._presentar_error,
        )
        self._password.set("")

    def _presentar_error(self, error: Exception) -> None:
        from conxml.diagnostico import sanitizar_texto

        mensaje = sanitizar_texto(str(error)) if isinstance(error, ErrorDescargaSAT) else (
            "Falló la operación. Consulta el archivo de diagnóstico para ver más detalles."
        )
        self._estado_lbl.configure(text=f"No se completó la operación: {mensaje}")
        messagebox.showerror("Descarga SAT", mensaje, parent=self)

    def _presentar_solicitud(
        self, cliente: str, filtro: FiltroDescarga, respuesta: RespuestaSAT,
        fiel: CredencialEFirma | None = None,
    ) -> None:
        if not respuesta.id_solicitud:
            messagebox.showerror("Descarga SAT", respuesta.mensaje or f"El SAT respondió con código {respuesta.cod_estatus or 'sin código'}.", parent=self)
            self._estado_lbl.configure(text="No se generó una solicitud")
            return
        with Catalogo(self.app.db_path) as catalogo:
            catalogo.guardar_solicitud_descarga(
                cliente=cliente, rfc=filtro.rfc, direccion=filtro.direccion,
                fecha_inicial=filtro.fecha_inicial.isoformat(), fecha_final=filtro.fecha_final.isoformat(),
                tipo_comprobante=filtro.tipo_comprobante, id_sat=respuesta.id_solicitud,
                cod_estatus=respuesta.cod_estatus, estado=1, mensaje=respuesta.mensaje,
            )
            filas = catalogo.solicitudes_descarga_cliente(cliente)
        self._renderizar_historial(filas)
        self._estado_lbl.configure(text=f"Solicitud registrada: {respuesta.mensaje or respuesta.cod_estatus}")
        if fiel is not None:
            self._guardar_firma(fiel)

    def _verificar(self) -> None:
        seleccion = self._tabla.selection()
        if not seleccion:
            messagebox.showinfo("Descarga SAT", "Selecciona una solicitud del historial.", parent=self)
            return
        try:
            cer, key, password = self._credenciales()
            cliente, _ = self._datos_cliente()
            with Catalogo(self.app.db_path) as catalogo:
                fila = catalogo.obtener_solicitud_descarga(seleccion[0])
            if fila is None:
                raise ErrorDescargaSAT("La solicitud seleccionada ya no está en el historial.")
            datos = dict(fila)
            if datos["cliente"] != cliente:
                raise ErrorDescargaSAT("La solicitud no corresponde al cliente activo.")
        except (ErrorDescargaSAT, ValueError) as exc:
            messagebox.showerror("Descarga SAT", str(exc), parent=self)
            return
        self._estado_lbl.configure(text="Consultando estado y paquetes en el SAT…")
        config = Config()
        modo = config.modo_descarga_sat
        datos["modo_guardado"] = modo
        datos["destino_guardado"] = str(config.carpeta_zip_sat if modo == "zip" else config.carpeta_boveda)

        def trabajo():
            fiel = CredencialEFirma.cargar(cer, key, password)
            if fiel.rfc and fiel.rfc != datos["rfc"]:
                raise ErrorDescargaSAT("La e.firma seleccionada no corresponde a esta solicitud.")
            sat = ClienteDescargaSAT(fiel)
            try:
                return procesar_solicitud(sat, self.app.db_path, datos, config), fiel
            finally:
                sat.cerrar()

        def presentar(resultado):
            seguimiento, fiel = resultado
            self._presentar_verificacion(datos, seguimiento)
            self._guardar_firma(fiel)

        self.app.ejecutar(trabajo, presentar, "Consultando y recuperando CFDI", al_error=self._presentar_error)
        self._password.set("")

    def _presentar_verificacion(self, datos: dict, resultado: ResultadoSeguimiento) -> None:
        respuesta = resultado.respuesta
        copiados, errores = resultado.copiados, resultado.errores
        insertados, recuperada = resultado.insertados, resultado.recuperada
        with Catalogo(self.app.db_path) as catalogo:
            filas = catalogo.solicitudes_descarga_cliente(datos["cliente"])
        self._renderizar_historial(filas)
        estado = ESTADOS.get(respuesta.estado, "Estado desconocido")
        texto = f"{estado}. CFDI: {respuesta.numero_cfdis}. XML organizados: {copiados}; incorporados al visor: {insertados}."
        if datos.get("modo_guardado") == "zip":
            texto = f"{estado}. Paquetes ZIP guardados: {copiados}. Sin extracción ni importación automática."
        if respuesta.estado == 3 and datos.get("recuperado"):
            texto = f"{estado}. Esta solicitud ya se había recuperado; no se volvió a descargar el paquete."
        elif respuesta.estado == 3 and not recuperada:
            texto = "Terminada. El SAT aún no entregó los paquetes; ConXml volverá a consultar."
        if errores:
            texto += f" XML con error: {errores}."
        self._estado_lbl.configure(text=texto)
        if respuesta.estado == 3:
            self.app.actualizar_resumen()
            admin = self.app._pantallas.get("admin40")
            if admin:
                admin._cargar_tabla()

    def _renderizar_historial(self, filas) -> None:
        seleccion = set(self._tabla.selection())
        self._estado_lbl.configure(
            text=(f"{len(filas)} solicitudes de este cliente" if filas
                  else "Aún no hay solicitudes para este cliente.")
        )
        for iid in self._tabla.get_children():
            self._tabla.delete(iid)
        for fila in filas:
            desde = date.fromisoformat(fila['fecha_inicial']).strftime("%d/%m/%Y")
            hasta = date.fromisoformat(fila['fecha_final']).strftime("%d/%m/%Y")
            periodo = f"{desde} a {hasta}"
            estado = ESTADOS.get(fila["estado"], "Pendiente")
            self._tabla.insert(
                "", "end", iid=fila["id_sat"],
                values=(fila["id_sat"], fila["direccion"], periodo, estado,
                        fila["numero_cfdis"], fila["mensaje"] or fila["cod_estatus"]),
            )
            if fila["id_sat"] in seleccion:
                self._tabla.selection_set(fila["id_sat"])
