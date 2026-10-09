# Introducción de primera apertura

ConXml incluye un video local de 18 segundos con música instrumental suave,
sin voz. Se muestra una vez por perfil antes de recuperar el cliente de la sesión
o abrir el selector de clientes. El único control es **Saltar**, superpuesto en
la esquina inferior derecha. Al terminar, saltar o cerrar, el inicio continúa.

La preferencia `introduccion_vista` se guarda en `preferencias.json` al salir
correctamente del reproductor, preservando las demás preferencias. Si falla
la reproducción, el inicio continúa y se vuelve a intentar en la siguiente apertura.
**Ayuda → Ver introducción** permite repetirla sin cambiar esa preferencia.

El video y los reproductores están incluidos en la distribución; no requieren
conexión. macOS utiliza AVKit y Windows utiliza WPF mediante PowerShell del sistema.
El reproductor se supervisa sin bloquear Tk y se cierra si se destruye la aplicación.

## Desarrollo y compilación

El proyecto editable está en `videos/conxml-introduccion`. El MP4 exportado se
copia a `src/conxml/ui/assets/introduccion.mp4`. `conxml.spec` incluye ese archivo
y el script de Windows; en macOS compila el reproductor Swift con `swiftc`.
`./scripts/build_mac.sh` genera `dist/ConXml.app` con todos los recursos.

En desarrollo en macOS, el reproductor debe estar compilado en
`build/native/conxml-intro-player`. Si falta, el programa inicia normalmente.

## Verificación

Se verificaron en macOS el botón Saltar visible sobre el video, la salida del
reproductor, la continuación automática al finalizar en la aplicación compilada,
la persistencia de primera apertura y el segundo inicio sin video. Las pruebas
automatizadas cubren fallos de reproducción, preservación de preferencias,
limpieza al cerrar y repetición desde Ayuda. Windows requiere una prueba de
reproducción en un equipo Windows antes de distribuir esa plataforma.
