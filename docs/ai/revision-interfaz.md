# Revisión de la interfaz adaptable

Muse Spark 1.3 Free implementó la propuesta mediante OpenCode en una copia
aislada. Codex revisó el parche antes de aplicarlo y corrigió la distribución
del selector de carpeta, los márgenes verticales, el cálculo de escalado y la
apertura automática de detalles después de operar en ventanas pequeñas.

La ventana ajusta su tamaño inicial a la pantalla. Al redimensionarla, reduce
la barra lateral, envuelve encabezados y oculta paneles secundarios cuando
falta altura. Los controles permiten mostrarlos manualmente. Las tablas se
conservan, incluyendo filas y selección, y mantienen ambos desplazamientos.

Validación en macOS con Python 3.13 y ventanas reales de CustomTkinter:

- 94 pruebas aprobadas; 1 prueba de integración externa excluida.
- Tablas de CFDI, pagos y nómina en 900x650, 1024x768, 1366x768,
  1440x900 y 1920x1080.
- Escalado al 100 %, 125 % y 150 %, con comprobación de altura útil de tabla
  después de mostrar información de una operación.
- Botones dentro de la ventana, desplazamientos accesibles y conservación
  de datos/selección durante cambios de tamaño.

Comando: `.venv/bin/python -m pytest -q`.

La implementación utiliza Tk/CustomTkinter compartidos por Mac y Windows.
Todavía falta comprobarla en un equipo Windows real; la simulación de escalado
en macOS no sustituye esa comprobación. La adaptación prioriza laptops; no se
ha validado en pantallas extremadamente pequeñas.

Estos cambios están en la carpeta local. No se han publicado en GitHub.
