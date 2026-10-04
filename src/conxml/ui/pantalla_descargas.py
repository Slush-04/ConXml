"""Interfaz de solicitudes, seguimiento y recuperación del SAT."""
from __future__ import annotations

import json
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from conxml.boveda import copiar_xmls, direccion_comprobante, ruta_cliente
from conxml.catalog.db import Catalogo
from conxml.catalog.importer import importar_carpetas
from conxml.config import Config
from conxml.cfdi import parse_comprobante
from conxml.sat.descarga_masiva import (
    ClienteDescargaSAT,
    CredencialEFirma,
    ErrorDescargaSAT,
    FiltroDescarga,
    RespuestaSAT,
    guardar_paquete_zip,
)
from conxml.ui import responsive as resp
from conxml.ui import theme as th
from conxml.ui.widgets import BotonPrimario, BotonSecundario, Encabezado, Insignia, PanelCard

ESTADOS = {
    0: "Token inválido", 1: "Aceptada", 2: "En proceso", 3: "Terminada",
    4: "Error", 5: "Rechazada", 6: "Vencida",
}
TIPOS = {"Todos": "", "Ingreso": "I", "Egreso": "E", "Traslado": "T", "Nómina": "N", "Pago": "P"}


class PantallaDescargas(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkFrame, app) -> None:
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._contenedor = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._contenedor.pack(fill="both", expand=True, padx=32, pady=24)
        Encabezado(
            self._contenedor, "Descarga SAT",
            "Solicita CFDI por cliente y periodo; después consulta y recupera los paquetes del SAT.",
        ).pack(fill="x")
        self._cliente_lbl = ctk.CTkLabel(
            self._contenedor, text="Cliente activo: —", text_color=th.TEXTO,
            font=(th.FUENTE, th.TAM_BODY, "bold"), anchor="w",
        )
        self._cliente_lbl.pack(fill="x", padx=8, pady=(12, 4))

        cred = PanelCard(self._contenedor)
        cred.pack(fill="x", pady=(8, 10))
        cred.columnconfigure(1, weight=1)
        self._cer = tk.StringVar()
        self._key = tk.StringVar()
        self._password = tk.StringVar()
        ctk.CTkLabel(cred, text="Certificado e.firma (.cer)", text_color=th.TEXTO).grid(row=0, column=0, padx=(16, 8), pady=(12, 6), sticky="w")
        ctk.CTkEntry(cred, textvariable=self._cer, placeholder_text="Selecciona el archivo .cer").grid(row=0, column=1, padx=8, pady=(12, 6), sticky="ew")
        BotonSecundario(cred, "Examinar", self._elegir_cer).grid(row=0, column=2, padx=(0, 16), pady=(12, 6))
        ctk.CTkLabel(cred, text="Llave privada (.key)", text_color=th.TEXTO).grid(row=1, column=0, padx=(16, 8), pady=6, sticky="w")
        ctk.CTkEntry(cred, textvariable=self._key, placeholder_text="Selecciona el archivo .key").grid(row=1, column=1, padx=8, pady=6, sticky="ew")
        BotonSecundario(cred, "Examinar", self._elegir_key).grid(row=1, column=2, padx=(0, 16), pady=6)
        ctk.CTkLabel(cred, text="Contraseña de .key", text_color=th.TEXTO).grid(row=2, column=0, padx=(16, 8), pady=(6, 12), sticky="w")
        ctk.CTkEntry(cred, textvariable=self._password, show="●", placeholder_text="Se usa solo durante la operación").grid(row=2, column=1, padx=8, pady=(6, 12), sticky="ew")
        ctk.CTkLabel(
            cred, text="ConXml no guarda la contraseña ni copia la llave privada.",
            text_color=th.TEXTO_SECUNDARIO, font=(th.FUENTE, th.TAM_NOTA),
        ).grid(row=2, column=2, padx=(0, 16), pady=(6, 12), sticky="w")

        solicitud = PanelCard(self._contenedor)
        solicitud.pack(fill="x", pady=(0, 10))
        solicitud.columnconfigure(1, weight=1)
        self._direccion = tk.StringVar(value="Emitidos")
        self._desde = tk.StringVar(value=date.today().replace(day=1).isoformat())
        self._hasta = tk.StringVar(value=date.today().isoformat())
        self._tipo = tk.StringVar(value="Todos")
        ctk.CTkLabel(solicitud, text="Dirección", text_color=th.TEXTO).grid(row=0, column=0, padx=(16, 8), pady=(12, 8), sticky="w")
        ctk.CTkComboBox(solicitud, variable=self._direccion, values=["Emitidos", "Recibidos"], width=150).grid(row=0, column=1, padx=8, pady=(12, 8), sticky="w")
        ctk.CTkLabel(solicitud, text="Tipo CFDI", text_color=th.TEXTO).grid(row=0, column=2, padx=(12, 8), pady=(12, 8), sticky="e")
        ctk.CTkComboBox(solicitud, variable=self._tipo, values=list(TIPOS), width=150).grid(row=0, column=3, padx=(8, 16), pady=(12, 8), sticky="w")
        ctk.CTkLabel(solicitud, text="Desde", text_color=th.TEXTO).grid(row=1, column=0, padx=(16, 8), pady=(4, 12), sticky="w")
        ctk.CTkEntry(solicitud, textvariable=self._desde, placeholder_text="AAAA-MM-DD", width=150).grid(row=1, column=1, padx=8, pady=(4, 12), sticky="w")
        ctk.CTkLabel(solicitud, text="Hasta", text_color=th.TEXTO).grid(row=1, column=2, padx=(12, 8), pady=(4, 12), sticky="e")
        ctk.CTkEntry(solicitud, textvariable=self._hasta, placeholder_text="AAAA-MM-DD", width=150).grid(row=1, column=3, padx=(8, 16), pady=(4, 12), sticky="w")
        self._btn_solicitar = BotonPrimario(solicitud, "Solicitar al SAT", self._solicitar)
        self._btn_solicitar.grid(row=0, column=4, rowspan=2, padx=(8, 16), pady=12, sticky="ns")

        historial = PanelCard(self._contenedor)
        historial.pack(fill="both", expand=True, pady=(0, 8))
        historial.rowconfigure(1, weight=1)
        historial.columnconfigure(0, weight=1)
        cabecera = ctk.CTkFrame(historial, fg_color="transparent")
        cabecera.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 8))
        self._estado_lbl = ctk.CTkLabel(cabecera, text="Solicitudes de este cliente", text_color=th.TEXTO_SECUNDARIO, font=(th.FUENTE, th.TAM_NOTA))
        self._estado_lbl.pack(side="left")
        self._btn_verificar = BotonSecundario(cabecera, "Consultar / descargar", self._verificar)
        self._btn_verificar.pack(side="right")
        marco = ctk.CTkFrame(historial, fg_color="transparent")
        marco.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        marco.rowconfigure(0, weight=1); marco.columnconfigure(0, weight=1)
        self._tabla = ttk.Treeview(
            marco, columns=("id", "direccion", "periodo", "estado", "cfdis", "mensaje"),
            show="headings", selectmode="browse", height=8,
        )
        for col, titulo, ancho in (
            ("id", "Solicitud SAT", 250), ("direccion", "Tipo", 90),
            ("periodo", "Periodo", 170), ("estado", "Estado", 110),
            ("cfdis", "CFDI", 70), ("mensaje", "Respuesta SAT", 260),
        ):
            self._tabla.heading(col, text=titulo)
            self._tabla.column(col, width=ancho, anchor="w")
        self._tabla.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(marco, orient="vertical", command=self._tabla.yview)
        scroll.grid(row=0, column=1, sticky="ns"); self._tabla.configure(yscrollcommand=scroll.set)
        self.botones = [self._btn_solicitar, self._btn_verificar]

    def aplicar_modo_compacto(self, ancho_compacto: bool, alto_compacto: bool) -> None:
        compacto = ancho_compacto or alto_compacto
        self._contenedor.pack_configure(padx=12 if compacto else 32, pady=12 if compacto else 24)

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
        self._renderizar_historial(solicitudes)

    def _elegir_cer(self) -> None:
        ruta = filedialog.askopenfilename(parent=self, title="Seleccionar certificado e.firma", filetypes=[("Certificado SAT", "*.cer *.crt"), ("Todos los archivos", "*.*")])
        if ruta:
            self._cer.set(ruta)

    def _elegir_key(self) -> None:
        ruta = filedialog.askopenfilename(parent=self, title="Seleccionar llave privada e.firma", filetypes=[("Llave privada SAT", "*.key"), ("Todos los archivos", "*.*")])
        if ruta:
            self._key.set(ruta)

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
            filtro = FiltroDescarga(
                rfc=rfc, direccion=self._direccion.get(),
                fecha_inicial=datetime.strptime(self._desde.get().strip(), "%Y-%m-%d").date(),
                fecha_final=datetime.strptime(self._hasta.get().strip(), "%Y-%m-%d").date(),
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
                return sat.solicitar(filtro)
            finally:
                sat.cerrar()

        self.app.ejecutar(trabajo, lambda r: self._presentar_solicitud(cliente, filtro, r), "Solicitando CFDI al SAT")
        self._password.set("")

    def _presentar_solicitud(self, cliente: str, filtro: FiltroDescarga, respuesta: RespuestaSAT) -> None:
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
            datos["paquetes"] = json.loads(datos.pop("paquetes_json") or "[]")
        except (ErrorDescargaSAT, ValueError) as exc:
            messagebox.showerror("Descarga SAT", str(exc), parent=self)
            return
        self._estado_lbl.configure(text="Consultando estado y paquetes en el SAT…")

        def trabajo():
            fiel = CredencialEFirma.cargar(cer, key, password)
            if fiel.rfc and fiel.rfc != datos["rfc"]:
                raise ErrorDescargaSAT("La e.firma seleccionada no corresponde a esta solicitud.")
            sat = ClienteDescargaSAT(fiel)
            try:
                respuesta = sat.verificar(datos["rfc"], datos["id_sat"])
                copiados = 0
                errores = 0
                recuperada = bool(datos.get("recuperado"))
                if respuesta.estado == 3 and not recuperada:
                    import tempfile
                    with tempfile.TemporaryDirectory(prefix="conxml-sat-") as temporal:
                        temp = Path(temporal)
                        archivos_boveda: list[Path] = []
                        for indice, paquete_id in enumerate(respuesta.paquetes, start=1):
                            zip_bytes = sat.descargar_paquete(datos["rfc"], paquete_id)
                            carpeta = temp / str(indice)
                            archivos = guardar_paquete_zip(zip_bytes, carpeta)
                            if archivos:
                                parcial = copiar_xmls(carpeta, Config(), cliente, datos["rfc"])
                                copiados += parcial.copiados
                                errores += parcial.errores
                                raiz_boveda = ruta_cliente(Config(), cliente)
                                for archivo in archivos:
                                    try:
                                        comprobante = parse_comprobante(archivo)
                                        direccion = direccion_comprobante(comprobante.emisor_rfc, datos["rfc"])
                                        destino = (
                                            raiz_boveda / direccion / f"{comprobante.fecha.year:04d}"
                                            / f"{comprobante.fecha.month:02d}" / archivo.name
                                        )
                                        if destino.is_file():
                                            archivos_boveda.append(destino)
                                    except Exception:
                                        continue
                        raiz_boveda = ruta_cliente(Config(), cliente)
                        with Catalogo(self.app.db_path) as catalogo:
                            importados = importar_carpetas(catalogo, archivos_boveda, cliente)
                    return respuesta, copiados, errores, importados.insertados, True
                return respuesta, copiados, errores, 0, recuperada
            finally:
                sat.cerrar()

        self.app.ejecutar(trabajo, lambda resultado: self._presentar_verificacion(datos, resultado), "Consultando y recuperando CFDI")
        self._password.set("")

    def _presentar_verificacion(self, datos: dict, resultado) -> None:
        respuesta, copiados, errores, insertados, recuperada = resultado
        with Catalogo(self.app.db_path) as catalogo:
            catalogo.guardar_solicitud_descarga(
                cliente=datos["cliente"], rfc=datos["rfc"], direccion=datos["direccion"],
                fecha_inicial=datos["fecha_inicial"], fecha_final=datos["fecha_final"],
                tipo_comprobante=datos["tipo_comprobante"], id_sat=datos["id_sat"],
                cod_estatus=respuesta.cod_estatus, estado=respuesta.estado,
                mensaje=respuesta.mensaje, numero_cfdis=respuesta.numero_cfdis,
                paquetes=respuesta.paquetes, recuperado=recuperada,
            )
            filas = catalogo.solicitudes_descarga_cliente(datos["cliente"])
        self._renderizar_historial(filas)
        estado = ESTADOS.get(respuesta.estado, "Estado desconocido")
        texto = f"{estado}. CFDI: {respuesta.numero_cfdis}. XML organizados: {copiados}; incorporados al visor: {insertados}."
        if respuesta.estado == 3 and datos.get("recuperado"):
            texto = f"{estado}. Esta solicitud ya se había recuperado; no se volvió a descargar el paquete."
        if errores:
            texto += f" XML con error: {errores}."
        self._estado_lbl.configure(text=texto)
        if respuesta.estado == 3:
            self.app.actualizar_resumen()
            admin = self.app._pantallas.get("admin40")
            if admin:
                admin._cargar_tabla()

    def _renderizar_historial(self, filas) -> None:
        for iid in self._tabla.get_children():
            self._tabla.delete(iid)
        for fila in filas:
            periodo = f"{fila['fecha_inicial']} a {fila['fecha_final']}"
            estado = ESTADOS.get(fila["estado"], "Pendiente")
            self._tabla.insert(
                "", "end", iid=fila["id_sat"],
                values=(fila["id_sat"], fila["direccion"], periodo, estado,
                        fila["numero_cfdis"], fila["mensaje"] or fila["cod_estatus"]),
            )
