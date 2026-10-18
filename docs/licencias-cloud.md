# Licencias de prueba cloud

La integración se activa **solo en una edición compilada de prueba**. El código de
este checkout y las ediciones anteriores quedan exentos. No hay una política
comercial/perpetua ni un plazo de prueba fijo: el administrador elige los días al
crear cada licencia (1–365) y las plazas (1–10). El servicio del piloto está desplegado y activo en
`https://conxml-licensing.slush04-conxml.workers.dev`.

## Preparar una edición de prueba

Crear un JSON privado de distribución (contiene exclusivamente datos públicos):

```json
{
  "service_url": "https://TU-SERVICIO.workers.dev",
  "trusted_keys": {"ID-DE-FIRMA": "CLAVE-PUBLICA-ED25519-BASE64URL-SIN-PADDING"}
}
```

La clave debe corresponder al firmante de producción, tener 32 bytes y codificarse
como base64url sin `=`. No incluir códigos, tokens ni una clave privada.

En macOS, antes de ejecutar el build habitual:

```sh
export CONXML_TRIAL_CONFIG=/ruta/absoluta/politica-publica.json
./scripts/build_mac.sh
```

En PowerShell:

```powershell
$env:CONXML_TRIAL_CONFIG = 'C:\ruta\politica-publica.json'
.\scripts\build_exe.ps1
```

`conxml.spec` valida el archivo y sustituye `conxml.distribucion` dentro de los
archivos Python de GUI **y CLI**. Una configuración inválida aborta la compilación.
La aplicación instalada no consulta esa variable ni un JSON externo para decidir
si exige licencia. La ausencia de claves/HTTPS en modo `trial` bloquea el arranque.
Sin esa variable al compilar se obtiene la edición de desarrollo exenta: identificar
claramente el artefacto antes de entregarlo. No publicar builds de desarrollo como
una edición protegida. Este procedimiento no firma el ejecutable con un certificado
Windows/macOS; eso corresponde al proceso de distribución.

## Compilación desde main en GitHub Actions

El workflow `Windows build` incorpora `config/licensing-trial.json`, con la URL y
clave pública de producción. Al solicitar una versión desde el Administrador, los
ejecutables GUI y CLI se generan como edición de prueba. El token administrativo y
la clave privada permanecen fuera del repositorio y del instalador.

La prueba del instalador consulta `conxml-cli licencia edicion`, comprueba que la CLI
rechace una importación sin licencia antes de crear el catálogo y verifica que la GUI
muestre la activación al instalar/actualizar. Esto no sustituye la prueba de activación
completa en un Windows con una licencia del piloto. El workflow conserva el instalador
como artefacto privado; publicar una Release sigue siendo una acción separada.

## Uso

La GUI presenta el aviso de actividad, el código y las acciones de activar,
reintentar o cerrar antes de mostrar el catálogo. En CLI:

```sh
conxml licencia activar
conxml licencia estado
```

El código se introduce sin eco y no se conserva. La identidad UUID y el token se
guardan juntos en el almacén seguro **antes** del primer envío. Se usa un servicio
de keyring independiente del monitor directo y del administrador. Los reintentos
reutilizan esa identidad, incluso si se perdió la primera respuesta. Nunca se inicia
un plazo local cuando no se puede activar.

Las señales automáticas se realizan cada 300–330 segundos. Los errores usan backoff
con jitter y respetan `Retry-After` numérico en 429; sin un valor válido se esperan
al menos 5 minutos. No hay redirecciones; las respuestas están acotadas, las peticiones
tienen timeout y los mensajes no incluyen cuerpos ni credenciales. Un fallo de red
conserva únicamente el permiso firmado anterior hasta su vencimiento.

El permiso se comprueba con claves incluidas, identidad, emisor, audiencia, nonce y
revisiones. El estado autoritativo (incluidas denegaciones y revisiones por licencia)
está en keyring; la copia JSON se reemplaza atómicamente antes de guardar en keyring y no puede
conceder permisos por sí sola. Una caché corrupta, ausente o distinta del keyring
exige validación online. Si el keyring falla al guardar una denegación, el diario
firmado conserva sus revisiones para impedir reutilizar el permiso previo al reiniciar. Un keyring corrupto o inaccesible bloquea el acceso y exige
recuperación administrativa, sin generar otra identidad silenciosamente.

La hora firmada se ancla al reloj monotónico durante la sesión. Se conserva el máximo
consumido y la hora local en el almacén seguro; un retroceso requiere validación
online y un reloj futuro nunca amplía el permiso. En cada arranque offline se consumen
conservadoramente hasta 30 segundos adicionales para cubrir el intervalo entre
persistencias. Reiniciar repetidamente con el reloj congelado no reinicia la ventana.
El permiso acaba como máximo a las 24 horas o al fin original de la prueba.

La carpeta `.conxml-licensing`, junto a la carpeta de configuración de ConXml, está
fuera del expediente fiscal habitual y contiene solo el bloqueo de sesión y una copia
del permiso, además de la outbox técnica `telemetry.json`. No contiene el token ni el código. No incluir esa carpeta ni el keyring
en respaldos fiscales. Restaurar un respaldo de ConXml no revierte una denegación.

Solo se admite una sesión de la edición de prueba por instalación, compartida entre
GUI, CLI y ejecutor periódico. Una segunda sesión informa que ConXml está abierto;
una tarea del sistema se reintentará en su siguiente ejecución. Se envía `closed`
al cerrar normalmente, con UUID y secuencia de sesión para que un cierre tardío no
oculte una nueva apertura. Sin señal durante 900 segundos se muestra inactivo;
esto no equivale a cierre ni revocación. Si se cierra sin internet, el informe
queda pendiente hasta una validación posterior. Un cierre inesperado se identifica
al siguiente arranque usando la última observación guardada, sin contar el intervalo
en que ConXml estuvo apagado.

El control se comprueba antes de una operación GUI, un comando CLI y cada tarea
SAT/cliente semanal nuevo. Una operación en curso termina; el modal espera a que
termine y a que se cierren los diálogos existentes. Los datos no se eliminan.
El monitor directo mantiene sus propios mensajes/bloqueos: **ambos** controles
deben permitir el acceso; una licencia nueva no elimina un bloqueo del monitor.

## Administrador y cambio de licencia

El proyecto hermano `ConXml-UpdateManager-main` añade **Licencias y pruebas**:
URL HTTPS, credencial en keyring separada, consulta manual, creación con duración
explícita y código visible una vez con botón Copiar, bloqueo/desbloqueo por equipo
o licencia y revocación con confirmación. Se presentan actividad y acceso por
separado, sistema operativo, primera activación, vencimiento, días restantes, última IP, versión y señal.
Los días se calculan con la hora del servicio, redondeando hacia arriba; cero significa
que venció y una licencia sin activar no tiene fecha ni días restantes. Cada equipo
muestra su primera activación; la licencia muestra la primera de cualquiera de sus equipos. Un fallo conserva la última lista y su hora de
sincronización. Las consultas del panel no afectan a las validaciones de los clientes.

Una instalación con prueba vencida o licencia bloqueada/revocada puede introducir
otro código válido sin cambiar su UUID/token. El servicio comprueba plazas y plazo
en la misma transacción; no reinicia una licencia ya activada. Un bloqueo del equipo
impide ese cambio y requiere que el administrador lo retire. No se cambia una
licencia aún vigente mediante este flujo. Un código nuevo no recupera una credencial
perdida ni sustituye un equipo físico: esos flujos requieren endpoints propios.

## Validación antes de entregar a interesados

Las pruebas locales cubren firma, nonce, permisos antiguos, persistencia de bloqueo,
vencimiento con reloj congelado, reinicios, retroceso/futuro, fallos de keyring/red,
una sesión por instalación, CLI y espera de operaciones/diálogos. El servicio usa
D1 local para verificar plazas, reintentos, cambio de licencia y concurrencia.

El despliegue y las credenciales reales del piloto ya están configurados. Siguen
pendientes la retención general de licencias/IP y respaldos D1, auditoría ampliada de transferencias, recuperación de
credenciales y reasignación de equipos. Mensajes cloud y ampliación de plazo siguen
fuera de esta API. Antes de publicar se necesita probar el instalador Windows real
(con/sin red, cambio de reloj, cierre durante una escritura, actualización y
restauración) sin XML reales. Las pruebas locales no certifican esa experiencia ni
resistencia a modificar el ejecutable o restaurar todo el sistema/keyring.

## Comprobación local de esta integración

- 66 pruebas de licencias, transporte, política de distribución, diálogo y controles
  anteriores: correctas, incluyendo fallo de keyring tras recibir una denegación.
- 75 pruebas del Administrador y 11 subpruebas: correctas.
- 20 pruebas Worker/D1 local: correctas; `npm run check` completó el dry-run con
  `API_ENABLED=false`. El contrato de firmas JavaScript/Python también pasó.
- La revisión general sin pruebas de interfaz completó 278 pruebas, con 14 omitidas
  y una integración deseleccionada. La suite GUI completa se detuvo por un ciclo de
  `CTkScrollbar.set/_draw/update_idletasks` en la prueba de diseño a 900×650.
  Ese código de scroll tenía cambios previos a esta tarea y no se modificó aquí.
- El diálogo nuevo de activación sí se abrió y comprobó con Tk real en una prueba.
  En esta comprobación inicial todavía no se había generado el instalador Windows
  ni desplegado el Worker; ver el avance posterior siguiente.

## Avance del piloto, 16 de octubre de 2026

La compilación 0.2.32 pasó 372 pruebas y la comprobación de Setup, cierre, reemplazo,
versión, GUI y conservación de datos en Windows:
https://github.com/Slush-04/ConXml/actions/runs/38910662925.
La política de prueba se comprobó dentro de los archivos GUI y CLI, y la CLI rechazó
una operación sin activación antes de crear su catálogo.

La API está activa y se verificó contra el servicio real con autenticación
administrativa, activación, firma con la clave pública incluida en el instalador,
bloqueo/desbloqueo y revocación firmada. La licencia técnica usada se revocó al
terminar. Los días para interesados se eligen en el Administrador; el día usado por
esa comprobación interna no define la duración del piloto. No se enviaron datos fiscales.

Para empezar una prueba: Administrador → Licencias y pruebas → Actualizar lista →
Crear prueba. Elegir etiqueta, días y equipos; copiar el código en su única
presentación e introducirlo en la edición Windows de prueba. No hace falta
recompilar para usar la API activada. Falta validar manualmente ese recorrido
completo en Windows con/sin red y con cambio de reloj antes de ampliar la distribución.

## Sesiones y diagnóstico técnico

En **Licencias y pruebas**, selecciona un equipo y pulsa **Ver sesiones y diagnóstico…**.
El detalle presenta aperturas, cierres informados, última observación de sesiones
interrumpidas y tiempo aproximado con ConXml abierto. Distingue ventana, comando
y tarea programada. Los totales corresponden exclusivamente al historial disponible;
no son tiempo de trabajo del usuario ni un contador de actividad de teclado/ratón.

La duración usa el reloj monotónico, se actualiza con cada señal y se conserva en
una outbox local acotada cuando falla la conexión. Los reintentos se deduplican
por UUID y revisión; solo una respuesta con permiso firmado válido permite confirmar
los datos enviados. Un fallo del archivo técnico no concede permisos ni bloquea
la licencia. Las fechas de sesión son aproximadas y no cambian el vencimiento.

Se envían únicamente categorías de fallos de operaciones, interfaz, comandos y
consulta/descarga/instalación de actualizaciones, junto a un tipo de excepción permitido.
No se envían mensajes de excepciones, trazas, rutas, registros completos, XML, RFC
ni credenciales. Al volver a abrir se reconocen marcadores de fallo del helper de
actualización y se envía solo la categoría. El panel muestra la hora de recepción
del diagnóstico, que puede ser posterior al error si no había conexión.

Cada equipo conserva como máximo 30 sesiones y 50 errores recibidos dentro de
los últimos 30 días. Una limpieza diaria elimina registros técnicos antiguos
incluso si el equipo no vuelve a conectar. No borra licencias, equipos ni fechas
de activación. Es necesario aplicar `0002_telemetry.sql` antes del nuevo Worker.
Los clientes 0.2.32 siguen validando con el contrato previo; aportarán sesiones y
diagnóstico al instalar una compilación con esta mejora. No se reconstruye historial anterior.

## Verificación de sesiones y diagnóstico, 17 de octubre de 2026

La API está desplegada con `0002_telemetry.sql` y se verificó con activación firmada,
sesión, diagnóstico técnico, cierre y lectura administrativa. Las licencias y equipos
existentes conservaron fechas, permisos e identidades. La prueba técnica quedó revocada.
El Administrador pasó 86 pruebas y 11 subpruebas, además de una comprobación con Tk real;
el servicio pasó 24 pruebas Worker/D1 local y el dry-run de Wrangler.

La compilación Windows 0.2.33 pasó 387 pruebas (12 omitidas, una integración
deseleccionada), generó la edición protegida y completó la instalación y actualización
reales con conservación de datos. Build:
https://github.com/Slush-04/ConXml/actions/runs/39084068213.
La validación incluyó persistir denegaciones recibidas al cerrar, incluso si falla
el keyring, y corregir fixtures de ZIP/UTF-8 para que las pruebas sean portables.

El instalador está como artefacto privado y registrado como build pendiente en el
Administrador para **Descargar build**; todavía requiere publicar la actualización
para distribuirla. Los equipos con 0.2.32 necesitan actualizarse para enviar sesiones
y diagnóstico; sus permisos y fechas actuales se conservan.
