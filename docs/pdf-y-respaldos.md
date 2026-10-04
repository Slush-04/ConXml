# PDF y almacenamiento local

## Vista previa y exportación

En Administración XML, Nómina y Pagos:

- Selecciona una fila y pulsa **Vista previa PDF**, o haz doble clic sobre ella.
- Usa **Guardar PDF** para elegir dónde guardar un comprobante.
- Selecciona varias filas con Ctrl/Cmd o Shift y pulsa **PDF selección (ZIP)**.
- **PDF vista (ZIP)** exporta los comprobantes de la tabla actual, respetando los filtros visibles.
- El menú contextual también ofrece las acciones de PDF.

La vista previa incluye navegación entre páginas y un botón para guardar.
El archivo se genera localmente a partir del XML original: datos generales,
emisor, receptor, conceptos, impuestos, relaciones y complementos presentes.
En las vistas de pagos se genera el PDF del REP de la fila seleccionada.
Varias filas de un mismo REP producen un solo PDF en el lote.

Los archivos del ZIP se nombran por UUID. Si algún XML falla, se conservan
los PDF válidos y se incluye `errores.json` con los detalles. Si ninguno se
puede generar, no se sobrescribe el archivo de destino.

## Datos y sesión

Clientes, catálogo, historial de solicitudes SAT y configuración permanecen
en el equipo. Se recuperan el último cliente, la pantalla de trabajo, los
filtros, carpetas de Administración y la vista de pagos. Las preferencias
de columnas siguen guardándose localmente.

La opción de limpiar al leer está desactivada por defecto: importar otro lote
agrega comprobantes sin vaciar el catálogo anterior. Si se activa expresamente
en Ajustes, esa preferencia se conserva.

La ruta de datos aparece en Ajustes. En la aplicación de macOS es
`~/Library/Application Support/ConXml/`; en desarrollo es la carpeta `data`
del proyecto. `CONXML_DATA_DIR` permite configurar otra carpeta local.

## Respaldos

En **Configuración y Ajustes → Respaldos y sesión local**:

- **Crear respaldo** guarda un ZIP en la ubicación elegida.
- **Restaurar respaldo** comprueba formato, archivos, hashes y base de datos
  antes de recuperar la información. Las pantallas se vuelven a cargar con
  la sesión restaurada.
- **Abrir datos locales** abre la carpeta en Finder o el explorador del sistema.

El respaldo automático al cerrar está activado inicialmente. Se conservan los
últimos diez archivos `auto_*.zip` en `data/respaldos`; los respaldos manuales
no se borran por esa política. La aplicación espera a que termine el respaldo
antes de cerrar. Si falla, queda abierta para permitir revisar el error.

Cada respaldo contiene una copia consistente de SQLite, XML disponibles,
preferencias, configuración y archivos del directorio de datos. También
incorpora los XML externos referenciados por el catálogo y adapta sus rutas
al restaurarlos. Si un XML ya no existe, se registra en `manifest.json` y se
avisa al usuario. Conviene conservar los XML de origen o ingresarlos a la Bóveda.

No se incluyen respaldos anteriores, vistas previas temporales ni archivos
`.cer`/`.key`. Las contraseñas y tokens de e.firma no se guardan en la sesión.

Antes de sustituir datos durante una restauración, el directorio actual se
conserva junto al nuevo, con nombre `*_antes_restaurar_<fecha>`. El mensaje
de restauración muestra su ubicación. No se elimina automáticamente.

## Logo

El PNG y los iconos ICO/ICNS usan transparencia real en el hueco central.
Se regeneraron las versiones para Windows y macOS a partir del logo corregido.

## Formato de factura (referencia SAT)

La vista previa y las descargas individuales o por lote utilizan el mismo diseño: datos del emisor y receptor en dos columnas, folio fiscal, certificados y fechas; tabla de conceptos; forma y método de pago; impuestos y total; complementos y certificación digital. Una factura sencilla cabe en una página y los documentos extensos se paginan sin recortar conceptos.

El QR se genera localmente con UUID, RFC del emisor, RFC del receptor, total y los últimos ocho caracteres del sello. Abre la consulta del SAT al escanearlo; generar el PDF no realiza esa consulta. Si faltan datos, el PDF indica que el QR no está disponible. La cadena original se reconstruye para timbres versión 1.1 completos; los sellos se toman del XML, sin validar firmas durante esta exportación.

Referencias consultadas:

- [SAT: ejemplo de representación gráfica CFDI 4.0, apéndice 4, página 38](https://www.sat.gob.mx/minisitio/Factura/documentos/Guia_llenadoCFDI_DPA.pdf).
- [SAT: Anexo 20, QR y secuencia del timbre fiscal digital 1.1](https://www.sat.gob.mx/cs/Satellite?blobcol=urldata&blobkey=id&blobtable=MungoBlobs&blobwhere=1461176340698&ssbinary=true).

El botón del menú está junto al nombre ConXml, en la cabecera lateral. Al contraer la navegación, permanece visible en una franja estrecha a la izquierda para desplegarla de nuevo.

### Diseño cercano al ejemplo visual del SAT

El PDF se presenta en A4 horizontal, en blanco y negro. La cabecera utiliza dos columnas sin líneas; cada concepto muestra una tabla gris con clave de producto, identificación, cantidad, clave de unidad, unidad, valor unitario, importe, descuento, pedimento y cuenta predial. La descripción y el desglose de impuestos aparecen debajo. Los totales quedan alineados a la derecha y los sellos ocupan el ancho de la página, seguidos del QR y los datos de certificación. La leyenda de representación impresa se muestra en el pie de cada página. Los números de anotación del ejemplo didáctico no forman parte del diseño. Los importes conservan los decimales del XML.

### Nitidez y zoom del visor

En macOS, el visor utiliza el renderizado nativo de PDF mediante PDFKit en una ventana propia para conservar el texto vectorial en pantallas Retina. En otros sistemas utiliza PDFium con resolución calculada a partir del tamaño de visualización y sobremuestreo. Los controles «+», «−» y «Ajustar» (macOS) o «Ajustar ancho» (otros sistemas) permiten ampliar y recuperar la vista; las barras de desplazamiento permiten recorrer la página en ambas direcciones. La rueda desplaza verticalmente y Mayús + rueda, horizontalmente. Esta mejora afecta la vista previa y conserva el PDF original al guardar.
