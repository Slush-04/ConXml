"""Control compacto de actualización. Todo Tk se ejecuta en el hilo principal."""
import tkinter as tk
import queue
import sys
import threading
from tkinter import messagebox

import customtkinter as ctk

from conxml import __version__
from conxml.config import Config
from conxml.respaldos import respaldo_automatico
from conxml.updates import Updater, UpdateError
from conxml.ui import theme as th


class Actualizaciones:
    def __init__(self, app):
        self.app = app
        # Cache fuera del expediente y respaldos; la demo respeta CONXML_DATA_DIR.
        self.updater = Updater(Config().base.parent / 'updates')
        self.release = None
        self.path = None
        self.queue = queue.Queue()
        self.checking = False
        self.closed = False
        self.poll = None
        self.timer = None
        self.button = ctk.CTkButton(app._marco_bd, text='↻ Versión', width=112, height=28,
                                   fg_color=th.SIDEBAR_HOVER, hover_color=th.PRIMARIO_HOVER, text_color=th.SIDEBAR_TEXTO_ACTIVO,
                                   command=self.click)
        self.button.pack(fill='x', pady=(12, 0))
        self.tooltip = ctk.CTkLabel(app, text='Buscar actualización', fg_color=th.FONDO_ENTRADA)
        self.button.bind('<Enter>', self._show_tip)
        self.button.bind('<Leave>', lambda _: self.tooltip.place_forget())
        tk.Misc.bind(self.app, '<Destroy>', self._destroy, add='+')
        self.poll = app.after(100, self._poll)
        self.timer = app.after(2000, self.check)

    def _show_tip(self, _):
        self.tooltip.configure(text=f'Descargar ConXml {self.release.version}' if self.release else f'ConXml {__version__}: buscar actualización')
        self.tooltip.place(x=self.app.ancho_sidebar + 8, rely=1, y=-16, anchor='sw')

    def _destroy(self, event):
        if event.widget is self.app:
            self.closed = True
            for timer in (self.poll, self.timer):
                if timer:
                    self.app.after_cancel(timer)

    def check(self, manual=False):
        if self.closed or self.checking:
            return
        self.checking = True
        def work():
            try:
                self.queue.put((self.updater.check(), None, manual))
            except Exception as exc:
                self.queue.put((None, str(exc), manual))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        if self.closed:
            return
        try:
            release, error, manual = self.queue.get_nowait()
            self.checking = False
            if error:
                self.app.registro(f'Actualizaciones: {error}')
                if manual:
                    messagebox.showinfo('Actualizaciones', error, parent=self.app)
            else:
                self.release = release
                self.button.configure(text='↓ Actualizar' if release else '↻ Versión')
                if release:
                    self.app.registro(f'ConXml {release.version} disponible. Pulsa Actualizar en el menú lateral para descargar.')
                elif manual:
                    messagebox.showinfo('Actualizaciones', 'No hay una versión compatible más reciente con instalador verificable.', parent=self.app)
            if self.timer:
                self.app.after_cancel(self.timer)
            self.timer = self.app.after(6 * 60 * 60 * 1000, self.check)
        except queue.Empty:
            pass
        self.poll = self.app.after(100, self._poll)

    def click(self):
        if not self.release:
            self.check(manual=True)
            return
        release = self.release
        if not messagebox.askyesno('Nueva versión', f'ConXml {release.version} disponible ({release.size / 1024**2:.1f} MB).\n¿Descargar la actualización?', parent=self.app):
            return
        self.app.ejecutar(lambda: self.updater.download(release),
                          lambda path: self._downloaded(release, path),
                          f'Descargando ConXml {release.version}')

    def _downloaded(self, release, path):
        self.path = path
        if self.updater.demo or sys.platform != 'win32' or not getattr(sys, 'frozen', False):
            messagebox.showinfo('Prueba de actualización', f'Descarga y SHA-256 comprobados:\n{path}\n\nEn desarrollo/Mac no se ejecutan reemplazos de binarios Windows.', parent=self.app)
            return
        if not messagebox.askyesno('Instalar actualización', f'Descarga comprobada. Se guardará un respaldo de tus datos y ConXml se actualizará automáticamente a la versión {release.version}.\n¿Continuar?', parent=self.app):
            return
        self.app.guardar_sesion()
        self.app.ejecutar(lambda: respaldo_automatico(Config().base),
                          lambda result: self._install(release, path, result),
                          'Guardando respaldo antes de actualizar')

    def _install(self, release, path, result):
        if result.faltantes:
            if not messagebox.askyesno('Respaldo con XML faltantes', f'{len(result.faltantes)} XML ya no están en sus rutas originales. El respaldo registra los faltantes.\n¿Continuar con la actualización?', parent=self.app):
                return
        try:
            self.updater.apply_update(release, path)
        except (UpdateError, OSError) as exc:
            messagebox.showerror('Actualización', str(exc), parent=self.app)
            return
        self.app.master.destroy()
        sys.exit(0)
