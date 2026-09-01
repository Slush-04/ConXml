# Plan de Rediseño — ConXml UI · Fluent Empresarial

## Objetivo

Reemplazar el diseño actual (vidrio/glassmorphism + índigo) por una interfaz
**sólida, limpia y empresarial** inspirada en Windows 11 Fluent Design sin transparencias,
estilo Notion / Linear. La estructura de pantallas se mantiene igual.

---

## Correcciones Críticas de Layout (Espacios Vacíos)

> [!IMPORTANT]
> Estos son los problemas visuales más urgentes identificados en producción.
> Deben resolverse aunque sea lo único que se cambie.

### Problema 1 — Sidebar: Frames Intermedios Visibles

**Causa**: Cada botón de navegación se envuelve en un `CTkFrame(fg_color="transparent")`
para alojar el indicador lateral. En ciertas versiones de CTk ese frame renderiza
un rectángulo blanco/gris visible aunque el color sea "transparent".

**Solución**: Eliminar los frames contenedores intermedios de la sidebar. Usar
en su lugar un `Canvas` de 3×30 px que se dibuja directamente (o simplemente
colocar el indicador y el botón como hijos directos del frame de navegación con
`grid` en dos columnas).

```
# Layout correcto para cada ítem de navegación:
nav_frame.columnconfigure(0, minsize=4)   # columna del indicador (ancho fijo)
nav_frame.columnconfigure(1, weight=1)    # columna del botón

indicador = CTkFrame(nav_frame, width=4, height=32,
                    fg_color="transparent", corner_radius=2)
indicador.grid(row=i, column=0, sticky="ns", padx=(4,0), pady=1)

boton = CTkButton(nav_frame, ...)
boton.grid(row=i, column=1, sticky="ew", pady=1, padx=(0,6))
```

El indicador cambia `fg_color` al color activo cuando la pantalla está seleccionada.
**No se usa** ningún frame contenedor adicional.

---

### Problema 2 — KPI Cards: Altura Inflada por `place()`

**Causa**: El ícono decorativo de fondo se coloca con `.place(relx=1.0, rely=0.5)`
dentro del frame de contenido. Tkinter/CTk cuenta el espacio del widget colocado
con `place` en el cálculo del tamaño del frame padre, inflando la altura.

**Solución**: **Eliminar completamente el ícono decorativo** de las tarjetas KPI.
El nuevo diseño Fluent/empresarial es más limpio sin él. La tarjeta debe tener
altura determinada solo por su contenido (etiqueta + valor).

```
# Layout correcto de Metrica:
barra lateral 4px (pack side=left, fill=y)
contenido (pack side=left, fill=both, expand=True, padx=14, pady=10):
  CTkLabel etiqueta  TAM_NOTA, TEXTO_SECUNDARIO, anchor=w
  CTkLabel valor     TAM_H1,  color_tono,       anchor=w
```

Altura resultante: ~72 px (compacta, sin espacio muerto).
No se usa `place()` en ninguna éutica de `Metrica`.

---

### Problema 3 — KPI Cards: Sombra con `place()` al 100% rely

**Causa**: El frame de sombra se coloca en `rely=1.0` (fuera del borde inferior
del widget), lo que también contribuye a inflar la altura calculada por el padre.

**Solución**: **Eliminar los frames de sombra** (no se usan en el nuevo diseño
Flat/Fluent). Sustituir por simplemente `border_width=1, border_color=BORDE`.

---

## Sistema de Diseño

### Paleta de Colores

| Token | Valor | Uso |
|---|---|---|
| `PRIMARIO` | `#2563EB` | Botones primarios, indicadores activos, acento |
| `PRIMARIO_HOVER` | `#1D4ED8` | Estado hover del primario |
| `PRIMARIO_FONDO` | `#EFF6FF` | Fondo de badges azules, hover suave |
| `PRIMARIO_TEXTO` | `#1E40AF` | Texto sobre fondo azul claro |
| `FONDO` | `#F8FAFC` | Fondo de la ventana (gris casi blanco) |
| `FONDO_TARJETA` | `#FFFFFF` | Fondo de cards y paneles |
| `FONDO_SIDEBAR` | `#1E293B` | Sidebar oscura fija (slate-800) |
| `FONDO_TABLA` | `#FFFFFF` | Fondo de Treeview |
| `FONDO_ENTRADA` | `#F1F5F9` | Fondo de inputs / entradas de texto |
| `BORDE` | `#E2E8F0` | Bordes de cards y separadores |
| `BORDE_FOCUS` | `#2563EB` | Borde de inputs al tener foco |
| `TEXTO` | `#0F172A` | Texto principal (casi negro) |
| `TEXTO_SECUNDARIO` | `#475569` | Etiquetas, subtítulos, hints |
| `TEXTO_DISABLED` | `#94A3B8` | Texto desactivado |
| `VERDE` | `#16A34A` | Estatus Vigente |
| `VERDE_FONDO` | `#F0FDF4` | Fondo badge Vigente |
| `ROJO` | `#DC2626` | Estatus Cancelado |
| `ROJO_FONDO` | `#FEF2F2` | Fondo badge Cancelado |
| `AMBAR` | `#D97706` | Estatus Sin Validar |
| `AMBAR_FONDO` | `#FFFBEB` | Fondo badge Sin Validar |
| `GRIS` | `#64748B` | Estatus neutral / no encontrado |
| `GRIS_FONDO` | `#F8FAFC` | Fondo badge gris |

> **Sin tuplas (claro, oscuro)**: la app es solo modo claro. Todos los tokens son
> cadenas `str` simples. Esto simplifica el código y elimina toda la lógica de
> resolución de modos.

---

### Tipografía — Segoe UI Variable

```
Fuente principal : "Segoe UI Variable"  (con fallback "Segoe UI")
Fuente consola   : "Cascadia Code"      (con fallback "Consolas")
```

| Rol | Variable | Tamaño | Peso |
|---|---|---|---|
| Título de pantalla / KPI valor | `TAM_H1` | `22` | `bold` |
| Subtítulo de sección | `TAM_H2` | `15` | `bold` |
| Título de tarjeta | `TAM_H3` | `13` | `bold` |
| Texto de cuerpo | `TAM_BODY` | `12` | `normal` |
| Notas, labels, badges | `TAM_NOTA` | `11` | `normal` |

**Regla de contraste**: todo texto principal (`TEXTO`) sobre `FONDO_TARJETA` debe
superar WCAG AA (ratio ≥ 4.5:1). `#0F172A` sobre `#FFFFFF` = 19.6:1 ✅.

---

### Radios de Esquina

| Token | Valor | Uso |
|---|---|---|
| `RADIO_PANEL` | `8` | PanelVidrio → ahora `PanelCard` |
| `RADIO_TARJETA` | `8` | Cards, toolbars |
| `RADIO_BOTON` | `6` | Todos los botones |
| `RADIO_CAMPO` | `6` | Inputs, combo boxes |
| `RADIO_BADGE` | `50` | Badges/insignias (cápsula) |
| `RADIO_GRUPO` | `5` | Botones de navegación sidebar |

**Sin sombras pronunciadas**: sombra máxima de `0 1px 3px rgba(0,0,0,0.10)` simulada
con bordes de 1px de `BORDE`. No se usarán frames superpuestos para sombras.

---

## Cambios por Archivo

### `theme.py` — REESCRIBIR COMPLETO

- Eliminar toda la sección de Vidrio / Glassmorphism (tokens `VIDRIO_*`, `TINTE_*`, `TRANSPARENTE`)
- Eliminar la importación de `vidrio.py`
- Paleta de modo único (strings simples, no tuplas)
- Escala tipográfica con fallback:
  ```python
  FUENTE = "Segoe UI Variable" if _tiene_fuente("Segoe UI Variable") else "Segoe UI"
  ```
- Función `_tiene_fuente(nombre)` que usa `tkinter.font.families()`
- Mantener `configurar_ctk()` pero setear solo `appearance_mode = "Light"` (fijo, no System)

---

### `vidrio.py` — NO MODIFICAR

Mantener el archivo tal como está (puede ser usado en otros proyectos del workspace).
Los componentes simplemente dejarán de importarlo.

---

### `widgets.py` — REESCRIBIR COMPLETO

**Eliminar**:
- `BrilloMixin` (no más sheen/brillo especular)
- `PanelVidrio` (reemplazado por `PanelCard`)
- `Card` (fusionado con `PanelCard`)

**Nuevo componente `PanelCard`**:
```
CTkFrame con:
  fg_color   = FONDO_TARJETA (#FFFFFF)
  border_width = 1
  border_color = BORDE (#E2E8F0)
  corner_radius = RADIO_TARJETA (8)
```

**`BotonPrimario`** — sólido, sin bordes brillantes:
```
fg_color    = PRIMARIO (#2563EB)
hover_color = PRIMARIO_HOVER (#1D4ED8)
text_color  = #FFFFFF
border_width = 0
height      = 36
corner_radius = RADIO_BOTON (6)
font        = (FUENTE, TAM_BODY, "bold")
```

**`BotonSecundario`** — outline style:
```
fg_color    = FONDO_TARJETA (#FFFFFF)
hover_color = PRIMARIO_FONDO (#EFF6FF)
text_color  = PRIMARIO (#2563EB)
border_width = 1
border_color = BORDE (#E2E8F0)
height      = 36
```

**`Metrica`** — card KPI limpia:
```
Layout vertical dentro de PanelCard:
  Fila superior: [barra lateral 3px de color semántico] | [contenido]
  Etiqueta: TAM_NOTA, TEXTO_SECUNDARIO, uppercase
  Valor: TAM_H1 bold, color semántico del tono
  Sin ícono decorativo de fondo (demasiado ruido visual)
```

**`TarjetaAccion`** — card simple con hover de borde:
```
PanelCard base
  hover: border_color cambia a PRIMARIO (sin aumentar border_width)
  Franja superior de 3px con color PRIMARIO
  Botón "Ir →" como BotonSecundario
```

**`Insignia`** — badge cápsula:
```
fg_color   = tono_fondo
text_color = tono_color
font       = (FUENTE, TAM_NOTA, "bold")
corner_radius = RADIO_BADGE (50)
padx = 10, pady = 3
```

**`Encabezado`** — título + subtítulo + línea divisoria:
```
CTkLabel título: TAM_H2, TEXTO, bold
CTkLabel subtítulo: TAM_BODY, TEXTO_SECUNDARIO
CTkFrame separador: height=1, BORDE, fill=X, pady=(10,0)
```

**`ResumenOperacion`** (toast de resultado):
```
Sin fg_color base (transparent)
Cuando hay tono: fg=tono_fondo, border_width=1, border_color=tono_color, corner_radius=8
Ícono de estado al inicio de la línea (✅ ⚠️ ❌)
```

**`FilaArchivo`**:
```
CTkEntry con placeholder_text, fg_color=FONDO_ENTRADA, border_color=BORDE
```

---

### `app.py` — MODIFICAR (estructura mantenida)

**Eliminar**:
- Import de `vidrio`
- Lógica de `vidrio.aplicar_efecto`, `vidrio.reaplicar_efecto`, `vidrio.TRANSPARENTE`
- `PanelVidrio` → reemplazar por `PanelCard`
- Grid con `padx=16, pady=16` alrededor → `padx=0, pady=0` (sin "marco difuminado")

**Ventana raíz**:
```python
raiz = ctk.CTk()
raiz.configure(fg_color=FONDO)   # #F8FAFC, sin transparencias
```

**Sidebar** (estructura se mantiene, colores actualizados):
```
fg_color      = FONDO_SIDEBAR (#1E293B)  ← Slate-800, no cambia
corner_radius = 0  (sin bordes redondeados en el sidebar)
Botones nav activos: fg = #2563EB (primario) para el indicador lateral
Botones nav inactivos: text_color = #94A3B8
```

**Logo CX**: se mantiene el círculo con `#2563EB` (azul Royal Blue).

**Área de contenido**:
```
Usar PanelCard con fg_color=FONDO (#F8FAFC) como contenedor
```

**Consola de bitácora**:
```
fg_color del marco = FONDO_TARJETA (#FFFFFF), border=1px BORDE
ScrolledText: background=FONDO_ENTRADA (#F1F5F9), foreground=TEXTO (#0F172A)
  tag "comando": foreground=#2563EB, bold
  tag "exito"  : foreground=#16A34A
  tag "error"  : foreground=#DC2626
  tag "detalle": foreground=#475569
  tag "nota"   : foreground=#64748B
```

---

### `pantalla_admin.py` — MODIFICAR

**Eliminar**: `_resolver()` y toda lógica de resolución de modos.

**Tabla Treeview** (estilo Fluent):
```python
estilo.configure("Tabla.Treeview",
    background     = FONDO_TABLA,    # #FFFFFF
    fieldbackground = FONDO_TABLA,
    foreground     = TEXTO,           # #0F172A
    rowheight      = 28,
    font           = (FUENTE, TAM_BODY),
)
estilo.configure("Tabla.Treeview.Heading",
    background = FONDO,              # #F8FAFC
    foreground = TEXTO_SECUNDARIO,   # #475569
    relief     = "flat",
    font       = (FUENTE, TAM_NOTA, "bold"),
)
```

Tags de estatus SAT (mismo esquema que antes):
```python
tag "vigente"      → foreground=VERDE  (#16A34A), bold
tag "cancelado"    → foreground=ROJO   (#DC2626), bold
tag "sin_validar"  → foreground=AMBAR  (#D97706)
tag "no_encontrado"→ foreground=GRIS   (#64748B)
```

Zebra striping:
```python
tag "par"   → background=FONDO_TABLA    (#FFFFFF)
tag "impar" → background=FONDO_ENTRADA  (#F1F5F9)
```

**Toolbar** (se mantiene como PanelCard):
```
PanelCard fg_color=FONDO_TARJETA, border=1px BORDE, corner_radius=8
```

---

### `pantalla_resumen.py` — MODIFICAR

**Hero Section**:
```
Saludo dinámico: TAM_NOTA, TEXTO_SECUNDARIO
Título principal: TAM_H1 (22px), bold, TEXTO (#0F172A)
Subtítulo: TAM_BODY, TEXTO_SECUNDARIO
Separador 1px BORDE debajo
```

**Labels de sección** ("RESUMEN DEL CATÁLOGO", "¿QUÉ QUIERES HACER?"):
```
TAM_NOTA, bold, TEXTO_SECUNDARIO — en mayúsculas para jerarquía sutil
```

---

## Qué NO debe hacer el código

> [!CAUTION]
> - **No usar tuplas `(claro, oscuro)`** para colores — todos son `str` simples.
> - **No importar `vidrio`** en ningún archivo de UI.
> - **No crear frames de sombra** superpuestos (`place` para sombras) — solo bordes.
> - **No usar `BrilloMixin`** ni `_actualizar_brillo`.
> - **No sobreescribir `_draw()`** en ningún widget — sin hacks de Canvas.
> - **No usar `ctk.set_appearance_mode("System")`** — siempre `"Light"`.
> - **No usar `con_alfa()`** — ya no hay mezcla de colores semitransparente.
> - **No usar `place()` dentro de widgets de contenido** — causa inflado de altura en frames CTk.
> - **No crear `CTkFrame` intermedios en la sidebar** para contener indicador + botón. Usar `grid` directo en 2 columnas.
> - **No añadir frames de sombra** con `place(relx=x, rely=1.0)` — el frame se infla.

---

## Archivos a Modificar

| Archivo | Acción |
|---|---|
| [`theme.py`](file:///c:/Users/CCP%20Servicio/Documents/EDUARDO_NAH/ConXml/src/conxml/ui/theme.py) | **REESCRIBIR** completamente |
| [`widgets.py`](file:///c:/Users/CCP%20Servicio/Documents/EDUARDO_NAH/ConXml/src/conxml/ui/widgets.py) | **REESCRIBIR** completamente |
| [`app.py`](file:///c:/Users/CCP%20Servicio/Documents/EDUARDO_NAH/ConXml/src/conxml/ui/app.py) | **MODIFICAR** — quitar vidrio, actualizar colores |
| [`pantalla_admin.py`](file:///c:/Users/CCP%20Servicio/Documents/EDUARDO_NAH/ConXml/src/conxml/ui/pantalla_admin.py) | **MODIFICAR** — tabla y toolbar |
| [`pantalla_resumen.py`](file:///c:/Users/CCP%20Servicio/Documents/EDUARDO_NAH/ConXml/src/conxml/ui/pantalla_resumen.py) | **MODIFICAR** — hero section |
| [`vidrio.py`](file:///c:/Users/CCP%20Servicio/Documents/EDUARDO_NAH/ConXml/src/conxml/ui/vidrio.py) | **NO TOCAR** |

---

## Criterio de Aceptación (Auditoría)

Una vez que la IA delegada genere el código, yo verificaré:

1. **`pytest -q`** → 62 passed, 0 failed
2. **Imports limpios**: ningún archivo de UI importa `vidrio`
3. **Sin tuplas de color**: `grep -r "(\"#" src/conxml/ui/` → 0 resultados en tokens de color
4. **`conxml.exe` compila** sin errores con `PyInstaller --noconfirm --clean conxml.spec`
5. **Visual — Sidebar**: no hay rectángulos vacios entre los botones de navegación
6. **Visual — KPI Cards**: la altura de cada card es compacta (~70-80 px), sin espacio muerto en la parte inferior
7. **Visual — Tabla**: columna Estatus muestra texto verde/rojo/ámbar según valor SAT
8. **Sin `place()` en widgets**: `grep -rn "\.place(" src/conxml/ui/widgets.py` → 0 resultados
