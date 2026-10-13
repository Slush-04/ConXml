"""Tabla de solo lectura con selección de celdas y páginas de 150 filas.

Mantiene los resultados completos para ordenar y operar sobre la vista filtrada,
pero entrega a tksheet únicamente la página actual.
"""
import tkinter as tk
from types import SimpleNamespace

import customtkinter as ctk
from tksheet import Sheet

from conxml.ui import theme as th


class TablaVisor(tk.Frame):
    TAM_PAGINA = 150

    def __init__(self, master, columns):
        super().__init__(master, bg=th.FONDO_TABLA)
        self._columnas = list(columns)
        self._visibles = list(columns)
        self._cabeceras = {c: {'text': c, 'command': None} for c in columns}
        self._anchos = {c: 120 for c in columns}
        self._filas = {}
        self._orden = []
        self._pagina = 0
        self._siguiente_id = 0
        self._orden_columna = None
        self._orden_desc = False
        self._pendiente = None
        self._acumulado_touchpad_x = 0
        self._acumulado_touchpad_y = 0
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.sheet = Sheet(
            self, data=[], headers=list(columns),
            show_row_index=False, show_top_left=False,
            show_default_header_for_empty=False,
            default_row_height=27, default_header_height=30,
            header_align='w', align='w', table_wrap='', header_wrap='',
            show_vertical_grid=True, table_grid_fg='#E4EAF1',
            header_grid_fg='#DDE5EF', header_border_fg='#DDE5EF',
            display_selected_fg_over_highlights=False,
            table_selected_cells_bg=th.PRIMARIO_FONDO,
            table_selected_cells_fg=th.PRIMARIO_TEXTO,
            table_selected_cells_border_fg=th.PRIMARIO,
            table_selected_rows_bg=th.PRIMARIO_FONDO,
            table_selected_rows_fg=th.PRIMARIO_TEXTO,
            table_selected_columns_bg=th.PRIMARIO_FONDO,
            table_selected_columns_fg=th.PRIMARIO_TEXTO,
            header_selected_columns_bg=th.PRIMARIO_FONDO,
            header_selected_columns_fg=th.PRIMARIO_TEXTO,
            font=('Arial', th.TAM_TABLA, 'normal'),
            header_font=('Arial', th.TAM_TABLA, 'bold'),
            table_bg=th.FONDO_TABLA, table_fg='#263246',
            header_bg='#E9EEF5', header_fg='#33465E',
            index_bg=th.FONDO_ENTRADA, index_fg=th.TEXTO,
            alternate_color='#F4F7FA',
        )
        self.sheet.enable_bindings('single_select', 'drag_select', 'row_select',
                                   'column_select', 'select_all', 'arrowkeys',
                                   'shift_select', 'ctrl_select', 'copy',
                                   'column_width_resize',
                                   'right_click_popup_menu')
        self.sheet.grid(row=0, column=0, sticky='nsew')
        self._activar_desplazamiento()
        self.sheet.CH.bind('<Double-1>', self.ordenar_cabecera, add='+')
        self.sheet.MT.bind('<Command-c>', lambda e: self.sheet.copy(e), add='+')
        barra = ctk.CTkFrame(self, fg_color=th.FONDO_ENTRADA, corner_radius=0)
        barra.grid(row=1, column=0, sticky='ew')
        estilo_boton = dict(width=96, height=28, corner_radius=6,
                            fg_color=th.FONDO_TABLA, hover_color=th.PRIMARIO_FONDO,
                            text_color=th.TEXTO, text_color_disabled=th.TEXTO_DISABLED,
                            border_width=1, border_color=th.BORDE,
                            font=(th.FUENTE, th.TAM_NOTA))
        self._anterior = ctk.CTkButton(barra, text='‹ Anterior',
                                     command=lambda: self.cambiar_pagina(-1), **estilo_boton)
        self._anterior.pack(side='left', padx=8, pady=6)
        self._estado = ctk.CTkLabel(barra, text='', text_color=th.TEXTO_SECUNDARIO,
                                   font=(th.FUENTE, th.TAM_NOTA))
        self._estado.pack(side='left', expand=True)
        self._siguiente = ctk.CTkButton(barra, text='Siguiente ›',
                                      command=lambda: self.cambiar_pagina(1), **estilo_boton)
        self._siguiente.pack(side='right', padx=8, pady=6)
        self._programar()

    def _activar_desplazamiento(self):
        """Dirige la rueda al eje de la tabla bajo el cursor.

        Shift + rueda permite mover columnas con trackpad o rueda convencional.
        Se devuelve ``break`` para que el contenedor exterior no consuma el gesto.
        """
        lienzos = (self.sheet.MT, self.sheet.CH, self.sheet.RI)
        for lienzo in lienzos:
            lienzo.bind('<MouseWheel>', self._desplazar_vertical)
            lienzo.bind('<Shift-MouseWheel>', self._desplazar_horizontal)
            # Rueda de Linux/X11. Los eventos Shift cubren el eje horizontal.
            lienzo.bind('<Button-4>', self._desplazar_vertical)
            lienzo.bind('<Button-5>', self._desplazar_vertical)
            lienzo.bind('<Shift-Button-4>', self._desplazar_horizontal)
            lienzo.bind('<Shift-Button-5>', self._desplazar_horizontal)
            # Tk 9 dejó de emitir MouseWheel para el gesto de dos dedos; el
            # evento nuevo conserva por separado el movimiento X e Y.
            if self.sheet.tk.call('info', 'commands', 'tk::PreciseScrollDeltas'):
                lienzo.bind('<TouchpadScroll>', self._desplazar_touchpad)

    @staticmethod
    def _unidades_rueda(event):
        numero = getattr(event, 'num', None)
        if numero in (4, 5):
            return -1 if numero == 4 else 1
        delta = getattr(event, 'delta', 0)
        if not delta:
            return 0
        # Windows suele enviar múltiplos de 120; macOS envía deltas pequeños.
        return -max(1, round(abs(delta) / 120)) if delta > 0 else max(1, round(abs(delta) / 120))

    def _desplazar_vertical(self, event):
        unidades = self._unidades_rueda(event)
        if unidades:
            self.sheet.MT.set_yviews('scroll', unidades, 'units')
        return 'break'

    def _desplazar_horizontal(self, event):
        unidades = self._unidades_rueda(event)
        if unidades:
            self.sheet.MT.set_xviews('scroll', unidades, 'units')
        return 'break'

    def _desplazar_touchpad(self, event):
        try:
            delta_x, delta_y = self.sheet.tk.call(
                'tk::PreciseScrollDeltas', int(event.delta)
            )
            delta_x, delta_y = float(delta_x), float(delta_y)
        except (TypeError, ValueError, tk.TclError):
            return 'break'

        # Tk entrega deltas de alta frecuencia en píxeles; la tabla desplaza
        # por unidades. Acumularlos evita saltar una fila por cada microgesto.
        self._acumulado_touchpad_x -= delta_x
        self._acumulado_touchpad_y -= delta_y
        pasos_x = int(self._acumulado_touchpad_x / 40)
        pasos_y = int(self._acumulado_touchpad_y / 27)
        if pasos_x:
            self._acumulado_touchpad_x -= pasos_x * 40
            self.sheet.MT.set_xviews('scroll', pasos_x, 'units')
        if pasos_y:
            self._acumulado_touchpad_y -= pasos_y * 27
            self.sheet.MT.set_yviews('scroll', pasos_y, 'units')
        return 'break'

    def _programar(self):
        if self._pendiente is None:
            self._pendiente = self.after_idle(self._renderizar)

    def _renderizar(self):
        self._pendiente = None
        paginas = max(1, (len(self._orden) + self.TAM_PAGINA - 1) // self.TAM_PAGINA)
        self._pagina = min(self._pagina, paginas - 1)
        ids = self.items_pagina()
        self.sheet.set_sheet_data([list(self._filas[i]['values']) for i in ids])
        self.sheet.headers([self._cabeceras[c]['text'] for c in self._columnas])
        self.sheet.display_columns([self._columnas.index(c) for c in self._visibles],
                                   all_columns_displayed=False, redraw=False)
        for i, c in enumerate(self._visibles):
            self.sheet.column_width(i, self._anchos[c], redraw=False)
        inicio = self._pagina * self.TAM_PAGINA + 1 if ids else 0
        self._aplicar_lectura(ids)
        self.sheet.set_options(copy_label="Copiar", select_all_label="Seleccionar todo")
        self.sheet.refresh()
        self._estado.configure(text=f'{inicio}–{inicio + len(ids) - 1 if ids else 0} de {len(self._orden):,} · Página {self._pagina + 1} de {paginas}')
        self._anterior.configure(state='normal' if self._pagina else 'disabled')
        self._siguiente.configure(state='normal' if self._pagina + 1 < paginas else 'disabled')

    def _aplicar_lectura(self, ids):
        """Formato visual sin modificar los valores copiados o exportados."""
        importes = {'subtotal', 'descuento', 'total', 'monto', 'pagado',
                    'saldo_pendiente', 'saldo_insoluto', 'saldo_anterior',
                    'total_factura', 'imp_saldo_ant', 'imp_pagado', 'imp_saldo_insoluto'}
        self.sheet.dehighlight_all(redraw=False)
        for indice, clave in enumerate(self._columnas):
            es_importe = clave in importes or clave.startswith(
                ('total_', 'monto_', 'iva_', 'isr_', 'ieps_', 'ret_'))
            self.sheet.align_columns(indice, align='e' if es_importe else 'w', redraw=False)
            if clave == 'estatus':
                for fila, iid in enumerate(ids):
                    valor = str(self._filas[iid]['values'][indice]).strip().casefold()
                    if valor == 'cancelado':
                        self.sheet.highlight_cells(fila, indice, fg=th.ROJO, redraw=False)

    def items_pagina(self):
        inicio = self._pagina * self.TAM_PAGINA
        return self._orden[inicio:inicio + self.TAM_PAGINA]

    def cambiar_pagina(self, delta):
        limite = max(0, (len(self._orden) - 1) // self.TAM_PAGINA)
        self._pagina = max(0, min(limite, self._pagina + delta))
        self.sheet.deselect('all')
        self.sheet.set_yview(0)
        self._programar()

    def __getitem__(self, key):
        if key == 'columns':
            return tuple(self._columnas)
        if key == 'displaycolumns':
            return tuple(self._visibles)
        return super().__getitem__(key)

    def configure(self, cnf=None, **kw):
        if 'columns' in kw:
            self._columnas = list(kw.pop('columns'))
            self._visibles = list(self._columnas)
            for c in self._columnas:
                self._cabeceras.setdefault(c, {'text': c, 'command': None})
                self._anchos.setdefault(c, 120)
        if 'displaycolumns' in kw:
            cols = kw.pop('displaycolumns')
            self._visibles = list(self._columnas if cols == '#all' else cols)
        if cnf or kw:
            super().configure(cnf, **kw)
        self._programar()

    # CTk registra el configure del padre a través de su alias config.
    config = configure

    def heading(self, column, **kw):
        if kw:
            self._cabeceras[column].update(kw)
            self._programar()
        return self._cabeceras[column]

    def column(self, column, option=None, **kw):
        if 'width' in kw:
            self._anchos[column] = kw['width']
            self._programar()
        opciones = {'width': self._anchos[column]}
        return opciones[option] if option else opciones

    def insert(self, parent, index, *, values=(), tags=(), iid=None):
        self._siguiente_id += 1
        iid = str(iid) if iid is not None else str(self._siguiente_id)
        if iid in self._filas:
            raise ValueError(f"Fila repetida: {iid}")
        self._filas[iid] = {'values': tuple(values), 'tags': tags}
        self._orden.append(iid)
        self._programar()
        return iid

    def get_children(self):
        return tuple(self._orden)

    def delete(self, *items):
        eliminados = set(items)
        self._orden = [i for i in self._orden if i not in eliminados]
        for i in items:
            self._filas.pop(i, None)
        self._pagina = 0
        self._programar()

    def item(self, item, option=None):
        return self._filas[item][option] if option else self._filas[item]

    def set(self, item, column):
        return self._filas[item]['values'][self._columnas.index(column)]

    def ordenar(self, ids):
        self._orden = list(ids)
        self._pagina = 0
        self._programar()

    def selection(self):
        ids = self.items_pagina()
        rows = set(self.sheet.get_selected_rows(get_cells_as_rows=True))
        rows.update(r for r, c in self.sheet.get_selected_cells(get_columns=True))
        return tuple(ids[r] for r in sorted(rows) if r < len(ids))

    def selection_set(self, item):
        self.see(item)
        self.sheet.select_row(self.items_pagina().index(item))

    def selection_remove(self, *items):
        self.sheet.deselect('all')

    def see(self, item):
        pagina = self._orden.index(item) // self.TAM_PAGINA
        if pagina != self._pagina or self._pendiente is not None:
            self._pagina = pagina
            if self._pendiente is not None:
                self.after_cancel(self._pendiente)
            self._renderizar()
        self.sheet.see(row=self.items_pagina().index(item))

    def bind(self, sequence=None, func=None, add=None):
        if sequence in ('<Double-1>', '<Button-2>', '<Button-3>'):
            return self.sheet.MT.bind(sequence, func, add='+')
        return super().bind(sequence, func, add)

    def focus(self, item=None):
        if item is not None:
            self.see(item)
            self.focus_set()
        seleccion = self.selection()
        return seleccion[0] if seleccion else ""

    def focus_set(self):
        self.sheet.MT.focus_set()

    def identify_row(self, y):
        row = self.sheet.identify_row(SimpleNamespace(widget=self.sheet.MT, y=y), allow_end=False)
        ids = self.items_pagina()
        return ids[row] if row is not None and 0 <= row < len(ids) else ''

    def identify_region(self, x, y):
        return 'cell' if self.identify_row(y) else ''

    def bbox(self, item):
        r = self.items_pagina().index(item)
        positions = self.sheet.MT.row_positions
        return (0, int(positions[r] - self.sheet.MT.canvasy(0)), self.sheet.MT.winfo_width(), int(positions[r+1] - positions[r]))

    def ordenar_cabecera(self, event):
        col = self.sheet.identify_column(event, allow_end=False)
        if col is not None and col < len(self._visibles):
            comando = self._cabeceras[self._visibles[col]]['command']
            if comando:
                comando()
            else:
                clave = self._visibles[col]
                self._orden_desc = not self._orden_desc if clave == self._orden_columna else False
                self._orden_columna = clave
                indice = self._columnas.index(clave)
                def valor(iid):
                    dato = str(self._filas[iid]['values'][indice] or '')
                    try:
                        return (1, float(dato))
                    except ValueError:
                        return (0, dato.casefold())
                self.ordenar(sorted(self._orden, key=valor, reverse=self._orden_desc))
