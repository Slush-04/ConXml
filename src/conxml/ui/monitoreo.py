"""Configuración visible y voluntaria del reporte técnico de presencia."""

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from conxml import monitoreo
from conxml.ui import theme as th
from conxml.ui.widgets import PanelCard, BotonSecundario, texto_adaptable


class ConfiguracionMonitoreo(PanelCard):
    def __init__(self, parent):
        super().__init__(parent)
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="x", padx=20, pady=18)
        ctk.CTkLabel(content, text="Monitoreo de equipos", font=(th.FUENTE, th.TAM_BODY, "bold")).pack(anchor="w")
        description = ctk.CTkLabel(content, text="Comparte con tu administrador la versión de ConXml, el sistema operativo y si la aplicación sigue abierta. Mientras su servidor esté encendido, también podrás recibir mensajes y bloqueos o desbloqueos del acceso a ConXml. El último bloqueo recibido se conserva al desconectar. No envía XML, RFC, contraseñas ni datos fiscales.",
                                  wraplength=690, justify="left")
        description.pack(fill="x", pady=8)
        texto_adaptable(description, content, margen=8)
        self.status = ctk.CTkLabel(content, text="", wraplength=690, justify="left", anchor="w")
        self.status.pack(fill="x", pady=(0, 8))
        self.toggle = ctk.CTkCheckBox(content, text="Compartir el estado técnico de esta instalación", command=self._toggle)
        self.toggle.pack(anchor="w", pady=(0, 10))
        button = BotonSecundario(content, "Importar configuración del administrador…", self._import)
        button.pack(anchor="w")
        self.botones = [button, self.toggle]
        self.load()

    def load(self):
        try:
            path = monitoreo.config_path()
            record = monitoreo.validate_record(monitoreo.read_record(path)) if path.exists() else None
            self.toggle.configure(state="normal" if record else "disabled")
            if record and record["enabled"]:
                self.toggle.select()
            else:
                self.toggle.deselect()
            if record:
                self.status.configure(text=f"Equipo: {record['alias']}\nServicio: {record['service_url']}\n{'Reporte habilitado' if record['enabled'] else 'Reporte desactivado'} · El administrador confirma la recepción.")
            else:
                self.status.configure(text="Sin configurar. Solicita a tu administrador un archivo distinto para cada equipo.")
        except monitoreo.MonitoringError as exc:
            self.toggle.configure(state="disabled")
            self.status.configure(text=str(exc))

    def _reload(self):
        controller = getattr(self.winfo_toplevel(), "_monitor_controller", None)
        if controller:
            controller.reload()
        self.load()

    def _toggle(self):
        try:
            monitoreo.set_enabled(bool(self.toggle.get()))
        except monitoreo.MonitoringError as exc:
            messagebox.showerror("Monitoreo", str(exc), parent=self)
        self._reload()

    def _import(self):
        source = filedialog.askopenfilename(parent=self, title="Importar configuración privada de este equipo", filetypes=[("Configuración JSON", "*.json")])
        if not source:
            return
        try:
            # Mostrar el destino antes de guardar una credencial o transmitir presencia.
            record = monitoreo.validate_record(monitoreo.read_record(Path(source)))
            if not messagebox.askyesno("Activar administración del equipo", f"¿Conectar esta instalación con {record['service_url']} usando el alias «{record['alias']}»?\n\nCompartirá su estado técnico y permitirá recibir mensajes y bloqueos o desbloqueos de ConXml. El bloqueo recibido se conservará al desconectar; los datos fiscales permanecen en el equipo.\n\nEl archivo debe ser exclusivo para este equipo.", parent=self):
                return
            monitoreo.import_configuration(Path(source))
        except monitoreo.MonitoringError as exc:
            messagebox.showerror("Monitoreo", str(exc), parent=self)
            return
        self._reload()
        messagebox.showinfo("Monitoreo configurado", "El reporte técnico quedó habilitado. Puedes desactivarlo aquí cuando lo necesites.\n\nLa credencial se guardó en el almacén seguro del sistema. Elimina el archivo importado si ya no lo necesitas.", parent=self)
