# Implementar interfaz adaptable para laptops Mac y Windows

Problema: ventana fija inicial 1020x680, sidebar 240px, encabezados sin wrap,
paneles de totales extensos, registro y detalles restan altura a las tablas.
El usuario quiere leer los CFDI en laptops y diferentes tamaños de pantalla.

Implementa el cambio, no solo una propuesta, sobre esta copia del código.
Alcance: src/conxml/ui/*.py, tests/test_ui_responsive.py (nuevo), README.md.
No cambiar rutas de datos, parser, importador, SAT ni reportes.

Criterios:
- Tamaño inicial según espacio de pantalla y escalado CustomTkinter. No forzar
  una ventana mayor que la pantalla. Usar APIs públicas y evitar zoom dependiente
  de Windows. Mantener tamaño mínimo práctico para laptop.
- Adaptar al tamaño de ventana en eventos Configure con debounce y filtrando
  eventos de hijos. No recrear tablas ni perder selección/datos al redimensionar.
- En ventana estrecha, sidebar compacto con navegación accesible (etiquetas
  breves legibles, no solo emojis); recuperar sidebar ancho al ampliar.
- En poca altura, ocultar registro y colapsar automáticamente los totales
  para dar prioridad a la tabla. Debe haber controles visibles para volver a
  mostrar los totales y detalles; no reabrirlos involuntariamente al operar.
- Usar encabezados que envuelvan texto al ancho disponible, márgenes compactos
  y botones/controles que no queden recortados. Contemplar CFDI, nómina y pagos.
- Evitar que el selector de vistas REP demasiado ancho empuje el botón Columnas
  fuera de pantalla; usar ComboBox si hace falta.
- Scroll horizontal y vertical siempre accesible; no comprimir las 47 columnas
  ni achicar fuentes hasta perder legibilidad. El usuario navegará por columnas.
- Objetivos de comprobación: 900x650, 1024x768, 1366x768, 1440x900 y 1920x1080;
  tabla con al menos 150px de altura en modo compacto y botones dentro de ventana.
- Añadir pruebas de geometría reales de Tk/CTk con skip explícito cuando falta
  display, datos temporales, ventanas destruidas al finalizar; no usar SAT real.
  No ejecutar comandos: Codex instala dependencias y ejecuta pruebas luego.
- Cambios simples mantenibles, no reescribir toda la interfaz.

Leer primero ui/app.py, ui/pantalla_admin.py, ui/widgets.py y ui/theme.py.
Entrega cambios y una explicación breve; no declares pruebas ejecutadas.
