"""Vista previa local: PDF nativo en macOS, renderizado adaptable y zoom."""
from pathlib import Path
import math
import shutil
import tempfile
import sys
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
from PIL import Image, ImageTk
import pypdfium2 as pdfium
from conxml.ui import theme as th


class VisorPDF(ctk.CTkToplevel):
    def __init__(self, parent, ruta: Path):
        super().__init__(parent)
        self.ruta = ruta
        self.title('ConXml - Vista previa PDF')
        self.geometry('980x760')
        self.minsize(640, 480)
        self.doc = pdfium.PdfDocument(str(ruta))
        self.pagina = 0
        self._ajuste_after = None
        self._ancho_preview = 710
        self._zoom = 1.0
        self._cerrado = False
        self._temporales = tempfile.TemporaryDirectory(prefix='conxml-visor-')
        self.protocol('WM_DELETE_WINDOW', self._cerrar)
        barra = ctk.CTkFrame(self)
        barra.pack(fill='x', padx=12, pady=(12, 6))
        self.anterior = ctk.CTkButton(barra, text='Anterior', width=90, command=lambda: self._mover(-1))
        self.anterior.pack(side='left')
        self.indice = ctk.CTkLabel(barra, text='')
        self.indice.pack(side='left', padx=12)
        self.siguiente = ctk.CTkButton(barra, text='Siguiente', width=90, command=lambda: self._mover(1))
        self.siguiente.pack(side='left')
        ctk.CTkButton(barra, text='Guardar PDF…', command=self._guardar).pack(side='right')
        zoom = ctk.CTkFrame(self, fg_color="transparent")
        zoom.pack(fill='x', padx=12, pady=(0, 6))
        ctk.CTkButton(zoom, text='−', width=40, command=lambda: self._cambiar_zoom(-.25)).pack(side='left', padx=(0, 4))
        ctk.CTkButton(zoom, text='+', width=40, command=lambda: self._cambiar_zoom(.25)).pack(side='left')
        self.indice_zoom = ctk.CTkLabel(zoom, text='100%', width=60)
        self.indice_zoom.pack(side='left', padx=6)
        ctk.CTkButton(zoom, text='Ajustar ancho', width=120, command=self._ajustar_ancho).pack(side='left')
        self.scroll = ctk.CTkFrame(self)
        self.scroll.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        self.scroll.grid_rowconfigure(0, weight=1)
        self.scroll.grid_columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(self.scroll, background=th.BORDE, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(self.scroll, orient='vertical', command=self.canvas.yview)
        horizontal = ttk.Scrollbar(self.scroll, orient='horizontal', command=self.canvas.xview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.imagen = tk.Label(self.canvas, borderwidth=0, highlightthickness=0, background='white')
        self._imagen_id = self.canvas.create_window(8, 8, window=self.imagen, anchor='nw')
        self.canvas.bind('<Configure>', self._ajustar)
        for widget in (self.canvas, self.imagen):
            widget.bind('<MouseWheel>', self._rueda)
            widget.bind('<Shift-MouseWheel>', lambda e: self._rueda(e, horizontal=True))
            widget.bind('<Button-4>', lambda e: self.canvas.yview_scroll(-3, 'units'))
            widget.bind('<Button-5>', lambda e: self.canvas.yview_scroll(3, 'units'))
        self._mostrar()
        self.after(100, self.lift)

    def _mostrar(self):
        if self._cerrado:
            return
        page = self.doc[self.pagina]
        try:
            ancho_pagina, alto_pagina = page.get_size()
            ancho = max(1, round(self._ancho_preview * self._zoom * ctk.ScalingTracker.get_widget_scaling(self)))
            alto = max(1, round(ancho * alto_pagina / ancho_pagina))
            # Renderizar de nuevo al tamaño solicitado; nunca ampliar la miniatura.
            bitmap = page.render(scale=max(1.0, ancho * 2 / ancho_pagina))
            try:
                pil = bitmap.to_pil().resize((ancho, alto), Image.Resampling.LANCZOS)
                self._foto = ImageTk.PhotoImage(pil, master=self)
                self.imagen.configure(image=self._foto)
            finally:
                bitmap.close()
        finally:
            page.close()
        self.indice.configure(text=f'Página {self.pagina + 1} de {len(self.doc)}')
        self.indice_zoom.configure(text=f'{self._zoom:.0%}')
        self.anterior.configure(state='normal' if self.pagina else 'disabled')
        self.siguiente.configure(state='normal' if self.pagina + 1 < len(self.doc) else 'disabled')
        self.update_idletasks()
        izquierda = max(8, (self.canvas.winfo_width() - ancho) // 2)
        self.canvas.coords(self._imagen_id, izquierda, 8)
        self.canvas.configure(scrollregion=(0, 0, max(self.canvas.winfo_width(), ancho + 16), alto + 16))
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def _ajustar(self, event):
        ancho = max(300, math.floor((event.width - 24) / ctk.ScalingTracker.get_widget_scaling(self)))
        if ancho == self._ancho_preview or self._cerrado:
            return
        self._ancho_preview = ancho
        if self._ajuste_after:
            self.after_cancel(self._ajuste_after)
        self._ajuste_after = self.after(150, self._redibujar)

    def _redibujar(self):
        self._ajuste_after = None
        self._mostrar()

    def _cambiar_zoom(self, paso):
        self._zoom = min(3.0, max(.5, self._zoom + paso))
        self._mostrar()

    def _ajustar_ancho(self):
        self._zoom = 1.0
        self._mostrar()

    def _rueda(self, event, horizontal=False):
        if not event.delta:
            return 'break'
        paso = -int(event.delta / 120) if abs(event.delta) >= 120 else (-1 if event.delta > 0 else 1)
        (self.canvas.xview_scroll if horizontal else self.canvas.yview_scroll)(paso * 3, 'units')
        return 'break'

    def _mover(self, paso):
        self.pagina = min(len(self.doc) - 1, max(0, self.pagina + paso))
        self._mostrar()

    def _guardar(self):
        destino = filedialog.asksaveasfilename(parent=self, title='Guardar PDF', initialfile=self.ruta.name, defaultextension='.pdf', filetypes=[('PDF', '*.pdf')])
        if destino:
            try:
                if Path(destino).resolve() != self.ruta.resolve():
                    shutil.copy2(self.ruta, destino)
            except OSError as exc:
                messagebox.showerror('Guardar PDF', str(exc), parent=self)

    def _cerrar(self):
        self._cerrado = True
        if self._ajuste_after:
            self.after_cancel(self._ajuste_after)
        self.imagen.configure(bitmap='', image='')
        self.doc.close()
        self._temporales.cleanup()
        self.ruta.unlink(missing_ok=True)
        self.destroy()


def abrir_vista_previa(parent, ruta: Path):
    """PDFKit en macOS; visor Python en los demás sistemas."""
    if sys.platform == 'darwin':
        base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[3]))
        ejecutable = base / 'assets' / 'conxml-pdf-viewer' if getattr(sys, 'frozen', False) else base / 'build' / 'native' / 'conxml-pdf-viewer'
        if ejecutable.is_file():
            try:
                proceso = subprocess.Popen([str(ejecutable), str(ruta)])
            except OSError:
                return VisorPDF(parent, ruta)

            def comprobar():
                estado = proceso.poll()
                if estado is None:
                    parent.after(250, comprobar)
                elif estado == 0:
                    ruta.unlink(missing_ok=True)
                else:
                    VisorPDF(parent, ruta)
            parent.after(250, comprobar)
            return proceso
    return VisorPDF(parent, ruta)
