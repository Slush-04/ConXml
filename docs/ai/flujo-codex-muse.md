# Codex coordina; Muse Spark implementa

La aplicación OpenCode puede invocarse desde Codex mediante su CLI. No hace
falta instalar otro servidor MCP para este flujo local.

## Estado

Se verificó OpenCode 2.0.22 en macOS y una respuesta real de
`opencode/muse-spark-1.3-contributor-free`, enviando solo un mensaje de prueba.
Después se verificó un encargo real de análisis de las rutas de datos. Muse
leyó código en la copia temporal, entregó una propuesta y produjo un parche
vacío, como se solicitó. Codex revisó la propuesta y registró observaciones
en `revision-inicial.md`. El usuario eligió Contributor Free.
La variante estándar todavía requiere configurar el proveedor y verificar acceso.

## Elegir variante

- `free`: Contributor Free. OpenCode indica que las conversaciones pueden
  utilizarse para entrenamiento. Usar únicamente código autorizado y fixtures
  sintéticos; nunca datos reales de clientes.
- `standard`: Muse Spark 1.3 estándar. Requiere acceso de pago configurado
  en OpenCode; los límites y la facturación se gestionan en el proveedor.

No hay modelo elegido por defecto: se debe especificar en cada ejecución.

## Ejecutar un encargo

Desde la carpeta del proyecto, primero preparar sin contactar a la IA:

```bash
python3 scripts/muse_worker.py docs/ai/tarea-inicial.md --model free --dry-run
```

Después de elegir la variante, para enviar la propuesta inicial:

```bash
python3 scripts/muse_worker.py docs/ai/tarea-inicial.md --model free
```

Para la estándar, sustituir `free` por `standard`. En otra computadora instalar
OpenCode y, si no está en PATH, definir CONXML_OPENCODE_BIN con la ruta de su CLI.

El lanzador copia únicamente Python de src/tests, fixtures XML sintéticos,
README y pyproject a una carpeta temporal. Las reglas del agente deniegan
acceso a carpetas externas y requieren aprobación para las herramientas
restantes, incluidos comandos de sistema, red y subagentes. Permiten
editar Python de src/tests y README dentro de la copia. Las reglas de OpenCode
son controles de herramientas, no un aislamiento del sistema operativo.
Se usa el agente nativo `build`: el acceso gratuito rechazó una configuración
que eliminaba herramientas mediante una prohibición general. El lanzador
no activa la aprobación automática.

La respuesta y un parche quedan en `.ai-work/`. No se aplican automáticamente.
No se incluyen data/, bases de datos, XML reales, certificados ni claves.
Revisar también el texto del encargo antes de enviarlo: se transmite completo.

## Ciclo de revisión

1. Codex define el encargo y los criterios de aceptación.
2. Muse prepara una propuesta o implementa sobre la copia.
3. Codex lee la respuesta y el parche, comprueba el alcance y revisa errores.
4. Codex aplica los cambios aceptados y ejecuta las pruebas pertinentes.
5. Si hay errores, Codex redacta otro encargo con correcciones concretas.

Cada invocación es un encargo; no hay un ciclo autónomo que se apruebe solo,
publique o haga push. La revisión de Codex ocurre en este chat. Para comprobar
el proyecto completo hace falta instalarlo en su entorno virtual con el extra
dev y ejecutar pytest. La instalación de Python por sí sola no instala ConXml.

Fuentes: https://opencode.ai/v2/docs/cli/commands/ y
https://opencode.ai/v2/docs/permissions/.
