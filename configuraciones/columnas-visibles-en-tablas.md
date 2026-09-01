# Columnas visibles en tablas (ocultar/mostrar columnas)

Fecha: 2026-08-24
Estado: Implementado en XML 4.0, Conciliación de Pagos (5 vistas) y Recibos de Nómina.

## 1. Qué hace

Cada tabla de la aplicación ofrece un botón **"⚙ Columnas"** que abre un
diálogo con un checkbox por columna. El usuario elige qué columnas quiere ver;
la selección:

1. Se aplica de inmediato al `ttk.Treeview` (sin recargar datos).
2. Se persiste en disco y se restaura automáticamente al reabrir el programa.
3. Es independiente por tabla (y por vista, en Conciliación de Pagos).

Reglas de diseño:

- Siempre debe quedar **al menos una columna visible** (validado en el diálogo).
- Las columnas ocultas conservan sus datos; solo se ocultan vía
  `displaycolumns` del Treeview, así que exportar a Excel **no** se ve afectado.
- `auto_ajustar_columnas` respeta las ocultas: mide únicamente las visibles.

## 2. Dónde vive el código

| Archivo | Responsabilidad |
| --- | --- |
| `src/conxml/ui/columnas.py` | Componente reutilizable completo (sin depender de pantallas). |
| `src/conxml/ui/pantalla_admin.py` | Lo instancia para sus 3 modos y 5 vistas de pagos. |

Dentro de `columnas.py`:

- `cargar_ocultas(clave, base=None)` / `guardar_ocultas(clave, ocultas, base=None)`:
  capa de persistencia JSON (tolerante a archivos corruptos).
- `GestorColumnas`: une un `Treeview` + una clave de configuración + la
  definición de columnas. Métodos: `aplicar()`, `abrir_dialogo(parent, al_aplicar)`,
  `ocultas()`.
- `DialogoColumnas`: `CTkToplevel` modal con checkbox por columna y botones
  Todas / Ninguna / Aplicar / Cancelar.

## 3. Formato de las preferencias

Ruta: `<carpeta de datos>/configuraciones/columnas_<clave>.json`
(en desarrollo: `data/configuraciones/`; en el `.exe`: `data\configuraciones\`
junto al ejecutable).

```json
{
  "ocultas": ["curp", "puesto"]
}
```

Claves en uso hoy:

| Clave | Tabla |
| --- | --- |
| `cfdi40` | Tabla de XML 4.0 |
| `nomina` | Tabla de Recibos de Nómina |
| `pagos_conciliacion` | Conciliación de Pagos, vista "Conciliación" |
| `pagos_facturas_ppd` | Conciliación de Pagos, vista "Facturas PPD" |
| `pagos_facturas_p` | Conciliación de Pagos, vista "Facturas P" |
| `pagos_pagos` | Conciliación de Pagos, vista "Pagos" |
| `pagos_doctos` | Conciliación de Pagos, vista "DoctosRelacionados" |

Borrar el JSON restaura todas las columnas.

## 4. Cómo replicarlo en una tabla nueva (checklist)

1. **Define tus columnas** como lista de tuplas `(clave, encabezado, ancho)`:

   ```python
   _MIS_COLUMNAS = [
       ("uuid", "UUID", 240),
       ("total", "Total", 100),
   ]
   ```

2. **Crea el Treeview** con `displaycolumns="#all"` y configura encabezados
   con un método tipo `_configurar_columnas` que primero resetee
   `displaycolumns` y luego asigne `columns`, `heading` y `column` (ver
   `PantallaAdministracion._configurar_columnas`).

3. **Instancia un gestor por tabla** (después de configurar las columnas):

   ```python
   self._gestores: dict[str, GestorColumnas] = {}
   ...
   self._gestor().aplicar()  # aplica preferencias guardadas al arrancar
   ```

   Patrón recomendado (creación perezosa por clave, como en
   `PantallaAdministracion._gestor`):

   ```python
   def _gestor(self) -> GestorColumnas:
       clave = "mi_tabla"
       gestor = self._gestores.get(clave)
       if gestor is None:
           gestor = GestorColumnas(self._tabla, clave, _MIS_COLUMNAS, "Mi tabla")
           self._gestores[clave] = gestor
       return gestor
   ```

4. **Agrega el botón** en la barra de herramientas de la tabla:

   ```python
   BotonSecundario(barra, "⚙ Columnas", self._abrir_columnas).pack(side="right")

   def _abrir_columnas(self) -> None:
       self._gestor().abrir_dialogo(
           self, al_aplicar=lambda: auto_ajustar_columnas(self._tabla)
       )
   ```

5. **Si la tabla cambia de conjunto de columnas en caliente** (p. ej. vistas),
   usa un gestor distinto por conjunto (clave diferente) y al cambiar:
   `_configurar_columnas(nuevas)` → `_gestor().aplicar()` → recargar filas.

6. **Tests**: la capa de persistencia se prueba en `tests/test_columnas.py`;
   agrega un caso si extiendes `columnas.py`.

## 5. Detalles técnicos importantes

- `displaycolumns` acepta una lista de claves visibles o `"#all"`.
  `GestorColumnas.aplicar()` hace fallback a `"#all"` si la lista queda vacía.
- `auto_ajustar_columnas` (en `pantalla_admin.py`) lee `tabla["displaycolumns"]`
  para medir solo columnas visibles; si copias esa función a otro módulo,
  conserva ese comportamiento.
- Al reconfigurar `columns` de un Treeview con `displaycolumns` previo, Tk
  lanza error si las claves ya no existen: por eso `_configurar_columnas`
  resetea `displaycolumns="#all"` **antes** de asignar `columns`.
- `DialogoColumnas` usa `transient` + `grab_set` diferido (`after(60, ...)`)
  para funcionar bien sobre CustomTkinter.
