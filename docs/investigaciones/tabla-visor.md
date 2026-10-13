# Investigación: tabla del visor de ConXml

Fecha: 9 de octubre de 2026. Investigación documental y revisión del código; no es un benchmark comparativo. No se modifica la interfaz con este informe.

## Conclusión

Para una evolución de escritorio de ConXml, recomiendo PySide6 con QTableView y QAbstractTableModel, consultando SQLite por páginas reales de 150 filas. Para una mejora inmediata conservando CustomTkinter, recomiendo separar y optimizar la consulta antes de sustituir otra vez el componente visual. La recomendación de Qt es una valoración de adecuación arquitectónica, pendiente de validar rendimiento y usabilidad con una prueba del visor.

El visor necesita una tabla de consulta contable de solo lectura, con selección de celdas para copiar y selección independiente de documentos para operaciones. La apariencia puede conservar colores, tipografía, espaciado y organización actuales.

## Hallazgos del código actual

- `Catalogo.consulta()` obtiene todas las columnas de todos los comprobantes que cumplen los filtros; no tiene LIMIT ni un contrato de orden configurable.
- `TablaVisor` conserva todos los resultados y solo entrega 150 al componente gráfico. Reduce dibujo, pero no lectura, preparación de datos ni memoria total.
- `_cargar_tabla()` consulta, prepara y actualiza en el hilo de interfaz. En CFDI y nómina obtiene registros para totales y vuelve a consultarlos para construir filas.
- `_filas_nomina()` abre y analiza cada XML al reconstruir la vista. Esta información debería prepararse en la importación o almacenarse en una caché con invalidación.
- Las vistas de pagos consultan documentos relacionados dentro de bucles. Conviene evaluar consultas conjuntas y agregaciones para evitar una consulta por pago.
- Fecha y monto se filtran sobre los valores preparados para la tabla. Con paginación real deben pasar al repositorio antes de limitar filas.
- El esquema revisado no declara índices secundarios para cliente, periodo y tipo. Las claves primarias sí tienen sus mecanismos de indexación. Los nuevos índices deben decidirse con EXPLAIN QUERY PLAN y mediciones, no por suposiciones.
- Importes se guardan como texto y la interfaz ordena valores formateados convirtiéndolos a float. Una consulta nueva debe distinguir datos numéricos y texto, preservando exactitud decimal; no ordenar cantidades lexicográficamente.
- Exportar Excel actualmente consulta por cliente y tipo, sin reutilizar todos los filtros del visor. Debe definirse explícitamente si se exporta el cliente completo o el resultado filtrado.

## Comparación

| Alternativa | Adecuación | Ventajas | Coste y límites |
|---|---|---|---|
| ttk.Treeview optimizado | Buena para un visor sencillo que conserve la interfaz | Integración existente, selección de documentos y pocas dependencias | Selección y copia de rangos de celdas requieren desarrollo propio; es un componente orientado a elementos/filas |
| tksheet | Buena si la prioridad es interacción de hoja de cálculo dentro de Tk | Selección y copia de celdas; dibuja la porción visible | No resuelve por sí mismo consultas, caché, totales ni lectura XML; el adaptador actual conserva el conjunto completo |
| PySide6 / QTableView | Mejor candidato para evolución de escritorio | Modelo separado de presentación, selección y carga incremental; formatos y delegados personalizables | Migrar la interfaz del visor y su integración; copia tabular y columnas congeladas requieren implementación; revisar distribución/licencia antes de adoptarlo |
| Tabulator en una vista web local | Alternativa si se elige una arquitectura web | Selección de rangos, portapapeles y paginación con una fuente de datos | Añade JavaScript, motor web y comunicación con Python; empaquetado y mantenimiento adicionales |
| AG Grid | Alternativa para una evolución web con necesidades empresariales | Modelo de carga por bloques y amplia funcionalidad | La selección de rangos de celdas figura como Enterprise; añade otra arquitectura y posibles costes |

Una vista web local puede funcionar sin enviar CFDI a un servicio externo; la arquitectura y los recursos empaquetados determinarían su funcionamiento sin conexión.

## Contrato funcional recomendado

1. Páginas reales de 150: cliente, periodo, filtros y orden se aplican en SQLite antes de obtener los registros. Usar orden estable con desempate por identificador. Si las páginas lejanas hacen lento OFFSET, medir paginación por cursor para siguiente/anterior; saltar a una página arbitraria requiere otra estrategia.
2. Consultas y preparación fuera del hilo gráfico. Cada trabajador abre su conexión SQLite; las respuestas se aplican en el hilo de interfaz. Descartar respuestas antiguas cuando cambia cliente, filtro o vista. Qt no permite modificar su modelo directamente desde el trabajador.
3. Totales sobre todo el conjunto filtrado, separados de la página. Evitar sumar monedas distintas sin una regla explícita. Los totales de selección también deben identificar moneda.
4. Copia de celdas o rangos como texto tabulado compatible con Excel; conservar UUID y RFC completos. No habilitar edición de datos fiscales accidentalmente.
5. Selección de comprobantes por identidad estable. En CFDI puede ser UUID; en pagos y documentos relacionados se necesitan identificadores de fila o claves compuestas porque un UUID puede repetirse.
6. Separar acciones sobre seleccionados, página actual y todos los resultados filtrados. Mostrar el alcance y su cantidad. La selección persistente entre páginas se mantiene fuera del componente gráfico.
7. Filtros por tipo de dato: fechas por rango, montos por rango, estatus por opciones y texto con búsqueda exacta o parcial. No asumir que un índice normal acelera búsquedas `%texto%`.
8. Columnas principales visibles para seguimiento: fecha, folio, contraparte, total, moneda y estatus. Impuestos, certificados, conceptos y relaciones disponibles mediante perfiles de columnas y un panel de detalle. Todos los datos siguen accesibles.
9. Formatos de lectura: importes alineados a la derecha, separadores consistentes, fechas legibles y texto completo al copiar o abrir detalle. Identificación fija al desplazarse horizontalmente si la prueba de uso lo justifica.

## Cómo decidir antes de migrar

Construir una prueba independiente de CFDI con el mismo repositorio y apariencia para comparar el visor actual optimizado y QTableView. Usar lotes sintéticos de 1.000, 10.000 y 100.000 registros, además de nómina y pagos con relaciones. Medir tiempo de primera página, filtro, orden, cambio de página, memoria y capacidad de interactuar mientras consulta. Verificar selección entre páginas, copia, totales y PDF. Son tamaños propuestos para pruebas, no capacidades demostradas.

No se recomienda mezclar Tk y Qt como widgets dentro de la misma ventana: son arquitecturas de interfaz y bucles de eventos distintos. Una adopción de Qt debe planificarse como migración del visor y su integración, reutilizando parser, catálogo, SAT y exportadores.

## Fuentes oficiales

- [Qt: programación modelo/vista y carga incremental](https://doc.qt.io/qtforpython-6/overviews/qtwidgets-model-view-programming.html)
- [Qt: QTableView](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QTableView.html)
- [Qt: QAbstractTableModel y restricciones de hilos](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QAbstractTableModel.html)
- [Qt: implementación de columnas congeladas](https://doc.qt.io/qt-6/qtwidgets-itemviews-frozencolumn-example.html)
- [tksheet: funcionamiento y API](https://ragardner.github.io/tksheet/DOCUMENTATION.html)
- [Python: ttk.Treeview](https://docs.python.org/3/library/tkinter.ttk.html#treeview)
- [Tabulator: selección de rangos](https://www.tabulator.info/docs/6.x/range/)
- [Tabulator: paginación](https://www.tabulator.info/docs/6.x/page/)
- [Tabulator: portapapeles](https://www.tabulator.info/docs/6.x/clipboard/)
- [AG Grid: modelo de filas infinito](https://www.ag-grid.com/javascript-data-grid/infinite-scrolling/)
- [AG Grid: selección de celdas Enterprise](https://www.ag-grid.com/javascript-data-grid/cell-selection/)
- [SQLite: planificación e índices](https://www.sqlite.org/queryplanner.html)
- [SQLite: SELECT, orden y LIMIT](https://www.sqlite.org/lang_select.html)
