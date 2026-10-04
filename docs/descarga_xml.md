# Descarga SAT

## Flujo disponible

En **Administración XML → Descarga SAT**, la aplicación toma el RFC del cliente
activo. El usuario elige **Emitidos** o **Recibidos**, el periodo, el tipo de
CFDI y los archivos `.cer` y `.key` de la e.firma vigente. La contraseña de la
llave se solicita al operar y se elimina del campo al iniciar la tarea.

ConXml autentica con el SAT, envía la solicitud y conserva en SQLite su
identificador y estado. El SAT procesa la solicitud de forma asíncrona. Desde el
historial se consulta su avance; cuando termina, ConXml baja los paquetes ZIP
y aplica el modo y destino elegidos en Configuración. El sistema registra que
la solicitud ya se recuperó para no descargarla
una segunda vez por accidente.

## Elegir dónde y cómo guardar

En **Configuración y Ajustes → Destino de descargas SAT**:

1. Elegir **Organizar XML e importar al visor** o **Conservar ZIP sin extraer**.
2. Elegir una carpeta con **Elegir carpeta…** o escribir su ruta completa.
3. Pulsar **Guardar destino y modo**. La elección se conserva al reiniciar.

En modo organizado, la carpeta elegida se convierte en la raíz de Bóveda.
Los XML se guardan como `cliente/Emitidos|Recibidos/año/mes/archivo.xml`, usando
el RFC y la fecha del CFDI, y se importan al visor. El destino predeterminado
es la bóveda local existente.

En modo ZIP, los bytes recibidos se guardan intactos en
`carpeta/cliente/solicitud/paquete.zip`, sin extraer, clasificar ni importar XML.
Puedes mover y extraer los paquetes manualmente; después puedes copiar los XML
desde Bóveda. Este modo conserva la raíz de Bóveda configurada previamente.
Su carpeta predeterminada es `descargas_sat` dentro de los datos locales.

Cada modo conserva su propia carpeta. Cambiar el destino se aplica a próximas
recuperaciones: no migra ni borra los archivos anteriores. Al cambiar la raíz
de Bóveda, su vista muestra la nueva carpeta; para ver los archivos anteriores,
vuelve a elegir la raíz anterior o cópialos manualmente. El catálogo y el
historial de solicitudes SAT permanecen en la misma base de datos.

Las opciones afectan únicamente a los paquetes recuperados por ConXml. Si
descargas directamente en un navegador, el destino lo controla el navegador.

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
