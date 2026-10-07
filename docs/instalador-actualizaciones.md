# Instalador y actualizaciones de ConXml

## Entrega al usuario

El archivo único `ConXml-Setup-X.Y.Z-windows-x64.exe` incluye GUI, CLI,
Python, dependencias y recursos (PyInstaller dentro de Inno Setup).
No necesita Python instalado en el equipo destino. Windows 10/11 x64.
Instala por usuario en `%LOCALAPPDATA%\Programs\ConXml`, crea accesos directos
y ofrece **Abrir ConXml** al finalizar. Drive puede transportar ese archivo inicial.
Los avisos siguientes consultan Releases de GitHub, no Drive.

Los datos se guardan en `%LOCALAPPDATA%\ConXml\data`: catálogo, preferencias,
XML y respaldos. Al iniciar se crean muestra, bóveda, descargas SAT y respaldos.
Actualizar o desinstalar no borra este expediente. `CONXML_DATA_DIR` mantiene
prioridad, incluidos directorios externos de XML configurados por el usuario.
Al primer arranque se copia `data` junto al ejecutable si existe y aún no existe
el expediente persistente. El original se conserva; no se mezclan dos catálogos.
Una instalación portable situada en otra carpeta requiere mantener esa carpeta
mediante `CONXML_DATA_DIR`, o restaurar un respaldo desde Ajustes en la nueva
instalación. No borres el original: algunos XML pueden tener rutas absolutas a él.
Cierra las versiones portables antiguas antes del primer arranque y de migrar datos.

## Publicación desde el Administrador

Repositorio público verificado: `Slush-04/ConXml`, rama `main`.
`.github/workflows/windows-release.yml` compila y prueba una versión mediante
`workflow_dispatch`, pero solo deja los resultados como artefacto privado de Actions.
No publica una Release. El Administrador descarga y prueba ese Setup; una acción
separada inicia `.github/workflows/windows-publish.yml` con la versión y el ID del
build que se aprobó. Subir código a `main` tampoco publica una versión.

El workflow de compilación sincroniza `__version__`, pyproject y bundle en su
checkout temporal, ejecuta las pruebas y compila ambos ejecutables, el instalador
y el ZIP de actualización. No hace commits ni crea Releases. La publicación valida
que el run elegido haya sido exitoso en `main`, comprueba ambos SHA-256 y solo
entonces crea y publica `vX.Y.Z`. Una versión publicada nunca se sobrescribe:
genera una versión superior. Mantén los componentes numéricos por debajo de 65536
para el recurso de versión de Windows.

GitHub Actions necesita permiso `contents: write` para publicar Releases y
`actions: read` para descargar el artefacto del build. El Administrador necesita
`Actions: read and write` para iniciar y consultar workflows, y `Contents: read`
para consultar Releases. El token se guarda solo en el almacén seguro del sistema;
ConXml no contiene credenciales y descarga artefactos de Releases públicas.

## Aviso y aplicación

La app consulta al abrir la ventana principal y cada seis horas; **↻** permite
reintentar. Cuando hay una versión numéricamente mayor, estable, publicada,
con instalador x64 del nombre esperado, tamaño válido y digest SHA-256, aparece
**⬇**. El texto al pasar el cursor y el registro indican la versión. No se anuncian
commits ni artefactos incompletos. Sin red conserva la sesión y permite reintentar.

Al pulsar se pide descargar. La descarga va a `ConXml\updates`, fuera de los
respaldos, se escribe temporalmente y se valida tamaño y SHA-256 antes de renombrar.
Los errores borran el temporal. La instalación requiere otra acción del usuario:
guarda sesión, crea respaldo incluso si el respaldo al cerrar está desactivado,
vuelve a comprobar el instalador, abre el asistente interactivo y cierra ConXml.
El mutex compartido con Setup bloquea la sustitución mientras otra GUI está abierta;
Setup no fuerza el cierre. Al terminar puedes abrir la nueva app. Cancelar el
asistente conserva la versión anterior; vuelve a abrirla con su acceso directo.
No hay instalación silenciosa ni actualización automática de esquemas de datos.

La API y todas las redirecciones usan HTTPS y orígenes GitHub permitidos; el
instalador debe pertenecer a la versión y repositorio fijados. SHA-256 verifica
integridad contra el digest recibido por HTTPS, **no es una firma independiente**.
Si la cuenta del repositorio o el workflow se compromete, un atacante podría
publicar instalador y digest. Esta entrega no incluye Authenticode ni una clave
de firma; Windows puede mostrar el editor como desconocido. Una firma de editor
requiere certificado y custodia de secretos en CI, nunca en el código.

## Compilar localmente en Windows

Instala Python 3.13 **x64** e Inno Setup **6.3 o posterior** en el equipo de build.
Esta compilación sirve para pruebas locales; no publica ni actualiza Releases.
En PowerShell desde la raíz, elige una versión local que no confundas con producción:

```powershell
# Para un build manual nuevo (elige una versión superior a la distribuida):
py -3.13 scripts/release_version.py 0.2.100
.\scripts\build_installer.ps1
# Si ISCC está en otra ubicación:
.\scripts\build_installer.ps1 -ISCC 'C:\ruta\ISCC.exe'
```

Salida: `dist\installer\ConXml-Setup-0.2.100-windows-x64.exe` y `.sha256`.
El script crea .venv si falta, instala dependencias, comprueba versiones, ejecuta
pruebas, PyInstaller e Inno Setup. Mac no puede producir este instalador Windows.
Las dependencias tienen rangos en pyproject: CI no es un build byte a byte
reproducible; revisa y fija versiones antes de exigir esa garantía.

## Prueba reproducible en Mac

Usa datos de prueba independientes. Terminal 1:

```bash
.venv/bin/python scripts/demo_updates.py --mode update
```

Terminal 2, desde la raíz:

```bash
CONXML_UPDATE_DEMO_URL=http://127.0.0.1:8765/latest \
CONXML_DATA_DIR=/tmp/conxml-demo PYTHONPATH=src \
.venv/bin/python -m conxml.ui_main
```

Crea un cliente de prueba y entra al programa. Aparece **⬇**; pulsa y acepta
la descarga. Se comprueba el fichero de demostración y aparece su ruta;
**nunca se ejecuta en Mac ni en modo demo**. El fichero no es un ejecutable real.
El binario empaquetado ignora completamente `CONXML_UPDATE_DEMO_URL`.
Detén el servidor y reinícialo con `--mode corrupt`, `truncated`, `offline`,
`current`, `missing`, `draft` o `incompatible`; pulsa ↻ o reinicia la app para
consultar de nuevo. Corrupt/truncated deben rechazar descarga; el resto no anuncia
un instalador nuevo o informa de conexión fallida. Los datos de clientes de prueba
siguen en `/tmp/conxml-demo`. El error de consulta conserva un aviso previamente
obtenido, pero su descarga todavía debe pasar todas las validaciones.

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/release_version.py --check
```

Las pruebas HTTP abren solo loopback (127.0.0.1), sin servicios externos.

## Validación pendiente en Windows

1. Instalar desde cuenta estándar sin Python. Probar GUI, CLI, importación XML,
   exportes Excel/PDF, recursos e iconos; confirmar apertura al finalizar.
2. Crear cliente, XML y preferencias, cerrar con respaldo. Publicar un build nuevo;
   comprobar aviso, descarga, respaldo previo e instalación con otra GUI abierta.
3. Abrir la nueva versión y confirmar catálogo, XML, sesión, preferencias y respaldos.
   Probar también rutas XML externas y una instalación portable antigua.
4. Probar cancelar descarga/asistente, falta de red/espacio y archivo alterado.
   Desinstalar y verificar que el expediente sigue presente; reinstalar y recuperarlo.

Ni la ejecución de Inno Setup ni el binario Windows se han validado en Mac.

Validación local realizada: **160 pruebas pasaron**, con una prueba de integración
SAT excluida por la configuración del proyecto. Incluye servidor HTTP real en
loopback, aviso y descarga en la GUI Mac en un proceso aislado, descarga alterada
o incompleta, ausencia de red, versiones incompletas/incompatibles, conservación
de archivos y migración. El lanzamiento de instalador Windows y el orden de
respaldo/cierre se comprobaron con simulaciones; requieren la validación real de
Windows indicada arriba. Se verificaron sintaxis YAML, compilación de módulos
Python, sincronización de versiones y límite numérico del recurso Windows.

En el runner alojado de Windows se omiten únicamente cinco comprobaciones de
geometría que requieren un escritorio físico mayor que el escritorio virtual del
runner. Las reglas geométricas puras y las demás pruebas siguen ejecutándose en CI;
esas cinco comprobaciones deben correrse en una laptop Windows con pantalla real.

## Archivos de implementación

- `src/conxml/updates.py`: consulta, compatibilidad, descarga, hashes y lanzamiento.
- `src/conxml/ui/actualizaciones.py` y `ui/app.py`: icono, hilo de consulta, confirmaciones,
  respaldo, inicialización y mutex de Windows.
- `src/conxml/config.py`: ubicación persistente, carpetas y copia de datos anteriores.
- `installer/conxml.iss`, `scripts/build_installer.ps1`, `scripts/build_exe.ps1`:
  asistente de instalación y compilación.
- `.github/workflows/windows-release.yml`: build privado para revisión.
- `.github/workflows/windows-publish.yml`: publicación explícita de un build aprobado.
- `scripts/release_version.py`, `src/conxml/__init__.py`, `pyproject.toml`,
  `conxml.spec`: versión consistente para código, paquete y bundle.
- `scripts/demo_updates.py`, `tests/test_updates.py`, `tests/test_config_installer.py`:
  demostración HTTP, interfaz, fallos, integridad y persistencia.
- `tests/test_ui_responsive.py`: expectativa de filtros de Bóveda actualizada a su
  comportamiento existente; verifica que la carpeta externa se lee completa.
- `README.md` y esta guía: entrega, activación, pruebas y límites.
