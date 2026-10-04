# Descarga SAT

## Flujo disponible

En **Administración XML → Descarga SAT**, la aplicación toma el RFC del cliente
activo. El usuario elige **Emitidos** o **Recibidos**, el periodo, el tipo de
CFDI y los archivos `.cer` y `.key` de la e.firma vigente. La contraseña de la
llave se solicita al operar y se elimina del campo al iniciar la tarea.

ConXml autentica con el SAT, envía la solicitud y conserva en SQLite su
identificador y estado. El SAT procesa la solicitud de forma asíncrona. Desde el
historial se consulta su avance; cuando termina, ConXml baja los paquetes ZIP,
extrae los XML, los acomoda en la Bóveda del cliente y los incorpora al catálogo
del visor. El sistema registra que el paquete ya se recuperó para no descargarlo
una segunda vez por accidente.

Los certificados, las llaves privadas, las contraseñas y los tokens no se guardan
en el catálogo. El historial sí persiste para que el usuario pueda continuar el
seguimiento después de reiniciar ConXml. La conexión con el SAT requiere Internet
y que la e.firma corresponda al RFC del cliente.

Para instalar las dependencias de esta versión en el entorno local:

```sh
python -m pip install -e .
```

## Condiciones publicadas por el SAT

La consulta oficial indica hasta 200,000 registros de CFDI por solicitud en el
WebService, con un millón de registros de metadata. Las solicitudes se procesan
de forma asíncrona y sus paquetes pueden vencer. Antes de recuperar periodos
grandes, conviene dividir la búsqueda si el SAT responde que excede los límites.

- [SAT: Consulta y recuperación de comprobantes](https://wwwmat.sat.gob.mx/cs/Satellite?c=ConsultaInfo&childpagename=SatTyR%2FConsultaInfo%2FSAT_LandingConsultaInformacion&cid=1462231542968&packedargs=d%3DTouch&pagename=TySWrapper)
- [SAT: direcciones vigentes de los servicios web](https://wwwmat.sat.gob.mx/cs/Satellite?blobcol=urldata&blobkey=id&blobtable=MungoBlobs&blobwhere=1461174995058&ssbinary=true)
- [SAT: documentación de solicitudes de descarga](https://wwwmat.sat.gob.mx/cs/Satellite?blobcol=urldata&blobkey=id&blobtable=MungoBlobs&blobwhere=1461175195160&ssbinary=true)
- [SAT: documentación de verificación de solicitudes](https://wwwmat.sat.gob.mx/cs/Satellite?blobcol=urldata&blobkey=id&blobtable=MungoBlobs&blobwhere=1461175779527&ssbinary=true)

## Pendiente

La descarga manual desde ConXml ya queda automatizada con el WebService. La
ejecución periódica mientras la aplicación está cerrada y el inicio automático
con el equipo son funciones separadas que aún no están implementadas.

La primera conexión con una e.firma real debe hacerse localmente, con archivos
del RFC autorizado; no se deben compartir e.firma, contraseña, token ni CFDI reales
por chat o en GitHub. La disponibilidad y el comportamiento final de la
integración deben confirmarse frente al SAT con una cuenta autorizada.
