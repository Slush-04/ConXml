# Tarea activa — ConXml

## Estado

`in_progress` — mejorar instalación inicial y actualización remota en Windows.

## Rama de trabajo

`antigravity/installer-fix`

## Instrucciones para Antigravity

1. Lee este archivo y `TASK_HANDOFF.md` antes de modificar código.
2. No trabajes sobre `main`.
3. No borres datos, certificados, claves ni archivos fuera del repositorio.
4. Reproduce el problema antes de corregirlo cuando sea posible.
5. Ejecuta las pruebas relevantes y registra los comandos y resultados en `coordination/RESULT.md` usando el MCP.
6. Haz commit y push únicamente a `antigravity/installer-fix`.

## Contexto del problema

El usuario reporta dos problemas relacionados:

1. El instalador debe ser sencillo y autocontenido: el `.exe` instalado debe
   incluir todo lo necesario para funcionar, sin exigir Python ni dependencias
   instaladas manualmente en el equipo destino.
2. Después de publicar una nueva versión y ejecutar el instalador, ConXml deja
   de abrir correctamente: parece iniciar y cerrarse inmediatamente. Hay que
   reproducirlo en Windows y conservar un log de arranque útil, porque el GUI
   actual se compila con `console=False`.
3. El usuario quiere que las versiones posteriores se descarguen y actualicen
   desde la aplicación, sin depender de volver a ejecutar manualmente el
   instalador.

## Objetivos de implementación

### A. Instalación inicial

- Verificar en una máquina Windows limpia (sin Python ni las dependencias del
  proyecto) que `ConXml-Setup-X.Y.Z-windows-x64.exe` instala y abre la GUI.
- Confirmar que quedan incluidos el runtime, recursos de CustomTkinter, iconos,
  fuentes, CLI y cualquier recurso requerido por PyInstaller.
- Diagnosticar el cierre inmediato después de actualizar. Registrar errores de
  arranque en una ubicación persistente como `%LOCALAPPDATA%\\ConXml\\logs`,
  sin guardar secretos ni datos sensibles.
- Mantener intactos catálogo, XML, preferencias, respaldos y rutas externas.
- No solucionar el problema ocultando excepciones ni eliminando validaciones.

### B. Actualización directa desde la aplicación

Diseñar e implementar un flujo seguro para que, después de la primera
instalación, ConXml pueda actualizarse desde una Release pública de GitHub sin
abrir manualmente el instalador:

- Mantener la consulta limitada a Releases estables del repositorio fijado.
- Publicar un artefacto actualizable de la aplicación (GUI y, si corresponde,
  CLI) con versión y SHA-256 verificables.
- Descargar a un archivo temporal, validar tamaño, versión, origen y SHA-256,
  y no ejecutar ni reemplazar nada si falla alguna validación.
- Cerrar la GUI de forma ordenada y usar un helper/proceso de actualización que
  pueda reemplazar el ejecutable después de que ConXml termine; no intentar
  sustituir el `.exe` mientras está bloqueado ni depender de que el instalador
  interactivo adivine cuándo cerrar la aplicación.
- Mantener un respaldo antes de actualizar, conservar los datos de usuario y
  relanzar la nueva versión solo cuando el reemplazo haya terminado.
- Implementar rollback o recuperación clara si falla el reemplazo o el nuevo
  ejecutable no puede arrancar.
- Conservar el instalador como mecanismo de instalación inicial y recuperación,
  pero no como requisito para las actualizaciones normales.

## Investigación requerida antes de modificar

Revisar como mínimo:

- `installer/conxml.iss`
- `conxml.spec`
- `scripts/build_exe.ps1`
- `scripts/build_installer.ps1`
- `.github/workflows/windows-release.yml`
- `src/conxml/updates.py`
- `src/conxml/ui/actualizaciones.py`
- `src/conxml/config.py`
- `tests/test_updates.py`
- `tests/test_config_installer.py`

En particular, comprobar la interacción entre `AppMutex`, el proceso GUI
abierto y `Updater.launch()`: actualmente se descarga y lanza el instalador,
pero el reemplazo no debe ocurrir mientras el ejecutable principal siga vivo.

## Criterios de aceptación

- Instalación limpia en Windows 10/11 x64 sin Python: la aplicación abre y la
  GUI no se cierra silenciosamente.
- Si la GUI falla al iniciar, existe un log de diagnóstico legible.
- Actualización de una Release A a una Release B desde la propia aplicación,
  sin ejecutar manualmente `ConXml-Setup-*.exe`.
- La aplicación se cierra, reemplaza el binario, vuelve a abrirse y conserva
  catálogo, XML, preferencias y respaldos.
- Descarga truncada, digest incorrecto, versión incompatible, falta de red,
  falta de espacio o fallo de arranque dejan la versión anterior funcional y
  muestran un mensaje accionable.
- Pruebas automatizadas para validación, descarga, cierre/reemplazo simulado,
  rollback y preservación de datos.
- Prueba real en Windows documentada con comandos, versión de Windows, versión
  anterior/nueva y resultado.

## Restricciones de coordinación

- Trabajar únicamente en `antigravity/installer-fix`; no modificar `main`.
- No subir certificados, tokens, contraseñas, XML reales ni datos del usuario.
- No borrar ni sobrescribir `data/`, respaldos ni el expediente persistente.
- Antes de declarar listo, usar el MCP `publish_result` con resumen, pruebas,
  archivos modificados, bloqueos y hash del commit.
