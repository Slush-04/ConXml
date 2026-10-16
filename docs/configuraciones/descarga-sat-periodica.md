# Descarga SAT periódica

La programación y la autorización de la e.firma se administran por cliente en **Configuración → Descarga SAT periódica**.

1. Registra el RFC del cliente.
2. En esa sección de Configuración, pulsa **Autorizar e.firma…** y selecciona el certificado `.cer`, la llave `.key` y su contraseña. La contraseña se guarda en el almacén seguro del sistema, separado del catálogo y de las preferencias.
3. Configura dos horarios independientes: **Solicitar XML** y **Revisar y organizar XML**. Puedes elegir frecuencia diaria o semanal, intervalo, día y hora de 24 horas.
4. Elige los días completos por solicitud, la dirección (emitidos, recibidos o ambos), el tipo CFDI y la zona horaria.
5. Activa la programación para ese cliente y pulsa **Guardar programación**.

Los valores iniciales son solicitar los viernes a las **16:00**, revisar los lunes a las **08:00**, y abarcar los últimos siete días completos, en `America/Merida`. Se pueden cambiar antes de activar. Guardar un horario nuevo establece un nuevo punto de inicio; no genera solicitudes retroactivas.

La solicitud enviada el viernes queda registrada. El lunes se consulta el SAT: cuando el estado sea **Terminada** y existan paquetes, se descargan los XML, se organizan en la bóveda por cliente, dirección, año y mes y se importan al catálogo. Si todavía está en proceso, se revisará en el próximo horario configurado; también puedes consultar manualmente. El seguimiento manual por minuto no adelanta la revisión de las solicitudes periódicas.

## Con la aplicación cerrada

ConXml registra un ejecutor del usuario en el programador del sistema: `launchd` en macOS, Programador de tareas en Windows, y un temporizador de usuario de systemd en Linux. El ejecutor comprueba cada minuto si corresponde alguna tarea y termina después del trabajo. El equipo debe estar encendido, con la sesión del usuario iniciada y acceso a Internet. Si estuvo suspendido, se ejecuta el último horario pendiente al volver a estar disponible.

La autorización usa Keychain en macOS, Credential Locker en Windows o Secret Service en Linux. No se usa un archivo de contraseñas en texto plano. En otro equipo, o si cambias la e.firma o el RFC, vuelve a autorizar. **Revocar autorización** retira la contraseña del almacén del sistema.

Cada horario queda registrado y un bloqueo entre procesos evita que la interfaz y el ejecutor envíen la misma tarea. Un envío con respuesta incierta no se reenvía automáticamente; revisa el historial y el estado de la última tarea en Configuración. Las tareas que no pudieron comenzar por falta de autorización vuelven a estar disponibles al autorizar la e.firma.

## Historial y columna Bajar

La tabla selecciona filas completas y reparte sus columnas en el ancho disponible. Junto a **Respuesta SAT**, el icono de **Bajar** permite guardar el ZIP de la solicitud o extraer sus XML en una carpeta. Si aún no se entregaron paquetes, primero consulta el estado.

Las solicitudes y su caché de paquetes están disponibles **14 días desde la creación de la solicitud**. Al vencer, se elimina la fila del historial y la copia temporal usada para Bajar. Los XML organizados en la bóveda y las copias exportadas a una carpeta elegida por el usuario se conservan. La limpieza ocurre en el ejecutor y al abrir Descargas SAT.

Si el SAT entregó varios paquetes, Guardar ZIP crea un archivo que contiene esos paquetes originales. Extraer XML separa los archivos en carpetas por paquete para evitar colisiones de nombres.

## Referencias de integración

- [Almacenes seguros compatibles y API de keyring](https://keyring.readthedocs.io/en/latest/).
- [Agentes de usuario y ejecución periódica de launchd](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html).
- [Creación de tareas programadas en Windows](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create).
