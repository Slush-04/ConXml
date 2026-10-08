"""Control compacto de actualización. Todo Tk se ejecuta en el hilo principal."""
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
        self.progress_window = None
        self.progress_bar = None
        self.progress_label = None
        self.button = ctk.CTkButton(app, text='↻', width=32, height=28,
                                   fg_color=th.FONDO_ENTRADA, text_color=th.TEXTO,
                                   command=self.click)
        self.button.place(relx=1, x=-16, y=8, anchor='ne')
        self.tooltip = ctk.CTkLabel(app, text='Buscar actualización', fg_color=th.FONDO_ENTRADA)
        self.button.bind('<Enter>', self._show_tip)
        self.button.bind('<Leave>', lambda _: self.tooltip.place_forget())
        self.app.bind('<Destroy>', self._destroy, add='+')
        self.poll = app.after(100, self._poll)
        self.timer = app.after(2000, self.check)

    def _show_tip(self, _):
        self.tooltip.configure(text=f'Descargar ConXml {self.release.version}' if self.release else f'ConXml {__version__}: buscar actualización')
        self.tooltip.place(relx=1, x=-16, y=40, anchor='ne')

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
                self.button.configure(text='⬇' if release else '↻')
                if release:
                    self.app.registro(f'ConXml {release.version} disponible. Pulsa ⬇ para descargar.')
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
        self._mostrar_progreso('Descargando actualización', f'Preparando descarga de ConXml {release.version}…')
        iniciado = self.app.ejecutar(lambda progreso: self.updater.download(release, progreso),
                                     lambda path: self._downloaded(release, path),
                                     f'Descargando ConXml {release.version}', con_progreso=True)
        if not iniciado:
            self._cerrar_progreso()

    def _mostrar_progreso(self, titulo, texto, *, indeterminado=False):
        self._cerrar_progreso()
        try:
            self.button.configure(state='disabled')
            ventana = ctk.CTkToplevel(self.app)
            ventana.title(titulo)
            ventana.geometry('440x145')
            ventana.resizable(False, False)
            ventana.transient(self.app.winfo_toplevel())
            ventana.protocol('WM_DELETE_WINDOW', lambda: None)
            etiqueta = ctk.CTkLabel(ventana, text=texto, wraplength=400)
            etiqueta.pack(padx=20, pady=(24, 14))
            barra = ctk.CTkProgressBar(ventana, width=390, mode='indeterminate' if indeterminado else 'determinate')
            barra.pack(padx=20, pady=(0, 22))
            if indeterminado:
                barra.start()
            else:
                barra.set(0)
            ventana.update_idletasks()
            self.progress_window = ventana
            self.progress_bar = barra
            self.progress_label = etiqueta
        except Exception:
            self.progress_window = self.progress_bar = self.progress_label = None

    def _cerrar_progreso(self):
        ventana = getattr(self, 'progress_window', None)
        self.progress_window = self.progress_bar = self.progress_label = None
        try:
            self.button.configure(state='normal')
        except Exception:
            pass
        if ventana is not None:
            try:
                ventana.destroy()
            except Exception:
                pass

    def on_progreso(self, actual, total):
        if self.progress_window is None:
            return
        if total > 0:
            porcentaje = max(0, min(100, int(actual * 100 / total)))
            self.progress_label.configure(text=f'Descargando actualización: {porcentaje}%  ({actual / 1024**2:.1f} / {total / 1024**2:.1f} MB)')
            self.progress_bar.set(actual / total)

    def operacion_error(self, detalle):
        if self.progress_window is None:
            return False
        self._cerrar_progreso()
        causa = detalle.rstrip().splitlines()[-1] if detalle.strip() else 'Error desconocido.'
        messagebox.showerror('No se pudo actualizar ConXml', f'La operación no terminó. No se instalará un archivo incompleto.\n\n{causa}', parent=self.app)
        return True

    def _downloaded(self, release, path):
        self._cerrar_progreso()
        self.path = path
        if self.updater.demo or sys.platform != 'win32' or not getattr(sys, 'frozen', False):
            messagebox.showinfo('Prueba de actualización', f'Descarga y SHA-256 comprobados:\n{path}\n\nEn desarrollo/Mac no se ejecutan reemplazos de binarios Windows.', parent=self.app)
            return
        if not messagebox.askyesno('Instalar actualización', f'Descarga comprobada. Se guardará un respaldo de tus datos y ConXml se actualizará automáticamente a la versión {release.version}.\n¿Continuar?', parent=self.app):
            return
        self.app.guardar_sesion()
        self._mostrar_progreso('Preparando actualización', 'Guardando un respaldo de tus datos…', indeterminado=True)
        self.app.ejecutar(lambda: respaldo_automatico(Config().base),
                          lambda result: self._install(release, path, result),
                          'Guardando respaldo antes de actualizar')

    def _install(self, release, path, result):
        self._cerrar_progreso()
        if result.faltantes:
            if not messagebox.askyesno('Respaldo con XML faltantes', f'{len(result.faltantes)} XML ya no están en sus rutas originales. El respaldo registra los faltantes.\n¿Continuar con la actualización?', parent=self.app):
                return
        try:
            self.updater.apply_update(release, path)
        except (UpdateError, OSError) as exc:
            messagebox.showerror('Actualización', str(exc), parent=self.app)
            return
        self.app.master.destroy()
        raise SystemExit(0)
