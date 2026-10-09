# Investigación del instalador y actualizaciones Windows

La detección y descarga de una Release son distintas de su aplicación. El flujo
actual usa Inno Setup para instalación inicial y un ZIP con dos ejecutables para
actualizaciones, descargados de Releases públicas de GitHub con SHA-256. La última
Release consultada durante esta investigación fue v0.2.23 y contiene ambos formatos.

## Hallazgos y correcciones

- Fallo reproducido de arranque: PantallaDescargas agregaba el botón de seguimiento
  con pack a un contenedor cuyos otros hijos usan grid. Tkinter lanza TclError al
  construir ConXmlApp, incluida la apertura automática con cliente guardado. El
  botón ahora usa grid. Este error de interfaz es independiente de detectar o
  descargar correctamente una actualización.

- La prueba con ejecutables reales reprodujo un fallo adicional en Windows
  PowerShell 5.1: después de copiar y validar la versión, Start-Process falló con
  "Unable to find the specified file" al relanzar desde la ruta con corchetes y
  apóstrofe. El arranque y el relanzamiento tras rollback ahora usan directamente
  ProcessStartInfo con FileName y WorkingDirectory literales y UseShellExecute=false.
- PyInstaller onefile ejecuta un bootloader y un hijo con la GUI. Esperar solo al
  PID de la GUI no garantiza que el archivo del bootloader esté liberado. El helper
  ahora espera a que desaparezcan los procesos cuyo ExecutablePath coincide con
  los ejecutables de la instalación. Incluye el CLI; vence tras 60 segundos y
  diagnostica los PID antes de modificar archivos. Las copias conservan reintentos,
  SHA-256 y rollback. Esto corrige una condición posible; sin los registros del
  equipo afectado no permite atribuirle con certeza el fallo reportado.
- PowerShell se inicia fuera del entorno de búsqueda de DLL de PyInstaller y el
  reinicio usa PYINSTALLER_RESET_ENVIRONMENT=1. El entorno de DLL de la aplicación
  se restaura después de lanzar el helper.
- El camino alternativo de Setup ahora comparte confirmación de arranque y registro
  persistente con el ZIP, escribe PowerShell UTF-8 con BOM, espera los procesos
  instalados, fija /DIR a la instalación en ejecución y conserva el instalador si
  falla o se cancela. El camino Setup sigue siendo interactivo.
- Un ZIP incompleto o con ejecutables duplicados falla antes de cerrar la aplicación.
- Inno conserva explícitamente la carpeta previa. AppId y AppMutex permanecen estables.

## Referencias comparables

[Velopack en Windows](https://docs.velopack.io/packaging/operating-systems/windows)
usa un Update.exe externo y una carpeta current sustituible. Controla bloqueos de
procesos y, si no puede completar la actualización, presenta el error y abre la
versión anterior. Sus accesos directos apuntan a un lanzador estable.

[Electron/Squirrel.Windows](https://www.electronjs.org/docs/latest/api/auto-updater/)
cierra las ventanas y termina la aplicación en quitAndInstall antes de aplicar la
actualización. El patrón aplicable a ConXml es separar descarga, cierre, sustitución
y reinicio; detectar una versión por sí solo no prueba que se haya instalado.

[PyInstaller](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html)
documenta tanto los dos procesos de onefile como el reinicio independiente y la
restauración de SetDllDirectoryW al ejecutar herramientas externas.

[Inno AppMutex](https://jrsoftware.org/ishelp/topic_setup_appmutex.htm) bloquea Setup
mientras existe el mutex de la aplicación. [UsePreviousAppDir](https://jrsoftware.org/ishelp/topic_setup_usepreviousappdir.htm)
recupera el destino anterior desde el registro.

## Validación y límites

Las pruebas PowerShell ejecutan la transacción con archivos reales y procesos
simulados: ventana en bootloader/hijo, cierre del bootloader, bloqueo persistente,
fallos de respaldo/copia/arranque, versión incorrecta, rollback y handshake.

scripts/test_installed_update.ps1 añade una prueba Windows con artefactos compilados:
instala Setup en una ruta con espacios, corchetes, apóstrofe y acento, abre la GUI,
la cierra sin matar el bootloader, reaplica los ejecutables mediante el helper,
comprueba hashes, versión CLI, apertura de ventana y datos conservados. La
compilación Windows exige que pase antes de entregar los artefactos y guarda logs.
Esta prueba reaplica la misma versión: no reemplaza una prueba de migración desde
una versión pública anterior ni una prueba de descarga remota de extremo a extremo.
El camino interactivo de Setup tampoco se automatiza en esta prueba.

La actualización ZIP no actualiza la versión de desinstalación en el registro de
Windows; la versión efectiva se obtiene del CLI y de la aplicación. Migrar a
Velopack requeriría cambiar paquetes, publicación y compatibilidad con instalaciones
existentes; no es un cambio necesario para corregir estas condiciones de arranque.

Las correcciones necesitan compilarse y distribuirse. Un ejecutable ya instalado
con el actualizador antiguo no obtiene código nuevo hasta completar una instalación.
Para recuperarlo, ejecutar manualmente el Setup corregido sobre la instalación
existente, con ConXml cerrado. Luego validar una actualización entre dos versiones.

Diagnóstico en %LOCALAPPDATA%\ConXml\logs:
actualizacion.log, actualizacion-launcher.log y actualizacion-setup.log.
