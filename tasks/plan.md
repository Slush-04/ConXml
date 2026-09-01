# Plan de Implementación: Migración de la UI de Tkinter/ttk a CustomTkinter

> El plan del MVP terminado quedó preservado en `tasks/plan-mvp.md` y `tasks/todo-mvp.md`.

## Overview

Migrar la interfaz gráfica de ConXml de **Tkinter/ttk** a **CustomTkinter (CTK)**. CTK está construido sobre Tkinter: la lógica de distribución (`grid`, `pack`, `place`), las variables (`StringVar`, `BooleanVar`) y los eventos se mantienen iguales. El cambio está en (1) las clases de widgets, (2) la eliminación de `ttk.Style` en `theme.py`, y (3) los colores como tuplas `(claro, oscuro)` para soporte nativo de modo claro/oscuro siguiendo al sistema.

**Alcance:** solo las pantallas activas de la app (`resumen`, `admin40`, `pagos`). Las 3 pantallas no conectadas a `app.py` (`pantalla_estatus`, `pantalla_importar`, `pantalla_exportar`) se eliminan por ser código muerto.

## Architecture Decisions

- **CTK sustituye a ttk, no a Tkinter.** Se mantienen `grid`/`pack`/`place`, `after`, `StringVar`/`BooleanVar`, `filedialog` y `messagebox`. Se elimina `ttk.Style` y todos los estilos (`TButton`, `TLabel`, `Card.TFrame`, etc.).
- **Colores como tuplas `(claro, oscuro)`.** `ctk.set_appearance_mode("System")` hace que el área de contenido siga a Windows. La **sidebar se mantiene siempre oscura** (constantes fijas `SIDEBAR_*`), patrón típico de escritorio que conserva el contraste actual.
- **La tabla (`ttk.Treeview`) se conserva.** CTK no tiene tabla nativa. Se mantiene `ttk.Treeview` + `CTkScrollbar` dentro de un `CTkFrame`, estilizada en el arranque según el modo de apariencia vigente. Limitación aceptada: no se re-themea en caliente al cambiar el modo de Windows.
- **La consola de registro (`tkinter.scrolledtext.ScrolledText`) se conserva.** CTK no tiene widget de texto multilínea; se embebe en un `CTkFrame` oscuro con esquinas redondeadas.
- **El hover de `TarjetaAccion` se simplifica.** CTkFrame no tiene hover nativo (eso es de `CTkButton`), pero con hijos de `fg_color="transparent"` el hover se reduce a 2 `configure` (frame `fg_color` + `border_color`) en lugar de la recursión actual `_cambiar_fondo_hijos`.
- **Threading + cola de mensajes intactos.** `app.ejecutar`/`_procesar_cola` no se tocan; solo cambia la capa de widgets. `botones` sigue siendo la lista de widgets a deshabilitar durante una operación.
- **PyInstaller: hook oficial de CTK.** Desde CTK 5.x el paquete trae su hook de PyInstaller para los assets; `conxml.spec` no debería requerir cambios, se verifica en el build (Task 8).
- **Fuentes y DPI sin cambios.** Se mantienen `("Segoe UI", tamaño, peso)` (CTK acepta tuplas de fuente) y la llamada `SetProcessDpiAwareness` en `main()`.

## Task List

### Fase 1: Fundamentos
- [x] Task 1: Instalar `customtkinter` y declararlo en `pyproject.toml` + smoke test de la UI
- [x] Task 2: Migrar `theme.py` de `ttk.Style` a tokens de color CTK

### Checkpoint 1: Fundamentos
- [x] `python -m pytest` pasa (59 tests existentes + smoke nuevo)
- [x] `customtkinter` instalado en `.venv` y `conxml.ui.theme` importable
- [ ] Revisión con humano antes de continuar

### Fase 2: Componentes base y ventana principal
- [x] Task 3: Migrar `widgets.py` (8 componentes reutilizables)
- [x] Task 4: Migrar `app.py` y `ui_main.py` (ventana, sidebar, navegación, consola)

### Checkpoint 2: La app arranca
- [x] `python -m conxml.ui_main` abre la ventana sin errores
- [x] Navegación Resumen / XML 4.0 / Pagos alterna pantallas y resalta el ítem activo
- [x] Consola y colores se ven correctos en claro y oscuro
- [ ] Revisión con humano

### Fase 3: Pantallas activas
- [x] Task 5: Migrar `pantalla_resumen.py`
- [x] Task 6: Migrar `pantalla_admin.py` (2 modos: cfdi40 y pagos)

### Checkpoint 3: Flujos end-to-end
- [x] Resumen muestra métricas e insignias reales del catálogo
- [x] En cfdi40 y pagos: leer carpeta → tabla → validar SAT (con progreso) → exportar Excel
- [x] Botones se deshabilitan durante la operación y se restauran al terminar
- [ ] Revisión con humano

### Fase 4: Limpieza y empaquetado
- [x] Task 7: Eliminar las 3 pantallas no conectadas
- [x] Task 8: Reconstruir ejecutables con PyInstaller y verificar el `.exe`

### Checkpoint Final
- [x] `dist\conxml.exe` arranca y las 3 pantallas se ven con el tema esperado (claro y oscuro)
- [x] `dist\conxml-cli.exe` sigue funcionando
- [x] Todos los tests pasan
- [ ] Revisión final con humano antes de declarar la migración completa

## Risks and Mitigations

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| `ttk.Treeview` no se adapta al modo oscuro en caliente | Bajo | Estilo aplicado en el arranque según el modo vigente; limitación documentada y aceptada |
| CTkFrame no tiene hover nativo para las tarjetas | Bajo | Binds `<Enter>`/`<Leave>` con 2 `configure` por evento; hijos con `fg_color="transparent"` |
| PyInstaller no empaqueta los assets de CTK | Medio | CTK ≥5.2 trae hook oficial; verificar en Task 8; añadir `hiddenimports`/`datas` al spec si faltara |
| Regresión visual/estructural al eliminar todo el `ttk.Style` | Medio | Checkpoints visuales por pantalla en modo claro y oscuro; comparar contra la versión actual antes de borrar |
| Cambiar `set_appearance_mode` requiere que los widgets se reconstruyan o reestilien | Bajo | CTK re-themea automáticamente los widgets nativos; solo la tabla queda fija al modo de arranque |

## Open Questions

- **Versión exacta de `customtkinter` a fijar** en `pyproject.toml` (recomendado `>=5.2`, revisar la más reciente al instalar).
- **¿El equipo usa Windows en modo oscuro o claro?** Confirmar en el checkpoint final para priorizar la revisión visual de las tuplas.
- **¿Se quiere conectar después la cola semanal (`conxml/semana.py`) a la GUI?** Fuera del alcance de esta migración; queda anotado en el handoff.

## Nota: restauración multi-RFC (Fase 3)

Antes de completar las Tasks 5-6 se detectó y corrigió una regresión en la capa de datos (se había perdido la columna `cliente` y la API `cliente=` en `db/importer/estatus/exportes`), que rompía 18+4 tests y bloqueaba el flujo end-to-end de la pantalla admin. El código original multi-RFC se recuperó del bytecode de `build/conxml/PYZ-00.pyz` (ver bitácora en `tasks/todo.md`). La Task 6 restaura además el selector de cliente (`CTkComboBox`) del build original.