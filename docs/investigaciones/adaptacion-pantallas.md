# Adaptación de ConXml a pantallas y escalado

La distribución responde al espacio de la ventana y sus paneles en unidades lógicas. El escalado DPI mantiene legibles los controles; no debe utilizarse para encoger el contenido hasta que quepa.

## Reglas implementadas

- La navegación se compacta por debajo de 1100 unidades; con menos de 800 de altura se prioriza la tabla.
- Descargas distribuye sus dos paneles según el ancho lógico disponible del formulario; las acciones de e.firma saltan de fila.
- `BarraAdaptable` convierte las posiciones mediante `CTk.place`, conserva el escalado y recalcula al cambiar el tamaño de sus controles.
- Los textos adaptables calculan el ancho al instalarse, incluso en paneles ya visibles.
- Los indicadores del resumen usan filas adaptables y Clientes permite desplazamiento horizontal sin estrechar las columnas por debajo de su ancho legible.
- El visor PDF redistribuye paginación, guardado y zoom en varias filas al reducirse el diálogo.
- La ventana inicial y los diálogos de columnas y PDF limitan sus dimensiones al espacio disponible. Windows consulta el área útil del monitor del padre. macOS/Linux usan el tamaño proporcionado por Tk y reservan márgenes; la identificación precisa del área útil por monitor queda pendiente en esas plataformas.

## Validación reproducible

Ejecutar con el Python del entorno que tenga Tk disponible:

```sh
python -m pytest tests/test_widgets_adaptables.py tests/test_descargas_responsive.py tests/test_geometria_pantallas.py
python -m pytest tests/test_ui_responsive.py tests/test_ui_design.py tests/test_ui_smoke.py tests/test_columnas.py tests/test_ui_pdf_local.py
```

Las pruebas nuevas cubren 100 %, 125 %, 150 % y 200 %, cambios de texto, reflujo y límites de geometría. Las pruebas de interfaz requieren un escritorio. Los cálculos de geometría con monitores secundarios no sustituyen una comprobación física en Windows con monitores de distinto DPI.

En el entorno macOS/Tk utilizado, ejecutar muchas raíces Tk sucesivas en un mismo proceso produjo una demora indefinida en el procesamiento nativo de geometría. El caso afectado termina al ejecutarlo solo. Para validar la suite de adaptación se ejecutó cada identificador de prueba en un proceso independiente. Si reaparece esa demora, obtener los identificadores con `python -m pytest tests/test_ui_responsive.py --collect-only -q` y ejecutar cada uno con `python -m pytest 'identificador' -q`.

Resultado de esta revisión: 26 pruebas nuevas aprobadas; 34 de adaptación aprobadas en procesos aislados; 15 de diseño, arranque y PDF aprobadas. La suite de interfaz conserva avisos de CustomTkinter sobre el logotipo PhotoImage existente. No se realizó validación física en monitores Windows con DPI distintos.

Para extender una vista, usar el ancho del contenedor, convertir píxeles a unidades lógicas antes de evaluar umbrales y reutilizar los componentes compartidos. Mantener acciones esenciales accesibles, contenido extenso desplazable y datos/selección al cambiar de distribución.
