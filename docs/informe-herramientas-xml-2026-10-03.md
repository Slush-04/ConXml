# Informe de herramientas XML y oportunidades para ConXml

Fecha de investigación: 3 de octubre de 2026.

## 1. Recomendación principal

ConXml debería evolucionar hacia un **administrador de CFDI para despachos con revisión documental, conciliación y control de excepciones**. Su base actual —clientes, bóveda local, CFDI 4.0, REP 2.0, nómina, consultas SAT y Excel— encaja con ese objetivo.

La siguiente inversión debe concentrarse en cuatro resultados: encontrar cualquier comprobante, entenderlo sin leer código XML, detectar documentos o pagos faltantes y entregar evidencia de revisión al cliente. Las funciones de desarrollo XML general pueden incorporarse gradualmente como herramientas auxiliares.

Antes de ampliar el producto, hay que corregir el vínculo entre comprobantes y clientes, la extracción de CFDI relacionados y la diferencia entre los filtros de pantalla y el contenido exportado.

## 2. Alcance y método

Se revisaron el README y el código de `src/conxml`, los modelos, SQLite, la importación, la bóveda, las pantallas de administración y descargas, los exportadores y las pruebas existentes. También se consultaron páginas y documentación de fabricantes y del SAT.

Las funciones de otros programas son **capacidades publicadas por sus proveedores**; no se instalaron ni se hicieron pruebas comparativas de rendimiento. La disponibilidad puede depender de licencia, edición o módulos adicionales. La ausencia de una función en las páginas consultadas no demuestra que el programa carezca de ella.

Para ConXml se distingue entre código existente, comportamiento reproducido y funciones que todavía necesitan validación. Se usaron XML sintéticos y una base temporal para dos comprobaciones específicas. No se consultaron CFDI reales ni se hicieron solicitudes al SAT con e.firma.

## 3. Herramientas que puede ofrecer un visor o administrador XML

Un **visor** permite leer y explorar documentos. Un **editor** permite cambiar su estructura. Un **administrador** organiza colecciones y ejecuta procesos sobre ellas. ConXml puede combinar visualización y administración fiscal.

| Área | Herramientas posibles | Aplicación en ConXml |
|---|---|---|
| Lectura | Texto con colores, árbol de nodos, formato legible, plegado, números de línea, atributos y namespaces | Vista técnica de solo lectura junto a una ficha contable |
| Exploración | Buscar texto, atributos y valores; copiar campo, UUID o ruta; abrir archivo y ubicación | Encontrar datos sin recorrer decenas de columnas |
| Consulta técnica | XPath, consultas guardadas y resultados tabulares | Diagnóstico de complementos y extracción especial |
| Validación | XML bien formado, XSD, reglas de negocio, errores con ubicación, sello y cadena original | Separar errores de estructura, firma, datos y consulta SAT |
| Edición | Autocompletado, insertar/eliminar nodos, deshacer, comparar y fusionar | Reservar para XML genérico o copias de trabajo; conservar intacto el CFDI original |
| Entrada | Archivos, carpetas recursivas, ZIP, arrastrar y soltar, descarga oficial y carpeta vigilada | Reducir pasos para ingresar lotes al catálogo |
| Organización | Clientes, emitidos/recibidos, periodos, etiquetas, notas, favoritos y vistas guardadas | Mantener expedientes de revisión por cliente y mes |
| Búsqueda contable | Fechas, RFC, UUID, serie, folio, conceptos, moneda, importes, impuestos, método y forma de pago | Resolver consultas combinadas y repetirlas |
| Operaciones masivas | Seleccionar filas, consultar estatus, exportar, copiar XML, generar PDF y empaquetar expedientes | Trabajar exactamente sobre el conjunto seleccionado |
| Integridad | Duplicados por UUID y hash, conflictos de contenido, archivos movidos, errores por lote | Evitar omisiones y detectar copias diferentes del mismo comprobante |
| Relaciones fiscales | Factura–REP, notas de crédito, sustituciones, anticipos, documentos relacionados | Navegar desde un comprobante a todo su contexto |
| Conciliación | PPD/REP, metadata SAT frente a catálogo, bancos frente a documentos, cargos frente a abonos | Explicar faltantes y discrepancias con evidencia |
| Reportes | Excel, CSV, PDF, conceptos por renglón, impuestos por tasa, nómina y resumen mensual | Entregar información reutilizable al despacho y sus clientes |
| Automatización | Colas, reintentos, reanudación, tareas periódicas y avisos de cambios | Evitar repetir trabajo y detectar cancelaciones posteriores |
| Auditoría | Historial de estatus, fecha de consulta, responsable, observaciones y cierre de periodo | Saber qué se revisó y con qué información |
| Continuidad | Respaldar/restaurar SQLite, XML y preferencias; comprobar integridad | Recuperar el expediente completo |
| Colaboración | Usuarios, permisos, tareas asignadas, revisión y aprobación | Etapa posterior si el despacho necesita trabajo simultáneo |

Los editores generales ofrecen buenos ejemplos para árbol, tablas, búsquedas, esquemas y comparación. Los administradores mexicanos aportan referencias más cercanas para descarga, revisión SAT, PDF y reportes contables. [XML Notepad](https://microsoft.github.io/XmlNotepad/), [Oxygen Grid Editor](https://www.oxygenxml.com/xml_editor/xml_grid_editor.html), [MiAdminXML: administración](https://www.adminxml.com/es/blog/tutoriales/administracion/).

## 4. Programas investigados y qué podemos aprender

### MiAdminXML

**Finalidad:** descarga y administración de CFDI para trabajo contable.

Su módulo de administración documenta exportación a Excel usando filtros, apertura del XML con el lector predeterminado, conversión a PDF, consulta de estado SAT y localización del archivo. La página principal también presenta análisis de nómina, conciliación PPD contra comprobantes de pago y reportes de retenciones e información de pagos. El tutorial indica que sus herramientas básicas corresponden a licencias Plus y Profesional. [Módulo de administración](https://www.adminxml.com/es/blog/tutoriales/administracion/), [funciones publicadas](https://www.adminxml.com/es/).

**Comparación:** ConXml ya cubre parte importante de la administración tabular, nómina, Excel y conciliación. La oportunidad inmediata es completar la experiencia por comprobante: abrir, localizar, revisar y convertir a PDF. También conviene mejorar el alcance de filtros y reportes.

### CONTPAQi XML en línea+

**Finalidad:** recuperar y organizar CFDI y conectarlos con el ecosistema contable CONTPAQi.

Publica descarga de emitidos y recibidos 3.3/4.0, ejecución desatendida, organización por RFC y periodos, consultas de estatus, filtros, PDF y Excel. Presenta gestión multiempresa y multiusuario; mediante el ADD señala validación de estructura, sello y cadena original, además de detección de duplicados. Las funciones del ADD y las integraciones deben distinguirse del descargador por sí mismo. [Página oficial](https://www.contpaqi.com/xml-en-linea).

**Comparación:** ConXml ya tiene multi-RFC, catálogo y código de descarga. Le faltan programación desatendida, compatibilidad histórica 3.3 y validación documental más profunda. Una integración contable debería empezar con exportadores definidos para un sistema concreto.

### Construsoft: XMLSAT++, XMLSAT Premium y Bóveda XML

**Finalidad:** administración, auditoría y análisis de grandes colecciones de CFDI.

El catálogo anuncia descarga, Excel, conceptos, PDF, reportes de impuestos, multiempresa y organización documental. XMLSAT Premium documenta cruces con listados 69/69-B y comparativas con declaraciones; Bóveda XML se enfoca en almacenamiento y sincronización, y Centinela XML en procesos recurrentes. Son productos y módulos distintos. [Catálogo del fabricante](https://www.construsoft.mx/), [XMLSAT Premium](https://www.construsoft.mx/xmlsat_premium.php).

**Comparación:** las oportunidades son análisis de conceptos, cruces de proveedores, expedientes y automatización. Hay páginas que aún mencionan DIOT 2019 y versiones antiguas: sirven como referencia funcional, pero no verifican compatibilidad con obligaciones de 2026.

### Microsoft XML Notepad

**Finalidad:** explorar y editar XML general mediante una interfaz sencilla.

Documenta árbol sincronizado con texto, búsqueda incremental, expresiones regulares y XPath, validación por esquema, autocompletado, deshacer/rehacer, comparación XML y estadísticas. Publica su código fuente. [Documentación oficial](https://microsoft.github.io/XmlNotepad/).

**Comparación:** ofrece buenas referencias para el visor técnico y los mensajes de validación. Su orientación general no reemplaza el modelo contable de ConXml. Adoptaría árbol, búsqueda y comparación de copias antes que edición de documentos fiscales.

### Oxygen XML Editor

**Finalidad:** edición, validación, transformación y publicación de XML profesional.

Ofrece modos Text, Grid y Author; soporte de esquemas, XPath/XQuery, transformaciones y comparación/fusión. Grid agrupa elementos repetidos en tablas, mostrando sus atributos y elementos como columnas; sus vistas permiten explorar jerarquías y estructuras repetitivas. [Funciones](https://www.oxygenxml.com/features.html), [modo Grid](https://www.oxygenxml.com/xml_editor/xml_grid_editor.html).

**Comparación:** la idea más útil es presentar conceptos, impuestos y documentos REP como subtablas sincronizadas con el XML. Los depuradores y herramientas de publicación tienen menor prioridad para el usuario contable.

### Altova XMLSpy

**Finalidad:** desarrollo profesional sobre XML y formatos relacionados.

Publica edición y validación, diseñador XSD, evaluador XPath/XQuery, transformaciones, depuradores, comparación/fusión de tres vías, integración con bases de datos y generación de código. La matriz de ediciones delimita qué funciones están incluidas. [Producto](https://www.altova.com/xmlspy-xml-editor), [ediciones](https://www.altova.com/xmlspy-xml-editor/editions).

**Comparación:** sirve de referencia para diagnóstico estructural y herramientas de extracción. Replicar un entorno completo de desarrollo tendría un costo alto y aportaría menos que mejorar los flujos de CFDI del despacho.

## 5. Comparación funcional

**Publicado:** capacidad descrita por el proveedor. **Parcial:** existe una base, pero tiene alcance incompleto. **NC:** no confirmado en las fuentes consultadas. **Código:** implementado en el repositorio, pendiente de comprobación real del servicio.

| Función | ConXml | MiAdminXML | CONTPAQi XML+ | Construsoft | XML Notepad | Oxygen / XMLSpy |
|---|---|---|---|---|---|---|
| Gestión de CFDI multi-RFC | Sí; vínculo por cliente por corregir | Publicado | Publicado | Publicado | NC | NC |
| Descarga SAT | Código con e.firma | Publicado | Publicado | Publicado | NC | NC |
| Descarga recurrente desatendida | Pendiente | NC | Publicado | Publicado, según producto | NC | NC |
| Consulta de estado SAT | Sí, con caché | Publicado | Publicado | Publicado | NC | NC |
| Conciliación PPD/REP | Sí; requiere robustecer reglas | Publicado | NC en la página de XML+ | Publicado, según producto | NC | NC |
| Excel contable | Sí | Publicado | Publicado | Publicado | NC | Herramientas generales de datos |
| PDF de CFDI | Pendiente | Publicado | Publicado | Publicado | NC | Transformación/publicación general |
| Conceptos detallados por renglón | Parcial: guarda descripciones | NC en las páginas usadas | Publica explotación de conceptos | Publicado | Nodos generales | Tablas/consultas generales |
| Árbol técnico y búsquedas XPath | Pendiente en la interfaz | NC | NC | NC | Publicado | Publicado |
| XSD / sello / cadena original | Pendiente | NC en las páginas usadas | Publicado mediante ADD | NC en las páginas usadas | XSD general | Validación general y esquemas |
| Cruce 69/69-B | Pendiente | NC en las páginas usadas | NC | Publicado | NC | NC |
| CFDI 3.3 | Rechazado por el parser actual | NC en las páginas usadas | Publicado | Publicado | Lectura XML general | Lectura XML general |

La tabla sintetiza las páginas enlazadas en la sección anterior. “Lectura XML general” no implica interpretación contable, validación fiscal o consulta SAT.

## 6. Lo que ya ofrece ConXml

| Componente | Evidencia local | Evaluación |
|---|---|---|
| Clientes y catálogo | `catalog/db.py`, `ui/pantalla_clientes.py` | Clientes con clave, nombre y RFC; SQLite y deduplicación |
| Bóveda | `boveda.py`, `ui/pantalla_boveda.py` | Copia y orden por cliente, dirección, año y mes |
| CFDI 4.0 | `cfdi/parser.py`, `cfdi/models.py` | Datos generales e impuestos; entidades externas y acceso de red desactivados en el parser |
| REP y nómina | `cfdi/pagos.py`, `cfdi/nomina.py` | Parsers especializados y vistas/reportes |
| SAT | `sat/soap.py`, `sat/estatus.py` | Estado, cancelabilidad y estatus de cancelación; reintentos, caché y consulta forzada |
| Descarga masiva | `sat/descarga_masiva.py`, `ui/pantalla_descargas.py` | Autenticación, solicitud, seguimiento, paquetes ZIP e incorporación a bóveda/catálogo |
| Administración | `ui/pantalla_admin.py` | Tablas, filtros UUID/RFC/serie/folio, totales y columnas configurables |
| Excel | `export/listado.py`, `export/pagos.py`, `export/nomina.py` | Listado de 47 columnas, conciliación y nómina |
| Procesamiento semanal | `semana.py`, `cli.py` | Base para lotes operativos; no equivale a un servicio periódico con la aplicación cerrada |

La descarga tiene código y documentación, pero la propia documentación indica que su funcionamiento debe confirmarse con una cuenta autorizada ante el SAT. Las pruebas actuales de esa pantalla todavía esperan controles y métodos de una versión anterior.

## 7. Correcciones que deben preceder a nuevas funciones

### A. Un comprobante debe poder pertenecer a varios expedientes

`comprobantes.uuid` es clave primaria y cada fila tiene un único `cliente`. En una base temporal, importar el mismo UUID para A devuelve `inserted`; importarlo para B devuelve `skipped` y B queda con cero comprobantes. Esto afecta una factura entre dos clientes del mismo despacho.

**Propuesta:** mantener un documento único por UUID y crear una tabla de asociaciones `cliente_comprobante`, con dirección y contexto de expediente. Adaptar consultas, pagos, exportadores y migración de datos. La deduplicación documental debe coexistir con la visibilidad en ambos clientes.

### B. Corregir la extracción de relaciones

El parser busca `cfdi:CfdiRelacionados/cfdi:Relacionado`, mientras que el nodo documentado es `CfdiRelacionado`. Una reproducción con ese nodo produce una lista vacía. La fixture existente también usa `Relacionado`, por lo que su prueba no detecta este caso. [Documentación SAT sobre el nodo](https://www.sat.gob.mx/cs/Satellite%3Fblobcol%3Durldata%26blobkey%3Did%26blobtable%3DMungoBlobs%26blobwhere%3D1461175754221%26ssbinary%3Dtrue).

**Propuesta:** corregir XPath y fixtures, conservar todos los grupos de relación con su tipo y reextraer relaciones de los documentos existentes.

### C. La exportación debe respetar el conjunto visible

La pantalla consulta con filtros UUID/RFC/serie/folio. `_run_exportar` llama a los exportadores usando solamente el cliente. Por tanto, una búsqueda en pantalla no limita automáticamente el Excel, y las columnas visibles tampoco constituyen una plantilla de exportación.

**Propuesta:** compartir un objeto de filtros entre tabla, totales, validación y exportación. Ofrecer “vista filtrada”, “selección” y “cliente completo”, indicando filas y alcance antes de generar el archivo.

### D. Robustecer conciliación y estatus

La vista PPD suma documentos relacionados y calcula `total - pagado` con valores convertidos a `float`. Ese recorrido no filtra por estado SAT del REP ni aplica conversión monetaria. Deben definirse reglas consistentes para REP cancelados, documentos repetidos, parcialidades y monedas distintas.

La consulta SAT guarda el estado actual y la fecha de consulta. Esa fecha **no es la fecha de cancelación**; el cliente SOAP actual no devuelve ese dato. Además, el valor vigente sobrescribe al anterior y la consulta normal omite comprobantes que ya tienen estado.

**Propuesta:** usar `Decimal` en los cálculos, diferenciar pagos documentados de movimientos bancarios confirmados, conservar historial de consultas y revalidar según antigüedad o cierre de periodo.

## 8. Funciones recomendadas por prioridad

Esfuerzo relativo: **Bajo**, cambio localizado; **Medio**, varios componentes; **Alto**, modelo, migración, integración o reglas extensas. No son estimaciones de calendario.

| Prioridad | Función | Resultado para el usuario | Esfuerzo | Dependencia |
|---|---|---|---|---|
| P0 | Asociaciones comprobante–cliente | Ver la misma factura en los dos clientes correspondientes | Alto | Migración y adaptación de consultas |
| P0 | Relaciones y exportación coherente | Revisar vínculos reales y exportar lo que se filtró | Medio | Parser y filtros compartidos |
| P0 | Conciliación con reglas monetarias y de estado | Saldos explicables y consistentes | Alto | REP, monedas, cancelaciones y casos de prueba |
| P0 | Validar descarga y actualizar sus pruebas | Saber que solicitud, recuperación y reanudación funcionan | Medio/alto | Contrato vigente del servicio SAT |
| P1 | Ficha completa al hacer doble clic | Emisor, receptor, conceptos, impuestos, REP, nómina y XML en una ventana | Medio | Modelo detallado de conceptos |
| P1 | Menú por comprobante | Copiar UUID, abrir XML, localizar archivo y consultar estado | Bajo | Identificar fila y abrir rutas en Mac/Windows |
| P1 | Filtros avanzados y vistas guardadas | Buscar por fechas, estado, importes, conceptos, moneda y pago | Medio | Filtros compartidos |
| P1 | PDF individual y por lote | Entregar representaciones legibles por UUID | Medio | Conceptos completos y plantillas |
| P1 | Respaldo y restauración | Recuperar catálogo, XML, preferencias y expedientes | Medio | Manifiesto, hashes y copia consistente de SQLite |
| P1 | Historial SAT y alertas | Detectar cambios de vigente a cancelado y consultas vencidas | Medio | Tabla de historial y política de revisión |
| P1 | Panel de incidencias | Revisar XML inválidos, REP huérfanos y referencias ausentes | Medio | Clasificación y evidencia por incidencia |
| P2 | Metadata SAT frente a catálogo | Identificar UUID que el SAT reporta y no están localmente | Alto | Solicitudes de metadata y comparador |
| P2 | Exportación de conceptos | Una fila por producto/servicio con cantidades, claves e impuestos | Medio | Nueva tabla/modelo de conceptos |
| P2 | Análisis de cuentas por cobrar/pagar | Cartera por tercero y saldos documentados | Alto | Conciliación robusta; vencimientos ingresados por usuario |
| P2 | Cruces 69/69-B | Mostrar coincidencias con fuente, situación y fecha | Medio | Actualización de listados oficiales |
| P2 | Descarga programada y carpetas vigiladas | Procesamiento periódico reanudable | Alto | Cola, credenciales protegidas y políticas de ejecución |
| P2 | CFDI 3.3 | Incorporar históricos sin alterar el parser 4.0 | Medio/alto | Parser versionado y modelo común |
| P3 | Validación XSD, cadena original y sello | Diagnóstico documental separado de estado SAT | Alto | Recursos oficiales versionados y validación criptográfica |
| P3 | Bancos y conectores contables | Cruzar movimientos y preparar registros contables | Alto | Formatos objetivo y reglas aprobadas |
| P3 | Complementos adicionales | Carta Porte, comercio exterior o retenciones, según demanda | Alto | Esquemas y casos por complemento |
| P3 | Multiusuario | Distribuir revisión y controlar permisos | Alto | Servicio central y gestión de acceso |

Los listados de operaciones presuntamente inexistentes son una fuente oficial para cruces; deben mostrarse sus diferentes situaciones y fechas, sin convertir toda coincidencia en una conclusión automática. [Consulta oficial SAT](https://www.sat.mx/cs/Satellite?c=ConsultaInfo&childpagename=SatTyR%2FConsultaInfo%2FSAT_LandingConsultaInformacion&cid=1462228576674&packedargs=d%3DTouch&pagename=TySWrapper).

## 9. Cómo implementar los módulos clave

**Ficha de comprobante.** Abrir una ventana con pestañas General, Conceptos, Impuestos, Relaciones, Pagos/Nómina, Historial SAT y XML. Cada importe debe conservar moneda, fuente y precisión. Los datos de negocio y las observaciones se guardan aparte del archivo original.

**Conceptos.** El modelo actual conserva descripciones, no un detalle completo por renglón. Añadir cantidad, unidad, claves SAT, identificación, valor unitario, importe, descuento, objeto de impuesto e impuestos por concepto. Esta base sirve para ficha, PDF, búsquedas y Excel detallado.

**PDF.** Generar desde el XML original y el modelo completo. Incluir UUID, fechas, emisor/receptor, conceptos, impuestos y datos aplicables al tipo de comprobante. Mostrar el estatus consultado con su fecha de consulta. El PDF generado por ConXml debe identificarse como representación del CFDI. Probar paginación con descripciones largas, múltiples conceptos, REP y nómina.

**Motor de incidencias.** Guardar código, severidad, UUID, evidencia y estado de revisión. Ejemplos: referencia sin documento local, REP sin factura, consulta SAT fallida, mismo UUID con contenido diferente y saldo inconsistente. “No hay REP local” debe describir una ausencia documental; no demostrar por sí solo que una factura no fue pagada.

**Metadata.** Crear un almacenamiento independiente de la metadata recibida, con solicitud, RFC, periodo y fecha de recuperación. Comparar por UUID y contexto: presentes en ambos, solo SAT, solo local, discrepancias de estado y datos. La metadata puede aportar fecha de cancelación, dato que no obtiene el cliente SOAP actual. [SAT: recuperación y definición de metadata](https://wwwmatnp.sat.gob.mx/consultas/42968/consulta-y-recuperacion-de-comprobantes-%28nuevo%29).

**Automatización.** Extender el historial de solicitudes con seguimiento por paquete, próximos intentos, caducidad y reanudación. No basta el indicador global `recuperado` para administrar fallos parciales. Dividir rangos y ajustar reintentos a las respuestas del SAT; la ejecución cuando la app está cerrada requiere un mecanismo específico del sistema operativo.

**Credenciales.** La implementación actual carga credenciales por operación y no las persiste en SQLite. Si se ofrece ejecución desatendida, habrá que diseñar almacenamiento protegido por el sistema operativo y autorización por RFC. Esto forma parte del módulo de automatización.

**Rendimiento.** Incorporar índices medidos sobre cliente/fecha, RFC y vínculos REP, paginación de tablas y consultas en segundo plano. El código carga e inserta filas completas en la interfaz; no se hizo un benchmark que permita asegurar un volumen máximo. Medir con lotes sintéticos de 1,000, 10,000 y 100,000 comprobantes y registrar memoria, importación, búsqueda y exportación.

**Respaldo.** Usar copia consistente de SQLite y un manifiesto de XML y configuración, con hashes. La restauración debe comprobar archivos faltantes y conflictos. Un botón de respaldo aporta valor solamente si también existe un flujo de restauración comprobado.

## 10. Ruta de desarrollo y criterios de aceptación

### Entrega 1: datos y reportes confiables

Corregir asociaciones multi-RFC, relaciones, filtros/exportación y conciliación. Actualizar las pruebas de descarga y confirmar el flujo SAT con una cuenta autorizada.

**Aceptación:** un UUID se ve en dos clientes sin duplicar el documento; relaciones con `CfdiRelacionado` se recuperan; Excel coincide con el conjunto anunciado; casos de REP cancelado, duplicado y multimoneda tienen resultados definidos; los errores de servicio quedan registrados y son reintentables.

### Entrega 2: visor práctico

Añadir ficha, conceptos, menú contextual, filtros guardados, PDF y respaldo/restauración.

**Aceptación:** doble clic muestra la información completa; abrir/localizar funciona en Mac y Windows; PDF conserva importes y páginas legibles; un respaldo restaura en una carpeta nueva un expediente equivalente.

### Entrega 3: revisión y auditoría

Añadir historial SAT, incidencias, comparación con metadata, notas y un paquete mensual con XML, PDF, Excel y reporte de revisión.

**Aceptación:** cada alerta tiene motivo, fuente y fecha; una cancelación posterior conserva el estado anterior; se identifica un UUID reportado por el SAT que falta en el catálogo; el paquete reproduce el periodo y cliente seleccionados.

### Entrega 4: automatización e integración

Añadir colas programadas, recuperación parcial, histórico 3.3 y el primer conector contable o bancario según la demanda real.

**Aceptación:** reiniciar no pierde avances ni genera duplicados; las credenciales no aparecen en logs; los reportes conservan alcance y trazabilidad; cada conector tiene una especificación y casos de ejemplo.

## 11. Límites y decisiones de producto

El SAT distingue portal y WebService y publica límites para cada uno: para el WebService señala hasta 200 mil registros por petición y hasta un millón de metadata. ConXml debe presentar progreso, espera y errores, y verificar las condiciones vigentes de la integración. No debe convertir frases comerciales de “descarga ilimitada” en una garantía de disponibilidad. [Información oficial SAT](https://wwwmatnp.sat.gob.mx/consultas/42968/consulta-y-recuperacion-de-comprobantes-%28nuevo%29).

La revisión estructural, la verificación criptográfica y el estado SAT deben verse como resultados separados. Leer un XML sin errores o encontrarlo vigente no determina por sí solo el tratamiento fiscal de una operación.

La generación de DIOT, cálculo de deducibilidad, timbrado, cancelación de CFDI y presentación de declaraciones requieren un alcance adicional y reglas vigentes verificadas. No los incluiría en la primera ampliación. También pospondría IA sobre XML y un editor profesional completo hasta tener datos, validaciones y flujos básicos sólidos.

La ventaja a desarrollar es concreta: **un expediente local por cliente y periodo, con documentos completos, relaciones navegables, saldos explicables y evidencia de revisión**. Esa propuesta aprovecha el producto existente y se puede entregar por etapas verificables.
