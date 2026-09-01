# Configuraciones de ConXml

Esta carpeta centraliza la documentación de funcionalidades configurables del
sistema, con instrucciones paso a paso para **replicarlas en el futuro** sobre
otras tablas, pantallas o módulos sin tener que reingeniería el código.

| Documento | Funcionalidad |
| --- | --- |
| [`columnas-visibles-en-tablas.md`](columnas-visibles-en-tablas.md) | Ocultar/mostrar columnas de cualquier tabla (Treeview) con preferencias persistentes. |
| [`vistas-conciliacion-de-pagos.md`](vistas-conciliacion-de-pagos.md) | Pestañas de la Conciliación de Pagos (Facturas PPD, Facturas P, Pagos, DoctosRelacionados) y cómo agregar más vistas. |

## Convenciones

- El componente reutilizable vive en `src/conxml/ui/` y no debe depender de
  ninguna pantalla en particular.
- Las preferencias del usuario en tiempo de ejecución se guardan junto al
  `.exe`, en `data/configuraciones/` (ver `conxml/config.py`), para que la
  herramienta siga siendo portátil.
- La documentación de esta carpeta es la fuente de verdad: si la
  funcionalidad cambia, actualiza el documento correspondiente en el mismo
  commit.
