# Primera ejecución real y revisión de Codex

Modelo: Muse Spark 1.3 Contributor Free, mediante OpenCode 2.0.22.

## Resultado comprobado

Muse recibió el encargo de proponer rutas estables sin implementar. Leyó
código en una copia temporal y entregó un análisis. El parche fue de cero
bytes: no cambió archivos. No ejecutó pruebas de ConXml.

## Revisión

El diagnóstico central es correcto: `Config.base` devuelve `Path("data")`
en ejecución desde Python, y depende del directorio de inicio.

La propuesta necesita estas correcciones antes de implementarse:

1. Mantener inicialmente el comportamiento actual de los ejecutables
   empaquetados, incluido Windows portátil. Mover también esos datos a
   APPDATA amplía el alcance y requiere diseñar una migración por separado.
2. No seleccionar automáticamente una base antigua según el directorio de
   inicio: conserva la dependencia que intentamos eliminar. Detectar las
   bases existentes, mostrar el conflicto y permitir una elección explícita.
3. Si existen una base antigua y otra en la nueva ubicación, no elegir una
   silenciosamente. Informar ambas y conservarlas sin sobrescribirlas.
4. Las rutas relativas indicadas explícitamente por CONXML_DATA_DIR pueden
   seguir dependiendo del directorio de inicio; distinguirlas del default
   estable y documentarlas.
5. `--db` solo selecciona una base; no migra bases ni XML. No describirlo
   como una migración y recordar que nómina depende de los XML originales.

## Estado

El flujo Codex → OpenCode/Muse → revisión de Codex ya fue comprobado.
La propuesta de rutas no está aprobada para implementarse todavía. Los
archivos de la aplicación permanecen sin modificaciones por parte de Muse.
La instalación de dependencias y las pruebas completas siguen pendientes.
