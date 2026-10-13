# Orden de carpetas de ConXml — 12 de octubre de 2026

Se revisaron las carpetas del proyecto, sus tamaños, referencias en código y scripts,
archivos de configuración y duplicados exactos de documentos y datos fuera de
entornos, compilaciones y dependencias. No se borraron datos ni se descartaron cambios locales.

## Estructura actual

| Carpeta | Uso / decisión |
|---|---|
| `src/` | Código activo. Se retiraron cachés de Python. |
| `tests/` | Pruebas y fixtures. Se retiraron cachés. |
| `scripts/` | Ejecución, compilación, instaladores y mantenimiento. |
| `docs/` | Documentación, investigaciones e ideas. |
| `docs/configuraciones/` | Guías antes situadas en la raíz como `configuraciones/`. |
| `docs/historico/` | Planes, listas de tareas y handoff antiguos; conservar como contexto histórico. |
| `docs/administracion/` | Carta de aceptación del servicio. |
| `data/` | Catálogo, clientes, bóveda, preferencias, exportaciones, respaldos y caché PDF. Conservar. |
| `data/importaciones/xml-legado/` | Los 30 XML antes situados en `3/`. No se borraron. |
| `.venv-mac/` | Entorno usado por el lanzador local y compilación macOS. |
| `build/native/` | Herramientas nativas usadas por la introducción y visor. Conservar. |
| `dist/` | Aplicaciones macOS, CLI y entregables Windows. Conservar porque no se confirmó cuáles se distribuyen. |
| `installer/` | Configuración del instalador. |
| `coordination/` y `tools/` | Integración de coordinación pendiente de revisión; tiene referencias activas. |
| `logs/` | Registro reciente; conservar para diagnóstico e ignorar en Git. |
| `videos/` | Proyecto y video de introducción usados por la aplicación. Sin modificaciones. |
| `.github/` | Automatización de releases. |
| `.git/` | Historial y cambios locales. |

## Retirado a respaldo externo

Ruta: `../ConXml-respaldo-orden-2026-10-12/`.

- `.venv` era un entorno de Windows copiado a macOS; los scripts Windows lo recrean si falta.
- Compilaciones PyInstaller anteriores, incluidas variantes de depuración. Se conserva `build/native/`.
- Cinco archivos `.spec` de variantes antiguas; se conserva `conxml.spec`.
- Cachés de pruebas/Python y archivos `.DS_Store` fuera del proyecto de video y del entorno activo.
- `updates/` estaba vacía.

Se retiraron aproximadamente 246 MiB del proyecto. El respaldo sigue ocupando
espacio en el disco: esta operación organiza, no libera ese espacio permanentemente.
Cada movimiento, ruta original y destino está registrado en `movimientos.json`
dentro del respaldo. Para deshacer un movimiento, devolver su destino a su origen,
comprobando antes que no haya nuevos archivos en la ruta original.

## Duplicados y límites

Dos preferencias JSON tienen contenido idéntico, pero corresponden a tablas distintas:
se conservaron ambas. `AGENTS.md` y `CLAUDE.md` del video también coinciden y sirven
a herramientas distintas. No se dedujo que datos o entregables fueran prescindibles
solo por su fecha. No se compararon por hash todos los ejecutables y dependencias.

Se actualizaron las referencias activas a la documentación trasladada y se añadieron
`logs/`, `data/cache/` y `data/importaciones/` a `.gitignore`. Los cambios previos de
código y preferencias se conservaron. Los documentos históricos pueden describir
la estructura y los resultados de pruebas de su época.

Validación: todos los destinos del registro existen, el lanzador conserva su entorno,
los datos y aplicaciones siguen presentes y el archivo Python cuya referencia se
actualizó mantiene sintaxis válida. No se ejecutó la interfaz ni toda la batería de
pruebas porque no se cambió comportamiento de la aplicación.
