"""Avisos del administrador y bloqueo de la interfaz, sin detener operaciones en curso."""

import tkinter as tk
from tkinter import ttk, messagebox


class RemoteControlView:
    def __init__(self, root, acknowledge_messages):
        self.root = root
        self.acknowledge_messages = acknowledge_messages
        self.lock_window = None
        self.message_window = None
        self.messages = {}
        self.shown_ids = []

    def queue_messages(self, messages):
        for message in messages:
            self.messages[message["id"]] = message["text"]

    def clear_messages(self):
        if self.message_window and self.message_window.winfo_exists():
            self.message_window.destroy()
        self.message_window = None
        self.messages.clear()
        self.shown_ids = []

    def _close_application(self):
        app = getattr(self.root, "_conxml_app", None)
        if app is not None:
            app._al_cerrar()
        else:
            self.root.destroy()

    def _show_lock(self):
        window = tk.Toplevel(self.root)
        self.lock_window = window
        window.title("ConXml — Acceso bloqueado")
        window.transient(self.root)
        window.resizable(False, False)
        content = ttk.Frame(window, padding=24)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="Acceso a ConXml bloqueado", font=("TkDefaultFont", 18, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(content, text="El acceso de esta instalación está suspendido.\n\nTus datos se conservan. Mantén ConXml abierto y conectado para recibir el desbloqueo. Si el servidor está apagado, se conservará el último bloqueo recibido. Contacta al administrador si necesitas recuperar el acceso.", wraplength=520, justify="left").pack(anchor="w")
        ttk.Button(content, text="Cerrar ConXml", command=self._close_application).pack(anchor="e", pady=(20, 0))
        window.protocol("WM_DELETE_WINDOW", self._close_application)
        window.grab_set()
        window.focus_set()

    def _show_messages(self):
        window = tk.Toplevel(self.root)
        self.message_window = window
        window.title("ConXml — Mensaje del administrador")
        window.transient(self.lock_window or self.root)
        content = ttk.Frame(window, padding=20)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="Mensaje del administrador", font=("TkDefaultFont", 14, "bold")).pack(anchor="w", pady=(0, 10))
        body = ttk.Frame(content)
        body.pack(fill="both", expand=True)
        text = tk.Text(body, width=65, height=10, wrap="word")
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=text.yview)
        scrollbar.pack(side="right", fill="y")
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(fill="both", expand=True)
        self.shown_ids = list(self.messages)[:20]
        for identifier in self.shown_ids:
            text.insert("end", self.messages[identifier] + "\n\n")
        text.configure(state="disabled")
        ttk.Button(content, text="Entendido", command=self._dismiss_messages).pack(anchor="e", pady=(12, 0))
        window.protocol("WM_DELETE_WINDOW", self._dismiss_messages)
        if self.lock_window:
            window.grab_set()
        window.focus_set()

    def _dismiss_messages(self):
        try:
            self.acknowledge_messages(self.shown_ids)
        except Exception:
            messagebox.showerror("Confirmación pendiente", "No se pudo guardar la confirmación del mensaje. Intenta nuevamente.", parent=self.message_window)
            return
        for identifier in self.shown_ids:
            self.messages.pop(identifier, None)
        self.message_window.destroy()
        self.message_window = None
        self.shown_ids = []
        if self.lock_window:
            self.lock_window.grab_set()

    def sync(self, blocked):
        if not self.root.winfo_exists() or self.root.state() == "withdrawn":
            return False
        app = getattr(self.root, "_conxml_app", None)
        busy = bool(app and getattr(app, "_ocupada", False))
        grab = self.root.grab_current()
        other_dialog = grab is not None and grab not in (self.lock_window, self.message_window)
        if blocked and self.lock_window is None and not busy and not other_dialog:
            self._show_lock()
        if not blocked and self.lock_window:
            self.lock_window.destroy()
            self.lock_window = None
        if self.messages and self.message_window is None and not other_dialog and not busy:
            self._show_messages()
        if self.lock_window and self.root.grab_current() is None:
            self.lock_window.grab_set()
        return bool(self.lock_window) == bool(blocked)
