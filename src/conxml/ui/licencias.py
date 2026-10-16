"""Puerta de activación: nunca interrumpe una escritura o un diálogo existente."""
import queue
import threading
import tkinter as tk
from tkinter import ttk

from conxml.licencias import LicenseError
from conxml.licensing_client import get_client


class LicenseView:
    def __init__(self, root, on_ready):
        self.root, self.on_ready = root, on_ready
        self.client = get_client()
        if self.client.required:
            self.root.title('ConXml — Licencia de prueba')
        self.window = None
        self.started = False
        self.busy = False
        self.events = queue.Queue()
        self.client.start()
        self.poll()

    def close(self):
        app = getattr(self.root, '_conxml_app', None)
        if app:
            app._al_cerrar()
        else:
            self.root.destroy()

    def show(self):
        window = self.window = tk.Toplevel(self.root)
        window.title('ConXml — Licencia de prueba')
        window.transient(self.root)
        window.protocol('WM_DELETE_WINDOW', self.close)
        body = ttk.Frame(window, padding=24)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text='Licencia de prueba', font=('TkDefaultFont', 18, 'bold')).pack(anchor='w')
        ttk.Label(body, text='La activación requiere internet. Se comparte el identificador de instalación,\nversión, sistema, actividad y última IP con el servicio de licencias.\nLos XML, RFC y credenciales fiscales permanecen en tu equipo.\nAl vencer o bloquearse el acceso, tus archivos se conservan.',
                  wraplength=550, justify='left').pack(anchor='w', pady=12)
        self.status = ttk.Label(body, text=self.client.error, wraplength=550, justify='left')
        self.status.pack(anchor='w', pady=8)
        ttk.Label(body, text='Código de licencia (se guarda solo la credencial del equipo):').pack(anchor='w')
        self.code = ttk.Entry(body, width=55, show='•')
        self.code.pack(fill='x', pady=8)
        self.activate = ttk.Button(body, text='Activar con este código', command=self.submit)
        self.activate.pack(anchor='w')
        self.retry = ttk.Button(body, text='Reintentar validación', command=lambda: self.submit(False))
        self.retry.pack(anchor='w', pady=8)
        ttk.Button(body, text='Cerrar ConXml', command=self.close).pack(anchor='e')
        window.grab_set()
        self.code.focus_set()

    def submit(self, activation=True):
        if self.busy:
            return
        code = self.code.get().strip() if activation else None
        self.code.delete(0, 'end')
        self.busy = True
        self.activate.configure(state='disabled')
        self.retry.configure(state='disabled')
        self.status.configure(text='Validando licencia…')

        def work():
            try:
                self.client.sync(code)
                self.events.put(None)
            except LicenseError as exc:
                self.events.put(str(exc))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        if not self.root.winfo_exists():
            return
        try:
            result = self.events.get_nowait()
            self.busy = False
            if self.window:
                self.activate.configure(state='normal')
                self.retry.configure(state='normal')
                self.status.configure(text=result or self.client.error)
        except queue.Empty:
            pass
        allowed = self.client.allowed()
        if allowed:
            if self.window:
                self.window.destroy()
                self.window = None
            if not self.started:
                self.started = True
                self.on_ready()
        else:
            app = getattr(self.root, '_conxml_app', None)
            if self.window is None and not (app and app._ocupada) and self.root.grab_current() is None:
                self.show()
            elif self.window and not self.busy:
                self.status.configure(text=self.client.error)
        self.root.after(500, self.poll)
