# Vistas de la Conciliación de Pagos (estilo Mi Admin XML)

Fecha: 2026-08-24
Estado: Implementado. La pantalla "Conciliación de Pagos" (`pagos`) tiene un
selector de vistas con 5 pestañas; se agregaron las 4 nuevas tomando como
referencia el programa Mi Admin XML.

## 1. Pestañas y su fuente de datos

| Pestaña | Clave interna | Fuente de datos | Una fila es… |
| --- | --- | --- | --- |
| Conciliación | `conciliacion` | `pagos` × `doctos_relacionados` × `comprobantes` | cada (pago × documento relacionado), igual que el Excel de pagos |
| Facturas PPD | `facturas_ppd` | `comprobantes` con `metodo_pago = 'PPD'` y `tipo_comprobante IN ('I','E')` | cada factura pendiente de cobro |
| Facturas P | `facturas_p` | `comprobantes` con `tipo_comprobante = 'P'` | cada recibo electrónico de pago (REP) |
| Pagos | `pagos` | tabla `pagos` (join a su REP) | cada pago individual capturado dentro de un REP |
| DoctosRelacionados | `doctos` | `doctos_relacionados` (join a pago, REP y factura) | cada documento aplicado por cada pago |

## 2. Lógica de negocio relevante

- **Estatus de Pago de una factura PPD** (columna `estado_cobranza`):
  - Sin documentos relacionados → `No pagada`.
  - `imp_saldo_insoluto` de la parcialidad más alta ≤ 0.01 → `Totalmente pagada`.
  - En otro caso → `Parcialmente pagada`.
  (Espejo exacto de `PanelResumenPagos`, para que los totales cuadren.)
- **Saldo Pendiente** = `Total − sum(imp_pagado)` de todos los doctos del UUID.
- En `DoctosRelacionados`, Año/Mes/Día salen de la **fecha de emisión de la
  factura**; Serie/Folio del docto con fallback a los de la factura.
- Las facturas PPD solo aparecen si el XML trae `MetodoPago="PPD"`; con la BD
  actual (solo PUE) la pestaña se ve vacía — es lo esperado.

## 3. Dónde está implementado

Todo en `src/conxml/ui/pantalla_admin.py`:

- `VISTAS_PAGOS`: lista ordenada `(clave, título)` — alimenta el
  `CTkSegmentedButton` de la barra de herramientas.
- `_COLUMNAS_FACTURAS_PPD`, `_COLUMNAS_FACTURAS_P`, `_COLUMNAS_PAGOS_LISTA`,
  `_COLUMNAS_DOCTOS`: definición de columnas por vista.
- `_columnas_vista(clave)`: mapa clave → columnas.
- `_cargar_tabla()`: despacha a `_filas_pagos`, `_filas_facturas_ppd`,
  `_filas_facturas_p`, `_filas_pagos_lista` o `_filas_doctos` según
  `self._vista`.
- `_cambiar_vista(titulo)`: reconfigura columnas, aplica visibilidad
  (ver [`columnas-visibles-en-tablas.md`](columnas-visibles-en-tablas.md)) y
  recarga filas.

Cada vista tiene su propia configuración de columnas visibles con clave
`pagos_<vista>` (ej. `pagos_facturas_ppd`).

## 4. Cómo agregar una vista nueva (checklist)

1. Agrega la tupla `(clave, "Título")` a `VISTAS_PAGOS` (el orden de la lista
   es el orden de las pestañas).
2. Define `_COLUMNAS_<CLAVE>` con tuplas `(clave_col, encabezado, ancho)`.
3. Regístrala en el mapa de `_columnas_vista`.
4. Escribe `_filas_<clave>(self, catalogo)` que inserte filas con los valores
   **en el mismo orden** de las columnas, con zebra `par`/`impar`.
5. Regístrala en el diccionario de despacho de `_cargar_tabla`.
6. Si necesita totales en el panel superior, extiende `PanelResumenPagos`.
7. Prueba: cambiar a la vista, ocultar una columna, reiniciar la app y
   verificar que la preferencia se restaura (`data/configuraciones/`).
