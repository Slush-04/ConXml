# Web de ConXml

Página estática en español, pensada para presentar ConXml y sus descargas. Todo el contenido y los recursos están dentro de esta carpeta. No necesita instalar dependencias ni compilar.

## Abrir localmente

Abre `index.html` con tu navegador, o haz doble clic en `Abrir página.command` en macOS.

Para servirla por HTTP desde la raíz del proyecto:

```sh
python3 -m http.server 8080 --bind 127.0.0.1 --directory web
```

Abre `http://127.0.0.1:8080`. Para detener el servidor, pulsa Ctrl+C.

## Habilitar las descargas

Edita `config.js`. Mientras `url` esté vacío, la plataforma muestra “En preparación” y la descarga está deshabilitada. Cuando agregues un enlace HTTPS o un archivo relativo válido, la tarjeta se habilitará automáticamente.

Ejemplo de configuración — sustituye los valores por los de tu paquete real:

```js
windows: {
  url: "downloads/ConXml-Setup-VERSION-windows-x64.exe",
  version: "VERSION",
  fileName: "ConXml-Setup-VERSION-windows-x64.exe",
  size: "TAMAÑO"
}
```

Si usas una ruta relativa, crea `web/downloads/` y coloca ahí el archivo. También puedes indicar la URL HTTPS de una descarga publicada. La versión de cada paquete se configura por separado de `projectVersion`.

No se incluyen los binarios existentes en `dist/`: los paquetes locales revisados son 0.2.25, mientras que el código actual es 0.2.31. Así se evita presentar un paquete anterior como si fuera la versión actual.

## Videos del proyecto

La sección “Ver videos” presenta dos piezas locales en formato MP4, con imágenes de portada:

- `assets/videos/conxml-presentacion.mp4` y `conxml-presentacion-poster.jpg`: presentación de ConXml.
- `assets/videos/conxml-reportes.mp4` y `conxml-reportes-poster.jpg`: video promocional sobre consulta SAT, conciliación de pagos y reportes de Excel.

Los reproductores HTML5 usan controles nativos, reproducción dentro de la página en móvil y `preload="none"`. No hay reproducción automática. Cada pieza puede descargarse mediante su enlace “Descargar video”. Los videos incluyen música suave sin narración y usan datos de ejemplo; las ilustraciones pueden diferir de la interfaz de la aplicación.

Las etiquetas de duración están en `index.html`, dentro de los elementos `data-video-duration="presentacion"` y `data-video-duration="reportes"`. Al reemplazar un video, actualiza también su portada y duración. Mantén el formato 16:9 y coloca todos los recursos en `assets/videos/` para que la página funcione sin servicios externos.

## Archivos

- `index.html`: contenido, secciones y preguntas frecuentes.
- `styles.css`: diseño adaptable a escritorio, tablet y móvil.
- `app.js`: vista ilustrativa, navegación móvil y activación de descargas.
- `config.js`: versión del proyecto y enlaces de los paquetes.
- `assets/logo-conxml.png`: copia del logo del proyecto.
- `assets/videos/`: videos MP4 y sus portadas JPG para la sección de presentación.

La vista del producto usa datos ficticios y se identifica como ilustrativa. Las pestañas funcionan con ratón, pantalla táctil y teclado. Las preguntas frecuentes se abren sin JavaScript. El diseño respeta la preferencia de movimiento reducido. No se usan fuentes, analíticas ni bibliotecas externas.

## Publicación en GitHub Pages

Dirección pública: [slush-04.github.io/ConXml](https://slush-04.github.io/ConXml/).

El flujo `.github/workflows/pages.yml` publica automáticamente los cambios de `web/` que lleguen a `main`. También puede ejecutarse manualmente desde **Actions → Publicar web → Run workflow**. En **Settings → Pages**, la fuente de publicación debe ser **GitHub Actions**.

Solo se despliegan `index.html`, los archivos CSS y JavaScript, `assets/` y, cuando exista, `downloads/`. Los videos y sus portadas se sirven desde el mismo sitio. El código Python, los datos de clientes, este README y el acceso local de macOS quedan fuera del sitio publicado.

Para actualizar la página, edita los archivos de esta carpeta y sube esos cambios a `main`. El resultado y el enlace de cada despliegue se consultan en Actions. Para otro alojamiento estático, usa los mismos archivos públicos con `index.html` en la raíz.
