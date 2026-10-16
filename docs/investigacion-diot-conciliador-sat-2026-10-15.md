# DIOT, conciliación SAT y evolución de ConXml

Investigación realizada el 15 de octubre de 2026. Alcance: revisar el código actual, consultar documentación pública del SAT y contrastar funciones anunciadas por sus fabricantes. Este documento propone desarrollo; no certifica cálculos fiscales ni representa una prueba funcional de los productos comparados.

## 1. Recomendación

Construir un motor común de operaciones e IVA y utilizarlo en tres entregas sucesivas:

1. **Conciliación de inventario SAT:** UUID locales contra metadata del SAT.
2. **Conciliación fiscal:** acumulados de ConXml contra información del visor, con diferencias explicadas.
3. **DIOT asistida:** operaciones por proveedor, revisión, archivo TXT y expediente de presentación.

El primer conciliador aporta valor aunque un cliente no tenga obligación de presentar DIOT. El motor fiscal permite después aprovechar el mismo trabajo en ambos módulos. La generación de DIOT puede desarrollarse antes de automatizar el acceso al visor: son dependencias distintas.

La oportunidad de producto es que el contador pueda abrir cualquier importe y conocer **qué comprobantes lo integran, qué regla se aplicó, qué falta revisar y qué cambió desde el cierre anterior**.

## 2. Base real disponible en ConXml

La revisión se realizó sobre el código de la versión declarada 0.2.31, no solamente sobre su publicidad o README.

| Componente | Evidencia local | Aprovechamiento y brecha |
|---|---|---|
| Catálogo por cliente y UUID | `src/conxml/catalog/db.py` | Reutilizar SQLite, asociaciones de clientes y deduplicación. Añadir fuentes externas y cortes. |
| CFDI 4.0 e impuestos generales | `src/conxml/cfdi/models.py`, `parser.py` | Hay impuestos del comprobante. Los conceptos se conservan como descripciones; hace falta estructurar conceptos, objeto de impuesto e impuestos por partida. |
| REP 2.0 | `src/conxml/cfdi/pagos.py` | Extrae fecha de pago, moneda, importe, documentos, parcialidad y saldos. No extrae `ImpuestosDR`, `ImpuestosP` ni `Totales`. |
| Moneda de documentos REP | `pagos.py` y persistencia de `catalog/db.py` | El parser lee `EquivalenciaDR`, pero la tabla y la inserción de documentos relacionados revisadas no la guardan. Completar antes de calcular operaciones en moneda extranjera. |
| Reporte de pagos | `src/conxml/export/pagos.py` | Sirve como relación REP–factura y muestra saldos. No es todavía una determinación de IVA ni una conciliación completa de todas las facturas sin REP. |
| Estatus y descarga SAT | `src/conxml/sat/estatus.py`, `descarga_masiva.py` | Reutilizar autenticación, solicitudes y seguimiento. La solicitud actual fija `TipoSolicitud="CFDI"`; falta soportar metadata. |
| Excel, PDF, bóveda y respaldos | `src/conxml/export/`, `boveda.py`, `respaldos.py` | Utilizar para entregar papeles de trabajo y conservar evidencia. |

El README anuncia extracción completa de impuestos de REP, pero el parser y el esquema revisados no respaldan esa capacidad. Esa diferencia debe resolverse antes de ofrecer una DIOT automática.

Para los cálculos nuevos conviene conservar `Decimal` de principio a fin. Los exportadores actuales convierten algunos datos a `float`; sus resúmenes no deben convertirse en la fuente del nuevo motor fiscal.

## 3. Qué se verificó sobre DIOT

El SAT anunció el uso exclusivo de la nueva plataforma desde el 1 de agosto de 2025. La plataforma permite carga TXT y obtención de acuse. [Comunicado SAT 42/2025](https://www.gob.mx/sat/prensa/sat-informa-que-la-diot-debe-presentarse-unicamente-por-medio-de-la-nueva-plataforma-digital-042-2025).

El instructivo oficial localizado distingue ejercicios 2025 en adelante de 2024 y anteriores. Establece UTF-8, separador `|`, campos condicionados y montos enteros; incluye datos de terceros, operaciones, IVA acreditable, no acreditable y datos adicionales. La documentación de CONTPAQi confirma el formato de 54 campos para 2025 en adelante. [Instructivo SAT, enero de 2025](https://www.sat.gob.mx/cs/Satellite?blobcol=urldata&blobkey=id&blobtable=MungoBlobs&blobwhere=1461176417476&ssbinary=true), [documentación del fabricante](https://conocimiento.blob.core.windows.net/conocimiento/2025/Contables/ContabilidadBancos/CartasTecnicas/CT_Contabilidad_Bancos_1831/mayor_informacion_en_el_proceso_de_la_diot_print.html).

El artículo 5, fracción III, de la LIVA exige pago efectivo del IVA trasladado para su acreditamiento; existen otros requisitos. Por ello, contar con un CFDI y su etiqueta PUE no basta para concluir automáticamente que todo su IVA es acreditable. [LIVA, artículos 1-B y 5](https://www.diputados.gob.mx/LeyesBiblio/pdf/LIVA.pdf).

### Aplicación propuesta: DIOT asistida

Flujo de usuario:

1. Elegir RFC, ejercicio, periodo y tipo de declaración.
2. Revisar cobertura de XML, estatus y pagos; mostrar faltantes y datos sin verificar.
3. Preparar operaciones candidatas: PUE, pagos relacionados con PPD y movimientos capturados con soporte.
4. Clasificar tercero y tipo de operación; dividir por operación cuando un proveedor tenga varias actividades.
5. Revisar tratamiento de IVA y excepciones por operación o concepto.
6. Presentar un resumen por proveedor con acceso al detalle de cada importe.
7. Ejecutar validaciones y exportar TXT, Excel de soporte y lista de pendientes.
8. El contador carga y presenta en el portal; registra posteriormente el acuse en ConXml.

Pantallas propuestas: **Resumen · Proveedores · Operaciones · Validaciones · Exportación e historial**.

Datos que deben poder capturarse o confirmarse:

- Evidencia y fecha del pago cuando no basten los datos disponibles.
- Tipo de operación del proveedor; evitar clasificar todas sus facturas con una sola regla permanente.
- Porcentaje y motivo de acreditamiento, con vigencia por periodo y posibilidad de excepción por operación.
- Operaciones extranjeras, identificación fiscal, país y soporte de importación cuando corresponda.
- Tratamiento de devoluciones, descuentos y bonificaciones según la operación y su efecto en el periodo.
- Región fronteriza correspondiente cuando aplique. Una tasa de 8% por sí sola no distingue norte de sur.

Las reglas del proveedor serían valores propuestos para agilizar captura; el contador conservaría el control de las excepciones. Los datos del XML original permanecerían separados de los ajustes y criterios contables.

### Ejemplo didáctico

Una factura PPD recibida en enero tiene base de $10,000 e IVA de $1,600. Un REP registra un pago de $5,800 en febrero, con base de $5,000 e IVA de $800 para ese documento. Suponiendo una única tasa, sin retenciones, descuentos ni otros impuestos, el movimiento candidato de febrero sería base de $5,000 e IVA de $800; el acreditamiento final depende de los requisitos aplicables y de la clasificación revisada.

La factura pendiente de pago no debe sumarse completa junto con el REP. Tampoco se debe obtener el IVA dividiendo cualquier pago entre 1.16: existen operaciones con varias tasas, retenciones y monedas.

### Condiciones de aceptación

- Separar cálculo con precisión completa de redondeo para salida; no truncar importes indiscriminadamente.
- Versionar layout y reglas por ejercicio. Reconfirmar el instructivo en el portal antes de liberar, pues la versión oficial localizada está fechada en enero de 2025.
- Distinguir error de formato, información incompleta y advertencia fiscal; exportar borradores identificados cuando queden pendientes y reservar la versión revisada para expedientes completos.
- Validar estructura TXT y probar su carga con casos autorizados en el aplicativo aplicable.
- Conservar relación entre campo exportado, proveedor, movimientos y XML fuente.
- No asumir que todos los RFC están obligados: guardar el perfil de obligaciones y su revisión por ejercicio. Esta investigación no determina la obligación particular de cada cliente ni cierra el análisis de facilidades de RMF 2026.

## 4. Conciliador con el SAT

Hay dos problemas diferentes que deben presentarse con nombres claros.

### A. Inventario de comprobantes: XML contra metadata

El SAT documenta metadata con UUID, RFC, fechas, total, tipo y estado del comprobante; su Web Service utiliza e.firma. Esa información permite comparar inventarios, pero no contiene el desglose de impuestos necesario para reconstruir todo el IVA. [SAT: consulta y recuperación](https://wwwmat.sat.gob.mx/consultas/42968/consulta-y-recuperacion-de-comprobantes-(nuevo)).

Propuesta:

1. Importar el archivo de metadata descargado por el usuario.
2. Normalizar UUID y RFC, identificar contribuyente, dirección y alcance temporal.
3. Cruzar por UUID contra el catálogo del cliente activo.
4. Separar coincidencias, faltantes locales, registros locales ausentes en la fuente importada y diferencias de estado o total.
5. Preparar una lista de XML por recuperar y un reporte Excel.
6. Añadir posteriormente solicitudes de metadata al cliente SOAP existente.

Un UUID ausente en la metadata importada debe decir **“no encontrado en esta consulta”**, con su periodo y filtros. No permite concluir que el CFDI no existe en el SAT. Un registro cancelado puede existir en metadata aunque no se conserve su XML local.

Esta primera versión no requiere automatizar el navegador del SAT y puede trabajar con archivos que el usuario ya descargó.

### B. Importes: ConXml contra acumulados del visor

El portal oficial de la anual enlaza un visor autenticado de facturas emitidas y recibidas. El servicio de descarga de XML es una fuente distinta. En la documentación pública consultada no se identificó una API oficial del visor para uso de terceros. No se accedió a una sesión fiscal autenticada. [SAT: visores](https://www.sat.gob.mx/minisitio/DeclaracionAnual/Empresas/visores.html).

El manual de Pocket Fiscal documenta extracción del visor a Excel con periodos, tipos de CFDI, métodos de pago y fecha de corte; constituye evidencia del funcionamiento anunciado por ese fabricante, no una especificación oficial del SAT. [Manual de Pocket Fiscal](https://www.pocketfiscal.com/manual/visor-facturas).

Propuesta inicial:

1. Importar un archivo disponible del visor o una plantilla de captura controlada.
2. Mostrar una vista previa y confirmar RFC, ejercicio, fuente, fecha de corte y columnas reconocidas.
3. Homologar dirección, periodo, tipo de comprobante, método de pago, moneda y concepto fiscal.
4. Calcular en ConXml los acumulados correspondientes bajo un conjunto identificado de reglas.
5. Mostrar **concepto · SAT · ConXml · diferencia · explicación · evidencia**.
6. Exportar diferencias y conservar la consulta como un corte inmutable.

Hace falta obtener muestras reales de los formatos usados por el despacho antes de fijar un importador automático. Si un archivo tiene únicamente acumulados, la comparación será por acumulados: no puede prometerse identificar desde él el UUID exacto de cada diferencia. El detalle local permitirá investigar candidatos; metadata y XML completarán la evidencia.

Ejemplo de interfaz con datos ficticios:

| Concepto | SAT | ConXml | Diferencia ConXml − SAT | Resultado |
|---|---:|---:|---:|---|
| IVA 16% de facturas PUE recibidas | $12,800 | $12,640 | −$160 | Revisar cobertura, filtros y corte |
| IVA 16% de pagos recibidos | $3,200 | $3,200 | $0 | Coincide para este concepto |
| CFDI vigentes en inventario comparable | 120 | 118 | −2 | Dos UUID faltantes locales, si metadata lo confirma |

Los conceptos definitivos dependerán del visor y régimen seleccionados. Mostrar cero diferencia no equivale a certificar deducibilidad, materialidad o cumplimiento de todos los requisitos fiscales.

### C. Confronta posterior: DIOT contra declaración de IVA

Agregar un puente de conciliación entre conceptos comparables. Separar diferencias por importaciones, retenciones, proporciones, devoluciones, ajustes y redondeo. Evitar comparar el IVA total de una DIOT con el saldo a cargo o a favor de la declaración mensual: representan magnitudes distintas.

### Cuándo considerar automatización del portal

Después de estabilizar el importador y el cálculo. Evaluar un acceso asistido que respete la autenticación y los pasos que deba completar el usuario, con mantenimiento de cambios del portal. La descarga masiva SOAP existente no da automáticamente acceso al visor, declaraciones u opiniones de cumplimiento.

## 5. Herramientas de otros programas y qué adoptar

Se comparan capacidades anunciadas públicamente. No se instalaron versiones de prueba ni se verificaron límites, velocidad, exactitud o disponibilidad en cada licencia.

| Producto y fuente del fabricante | Qué destaca en su documentación | Aplicación propuesta en ConXml |
|---|---|---|
| [MiAdminXML: DIOT](https://www.adminxml.com/es/generar-carga-batch-diot/) y [pagos](https://www.adminxml.com/es/control-y-conciliacion-de-pagos/) | Asistente DIOT, clasificación de proveedores, proporción de IVA y conciliación PPD–REP. | Asistente de cierre con pendientes visibles y reglas recordadas por proveedor, editables por operación. |
| [XMLSAT Premium, Softwarepaq](https://www.softwarepaq.com/xmlsat_premium.php) | DIOT, reportes tributarios, conciliación PPD y un módulo anunciado para diferencias de IVA contra SAT; reúne muchas utilidades. | Unir descarga, validación y revisión en una cola por cliente y periodo; concentrar las incidencias en una sola vista. |
| [CONTPAQi Anticipa](https://www.contpaqi.com/anticipa) | Tableros de discrepancias e impuestos, indicadores y conexión con XML en Línea+ y ADD. | Tablero fiscal con navegación del total al documento y seguimiento de diferencias. La conexión con sistemas contables sería una etapa aparte. |
| [ContadorMx CORE](https://contadormx.com/core/) | Clasificación de gastos, diagnóstico, IVA/ISR, PPD/REP, DIOT TXT y consultas con IA desde una base común. | Compartir clasificación y motor entre reportes. Incorporar ayuda para búsquedas y explicaciones después de estabilizar reglas numéricas reproducibles. |
| [Pocket Fiscal](https://www.pocketfiscal.com/manual/visor-facturas) y [reportes](https://www.pocketfiscal.com/reportes) | Extrae acumulados del visor a Excel, identifica corte y genera constancias de consultas y documentos descargados. | Guardar fecha de corte, alcance de cada consulta y evidencia de cobertura. Añadir expediente por RFC y periodo. |

Estos productos muestran que XML a Excel, PDF, bóveda y descarga ya son funciones habituales del mercado. ConXml tiene varias de ellas. La siguiente mejora con mayor utilidad sería convertir sus datos en una revisión fiscal explicable y repetible.

## 6. Otras funciones candidatas, ordenadas por utilidad

| Prioridad propuesta | Función | Aplicación concreta | Esfuerzo relativo |
|---|---|---|---|
| Alta | Alertas de PPD y REP | Factura sin REP localizado, REP sin factura, parcialidad repetida, saldo inconsistente, pagos duplicados por revisar y documentos cancelados. Evitar presentar “sin REP” como prueba de “no pagada”. | Medio |
| Alta | Cancelaciones después del cierre | Historial de estatus y comparación de cortes, con periodos e importes potencialmente afectados; revisión por el contador. | Medio |
| Alta | Catálogo de criterios fiscales | Reglas propuestas por proveedor/concepto, vigencia y excepciones. Compartido entre DIOT y papeles de trabajo. | Medio |
| Alta | Cruce con listados 69-B | Descargar publicaciones oficiales, guardar fecha y categoría y mostrar coincidencias por RFC con vínculo a la fuente. Diferenciar las categorías publicadas y no emitir un juicio automático sobre una operación. | Bajo a medio |
| Media | Cierre mensual y expediente | Estado “por revisar/revisado/cerrado”, notas, documentos de soporte, fuentes, TXT, Excel y acuses. Reabrir mediante una nueva versión. | Medio |
| Media | Conciliación bancaria | Importar CSV/XLSX, proponer coincidencias por importe, fecha y referencia; admitir pagos agrupados, parcialidades y confirmación humana. | Alto |
| Media | Nómina contra visor | Acumulados por trabajador, percepciones, deducciones, ISR y subsidio; comparar con fuente del visor identificada. Reutilizar el parser de nómina existente. | Medio a alto |
| Media | Reporte por conceptos | Estructurar claves, unidades, cantidades, descuentos e impuestos; agrupar compras y gastos y encontrar anomalías. | Medio |
| Media | Retenciones e información de pagos | Parser independiente y reportes por complemento; no confundir estos XML con retenciones contenidas en un CFDI ordinario. | Alto |
| Posterior | Exportación de pólizas | Catálogo de cuentas, reglas, revisión y adaptadores a layouts contables definidos. | Alto |
| Posterior | Expediente de materialidad | Adjuntar contratos, órdenes, entregables y pagos vinculados al UUID; checklist y faltantes documentales. | Medio |
| Posterior | Asistente de consulta | Preguntas sobre datos y explicaciones con enlaces al XML y a la regla aplicada; cálculos ejecutados por el motor verificable. | Medio a alto |

Fuente externa para los listados: [SAT: contribuyentes con operaciones inexistentes](https://wwwmat.sat.gob.mx/consultas/76675/consulta-la-relacion-de-contribuyentes-que-realizan-operaciones-inexistentes). El estado SAT “Vigente” y la situación del emisor en un listado son controles diferentes.

## 7. Diseño técnico propuesto

Mantener Python, SQLite y la interfaz actual para estas primeras entregas. La investigación no identifica una necesidad de reescribir ConXml.

Separar cuatro capas:

1. **Evidencia original:** XML y archivos externos con hash, RFC, fecha de importación, periodo y corte.
2. **Datos estructurados:** conceptos, impuestos, pagos y relaciones entre documentos.
3. **Criterios y cálculo:** decisiones del contador, reglas versionadas y movimientos fiscales.
4. **Presentación:** conciliaciones, DIOT y papeles de trabajo.

Módulos nuevos sugeridos:

```text
src/conxml/fiscal/         operaciones, monedas, IVA y reglas
src/conxml/conciliacion/   metadata, acumulados del visor y explicaciones
src/conxml/diot/           clasificación, validación y layouts por ejercicio
```

Entidades adicionales sugeridas:

- `conceptos_cfdi` e `impuestos_concepto`.
- Impuestos REP por documento, por pago y totales, conservando su nivel de origen.
- `fuentes_sat` y registros importados de metadata/visor.
- `historial_estatus`, separado del último estado consultado.
- `criterios_fiscales` con alcance cliente/proveedor/operación y vigencia.
- `movimientos_fiscales` con UUID, pago, base, tasa, impuesto, moneda y periodo.
- `cierres`, `ajustes` y `exportaciones_diot` con versión y trazabilidad.

La unidad del movimiento fiscal debe distinguir RFC activo, dirección, UUID, índice de pago, documento relacionado e impuesto. Un REP con varias facturas no debe repetir el total completo del pago en cada factura. Validar pertenencia del emisor/receptor al contribuyente y consultar antecedentes de otros meses cuando un pago del periodo corresponda a una factura anterior.

Reglas operativas:

- Reprocesar los XML conservados para completar los datos nuevos, con una migración verificable y respaldo previo.
- Probar relaciones de notas de crédito y sustituciones, tasas mixtas, retenciones y pagos cruzados entre periodos.
- Separar fecha de emisión, timbrado, pago, consulta y corte del SAT.
- No reemplazar un estatus desconocido o una descarga fallida por “Vigente”.
- Mantener los ajustes fuera del XML; exigir motivo y registrar su impacto.
- Preparar cambios de versión de la fuente y rechazar formatos no reconocidos con un mensaje concreto.

## 8. Secuencia de implementación y validación

| Entrega | Resultado revisable | Comprobación necesaria |
|---|---|---|
| 1. Inventario SAT | Importación metadata, cruce por UUID y Excel de faltantes/diferencias. | Casos con cancelados, duplicados, filtros parciales, RFC equivocado y consultas de distintos cortes. |
| 2. Motor de operaciones e IVA | REP completo, conceptos, moneda, periodos y detalle de cálculo. | Casos de referencia con importes esperados preparados por el contador. |
| 3. Conciliador del visor | Importación/captura de acumulados, homologación y diferencias trazables. | Archivos reales anonimizados de las variantes que use el despacho. |
| 4. DIOT asistida | Clasificación, validaciones, TXT, Excel e historial. | Casos fiscales revisados, layout vigente y prueba de aceptación en el portal con datos autorizados. |
| 5. Seguimiento | Historial de cancelaciones, listados y expediente mensual. | Reabrir un cierre, cambiar un estatus y mostrar solo el impacto correspondiente. |

Son entregas funcionales, no fechas prometidas. La estimación en semanas debe hacerse después de revisar muestras del visor y acordar el alcance fiscal: proveedores nacionales sencillos requieren menos trabajo que importaciones, proporciones, multimoneda e históricos.

Para cerrar el diseño hacen falta muestras anonimizadas del visor que use el despacho y un conjunto de casos revisados: PUE, PPD con varios pagos, REP de factura de mes anterior, retenciones, notas de crédito, sustituciones y tasas mixtas. Si se incluyen importaciones o acreditamiento proporcional, incorporar también esos casos.

## 9. Límites de la investigación

- Se consultaron fuentes públicas; no se presentaron declaraciones ni se ingresó con credenciales del usuario.
- El formato oficial DIOT localizado está fechado en enero de 2025. Antes de implementar la salida productiva se debe verificar si el aplicativo ofrece una revisión posterior.
- Algunas rutas históricas del SAT siguen indexadas con manuales anteriores. Para una implementación nueva no conviene usar el antiguo programa de escritorio como especificación principal.
- No se identificó una API pública oficial para extraer los acumulados del visor o presentar DIOT desde un tercero. Esto no prueba que no exista alguna integración específica; exige confirmación antes de comprometer esa automatización.
- Las reglas particulares de obligación, facilidades y vencimientos por régimen para 2026 quedan fuera de la determinación realizada aquí. Deben validarse al implementar el perfil fiscal.
- No se compararon precios ni se probaron promesas comerciales de velocidad o exactitud.

La entrega de esta revisión es el presente documento; el código de aplicación no fue modificado como parte de la investigación.
