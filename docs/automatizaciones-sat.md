# Automatizaciones SAT propuestas

Revisión del código y documentación oficial: 13 de octubre de 2026.

| Prioridad | Proceso | Qué ahorra | Estado en ConXml |
|---|---|---|---|
| 1 | Descarga incremental de emitidos y recibidos por cliente | Elegir repetidamente RFC, dirección y fechas | Solicitud, seguimiento y recuperación existen. Falta programar nuevas solicitudes por cliente/periodo. |
| 2 | Revisar cancelaciones y estatus de CFDI periódicamente | Consultar folios manualmente y repetir consultas sin necesidad | Consulta en lotes y caché existen. Falta agenda y resumen de cambios. |
| 3 | Descargar metadata y compararla contra UUID locales | Detectar comprobantes ausentes y diferencias de estatus | Función nueva: el cliente actual solicita CFDI, no metadata. |
| 4 | Importar y organizar automáticamente paquetes descargados | Mover archivos y cargarlos de nuevo al visor | Disponible cuando se elige organizar XML e importar. |
| 5 | Cola diaria/semanal para varios clientes | Ejecutar importar, validar y exportar por cliente | Motor semanal por comandos existente; falta pantalla de cola y programación. |
| 6 | Reporte final de anomalías, Excel y respaldo | Preparar entregables y revisar carpetas al terminar | Exportación y respaldo existen; falta encadenarlos y mostrar resumen por cliente. |

El SAT documenta recuperación de XML emitidos/recibidos y metadata, con autenticación
mediante e.firma para el Web Service. La metadata incluye UUID, RFC, fechas, total,
estado y fecha de cancelación. Compararla con el catálogo es una propuesta de
ConXml basada en esos campos, no un servicio adicional prestado por el SAT.

La descarga ya acepta solicitudes y sigue las pendientes mientras ConXml permanece
abierto y la e.firma está activada. Trabajar con la aplicación cerrada requiere un
proceso en segundo plano y una forma acordada de proteger las credenciales en el
sistema. Actualmente no se guarda la contraseña de la e.firma.

Recomendación: implementar primero una cola visible con periodos por cliente,
reintentos, recuperación de paquetes, importación y resumen. Añadir después la
comparación por metadata y la agenda con ConXml cerrado. No se ha implementado
ninguna automatización nueva como parte de esta revisión.

Fuentes oficiales:

- [SAT: consulta y recuperación de comprobantes](https://wwwmatnp.sat.gob.mx/consultas/42968/consulta-y-recuperacion-de-comprobantes-(nuevo)).
- [SAT: servicio de solicitud de descarga masiva](https://www.sat.gob.mx/cs/Satellite?blobcol=urldata&blobkey=id&blobtable=MungoBlobs&blobwhere=1461175195160&ssbinary=true).
- [SAT: documentación del servicio de consulta CFDI](https://www.sat.gob.mx/minisitio/Factura/documentos/cancelacion/ar_consulta_cfdi.pdf).
