"""Edición del calendario SAT por cliente, desde Configuración."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from datetime import datetime, timezone

import customtkinter as ctk

from conxml.catalog.db import Catalogo
from conxml.config import Config
from conxml.sat.periodicas import DIAS, guardar_plan, plan_predeterminado, planes, proximas, validar_plan
from conxml.sat.programador_sistema import instalar
from conxml.ui import theme as th
from conxml.ui.widgets import BarraAdaptable, BotonPrimario, BotonSecundario, PanelCard, texto_adaptable

TIPOS = {'Todos': '', 'Ingreso': 'I', 'Egreso': 'E', 'Traslado': 'T', 'Nómina': 'N', 'Pago': 'P'}


class ConfiguracionPeriodicaSAT(PanelCard):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._cliente = None
        contenido = ctk.CTkFrame(self, fg_color='transparent')
        contenido.pack(fill='x', padx=20, pady=18)
        ctk.CTkLabel(contenido, text='Descarga SAT periódica', font=(th.FUENTE, th.TAM_BODY, 'bold')).pack(anchor='w')
        self._cliente_lbl = ctk.CTkLabel(contenido, text='', anchor='w', text_color=th.TEXTO_SECUNDARIO)
        self._cliente_lbl.pack(fill='x', pady=(4, 8))
        self._activo = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(contenido, text='Activar para este cliente, incluso con ConXml cerrado',
                       variable=self._activo, font=(th.FUENTE, th.TAM_BODY)).pack(anchor='w', pady=(0, 12))
        self._horarios = {}
        for tarea, titulo in (('solicitar', 'Solicitar XML'), ('revisar', 'Revisar y organizar XML')):
            ctk.CTkLabel(contenido, text=titulo, font=(th.FUENTE, th.TAM_BODY, 'bold'), anchor='w').pack(fill='x', pady=(4, 6))
            barra = BarraAdaptable(contenido)
            barra.pack(fill='x', pady=(0, 10))
            variables = {'frecuencia': tk.StringVar(value='Semanal'), 'cada': tk.StringVar(value='1'),
                         'dia': tk.StringVar(value='Viernes'), 'hora': tk.StringVar(value='16:00')}
            self._horarios[tarea] = variables
            for etiqueta, clave, valores, ancho in (
                ('Frecuencia', 'frecuencia', ['Diario', 'Semanal'], 130),
                ('Cada (días / semanas)', 'cada', None, 140),
                ('Día de la semana', 'dia', DIAS, 130), ('Hora · 24 h', 'hora', None, 100),
            ):
                grupo = ctk.CTkFrame(barra, fg_color='transparent')
                ctk.CTkLabel(grupo, text=etiqueta, font=(th.FUENTE, th.TAM_NOTA), anchor='w').pack(fill='x')
                if valores:
                    entrada = ctk.CTkComboBox(grupo, variable=variables[clave], values=valores, width=ancho, state='readonly')
                else:
                    entrada = ctk.CTkEntry(grupo, textvariable=variables[clave], width=ancho)
                entrada.pack(fill='x', pady=(2, 0))
                barra.agregar(grupo)
            variables['frecuencia'].trace_add('write', lambda *_a, v=variables: self._cambiar_frecuencia(v))
            variables['entrada_dia'] = barra._elementos[2].winfo_children()[-1]
        opciones = BarraAdaptable(contenido)
        opciones.pack(fill='x', pady=(6, 12))
        self._dias = tk.StringVar(value='7')
        self._direccion = tk.StringVar(value='Ambos')
        self._tipo = tk.StringVar(value='Todos')
        self._zona = tk.StringVar(value='America/Merida')
        for etiqueta, variable, valores, ancho in (
            ('Días completos por solicitud', self._dias, None, 185),
            ('Dirección', self._direccion, ['Ambos', 'Emitidos', 'Recibidos'], 140),
            ('Tipo CFDI', self._tipo, list(TIPOS), 130),
            ('Zona horaria', self._zona, None, 190),
        ):
            grupo = ctk.CTkFrame(opciones, fg_color='transparent')
            ctk.CTkLabel(grupo, text=etiqueta, font=(th.FUENTE, th.TAM_NOTA), anchor='w').pack(fill='x')
            entrada = ctk.CTkComboBox(grupo, variable=variable, values=valores, state='readonly', width=ancho) if valores else ctk.CTkEntry(grupo, textvariable=variable, width=ancho)
            entrada.pack(fill='x', pady=(2, 0))
            opciones.agregar(grupo)
        nota = ctk.CTkLabel(
            contenido, text='La solicitud abarca los días completos anteriores al envío. El equipo debe estar encendido, '
            'con tu sesión iniciada y conexión a Internet. Autoriza la e.firma en Descargas SAT. '
            'El historial y sus paquetes temporales se eliminan a los 14 días de crear la solicitud; los XML de la bóveda se conservan.',
            wraplength=650, justify='left', anchor='w', text_color=th.TEXTO_SECUNDARIO,
            font=(th.FUENTE, th.TAM_NOTA),
        )
        nota.pack(fill='x', pady=(0, 12)); texto_adaptable(nota, contenido, margen=8)
        acciones = BarraAdaptable(contenido); acciones.pack(fill='x')
        self._btn_guardar = acciones.agregar(BotonPrimario(acciones, 'Guardar programación', self._guardar))
        acciones.agregar(BotonSecundario(acciones, 'Autorizar e.firma…', lambda: self.app.navegar('descargas')))
        self._estado = ctk.CTkLabel(contenido, text='', wraplength=650, justify='left', anchor='w', text_color=th.TEXTO_SECUNDARIO)
        self._estado.pack(fill='x', pady=(10, 0)); texto_adaptable(self._estado, contenido, margen=8)
        self.cargar()

    def _cambiar_frecuencia(self, variables):
        variables['entrada_dia'].configure(state='readonly' if variables['frecuencia'].get() == 'Semanal' else 'disabled')

    def cargar(self):
        self._cliente = getattr(self.app, 'cliente_actual', None)
        if not self._cliente:
            self._cliente_lbl.configure(text='Selecciona un cliente para configurar sus horarios.')
            self._btn_guardar.configure(state='disabled')
            return
        self._btn_guardar.configure(state='normal')
        config = Config()
        with Catalogo(getattr(self.app, 'db_path', config.db_path)) as cat:
            cliente = cat.obtener_cliente(self._cliente)
            ultimo = cat.conn.execute('SELECT estado,mensaje FROM sat_ejecuciones_periodicas WHERE cliente=? ORDER BY instante DESC LIMIT 1', (self._cliente,)).fetchone()
        self._cliente_lbl.configure(text=f"Cliente: {cliente['nombre'] if cliente else self._cliente}")
        plan = planes(config).get(self._cliente, plan_predeterminado())
        self._activo.set(plan['activo']); self._dias.set(str(plan['dias_xml']))
        self._direccion.set(plan['direccion']); self._zona.set(plan['zona'])
        self._tipo.set(next(nombre for nombre, valor in TIPOS.items() if valor == plan['tipo']))
        for tarea, variables in self._horarios.items():
            for clave in ('frecuencia', 'cada', 'hora'):
                variables[clave].set(str(plan[tarea][clave]))
            variables['dia'].set(DIAS[plan[tarea]['dia']])
        texto = 'Programación desactivada para este cliente.'
        if plan['activo']:
            textos = []
            for tarea, titulo in (('solicitar', 'Próxima solicitud'), ('revisar', 'Próxima revisión')):
                fecha = proximas(plan, tarea)
                textos.append(f'{titulo}: {DIAS[fecha.weekday()]} {fecha:%d/%m/%Y %H:%M}')
            texto = '\n'.join(textos)
        if ultimo:
            estados = {'completada': 'Completada', 'ejecutando': 'En curso', 'error': 'Error', 'sin_autorizacion': 'Falta autorizar e.firma'}
            texto += f'\nÚltima tarea: {estados.get(ultimo[0], ultimo[0])} · {ultimo[1]}'
        self._estado.configure(text=texto)

    def _guardar(self):
        if not self._cliente:
            return
        try:
            plan = {
                'activo': self._activo.get(), 'zona': self._zona.get().strip(),
                'dias_xml': int(self._dias.get()), 'direccion': self._direccion.get(), 'tipo': TIPOS[self._tipo.get()],
            }
            for tarea, variables in self._horarios.items():
                plan[tarea] = {'frecuencia': variables['frecuencia'].get(), 'cada': int(variables['cada'].get()),
                               'dia': DIAS.index(variables['dia'].get()), 'hora': variables['hora'].get().strip()}
            validar_plan(plan)
            config = Config()
            with Catalogo(getattr(self.app, 'db_path', config.db_path)) as cat:
                cliente = cat.obtener_cliente(self._cliente)
            if plan['activo'] and (not cliente or not cliente['rfc']):
                raise ValueError('Registra el RFC del cliente antes de activar la programación.')
            # Registrar primero: si falla el sistema, el plan todavía no queda activo.
            # Se conserva el ejecutor aun al pausar, para limpiar el historial vencido.
            instalar(config)
            guardar_plan(config, self._cliente, plan)
        except Exception as exc:
            messagebox.showerror('Programación SAT', str(exc), parent=self)
            return
        self.cargar()
        self._estado.configure(text='Programación guardada.\n' + self._estado.cget('text'))
