# ConXml · Introducción de primera apertura

Composición Hyperframes de 18 segundos, horizontal 1920×1080, en español, con música instrumental suave y sin voz.

## Recorrido

- 0–3 s: bienvenida y marca.
- 3–7 s: selecciona o crea un cliente.
- 7–11 s: carga XML desde la Bóveda.
- 11–15.5 s: consulta SAT, concilia pagos y exporta a Excel.
- 15.5–18 s: bienvenida y siguiente paso.

Los paneles son ilustraciones del flujo, con información de ejemplo.
El reproductor de ConXml superpone un único botón «Saltar» en la esquina
inferior derecha. Al terminar el video continúa automáticamente.

## Revisar y exportar

Desde esta carpeta:

```sh
npm run check
npx hyperframes preview --background
# Después de revisar la vista previa:
npx hyperframes render --quality delivery --fps 30 --output conxml-introduccion.mp4
```

Para detener la vista previa: `npx hyperframes preview --stop`.

El logo y GSAP están guardados localmente. Los archivos editables son
index.html, assets/styles.css y compositions/*.html. El compilador incrusta las
fuentes al preparar la pieza para reproducción y exportación.

## Integración en ConXml

El MP4 está incluido en `src/conxml/ui/assets/introduccion.mp4`.
Se reproduce una sola vez por perfil; saltarlo también marca la introducción
como vista. Al terminar o saltar continúa el inicio habitual. Se puede repetir
con Ayuda → Ver introducción. La música se detiene al cerrar el reproductor.
Si el reproductor falla, el programa continúa y no marca el video como visto.
macOS usa AVKit; Windows usa un reproductor WPF local. No necesita conexión.

## Música

Pista original generada localmente: assets/audio/conxml-bienvenida.wav.
Fuente reproducible: scripts/crear_musica.py (Python y NumPy).
No usa grabaciones ni samples de terceros. Los fades y el volumen se pueden
editar en la pista musica-introduccion de Studio.
