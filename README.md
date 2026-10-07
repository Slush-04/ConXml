# ConXml 📄💼

> **Gestor CFDI Multi-RFC para Despachos Contables**  
> Parser nativo CFDI 4.0 / REP 2.0 / Nómina 1.2, consulta de estatus ante el SAT, catálogo SQLite y generación de reportes contables en Excel.

---

## 🚀 Descripción

**ConXml** es una solución local en Python diseñada para agilizar y simplificar el flujo contable y fiscal en despachos que administran múltiples clientes (RFCs). Permite procesar lotes masivos de archivos XML sin restricciones de volumen, verificar el estatus en tiempo real ante los servicios del SAT y exportar reportes detallados y conciliaciones de pago en Excel.

Cuenta con una **interfaz gráfica moderna** y personalizable (GUI) y con una **interfaz de línea de comandos** (CLI) para automatizaciones.

---

## ✨ Características Principales

- **Multi-RFC y Catálogo SQLite**: Organización por cliente, deduplicación automática de comprobantes mediante UUID fiscal y almacenamiento local rápido y seguro.
- **Parser CFDI 4.0 Robusto**:
  - Facturas de Ingreso, Egreso y Traslado.
  - Complemento de Nómina (versión 1.2).
  - Complemento para Recepción de Pagos (REP 2.0) con extracción completa de impuestos y documentos relacionados (PPD).
- **Consulta de Estatus SAT**:
  - Conexión al servicio oficial `ConsultaCFDIService` del SAT vía SOAP.
  - Validación de estado (*Vigente*, *Cancelado*), cancelabilidad y fecha de cancelación.
  - Caché inteligente local y pausas configurables (rate limiting) para evitar bloqueos por parte del SAT.
- **Exportación Profesional a Excel (`.xlsx`)**:
  - **Listado General**: Más de 45 columnas contables, impuestos desglosados (IVA, ISR, IEPS retenidos y trasladados), filtros automáticos y formateo monetario.
  - **Conciliación de Pagos**: Cruce de facturas PPD con sus complementos REP, saldos anteriores, importes pagados y saldos insolutos.
- **Interfaz Gráfica (GUI) Moderna**:
  - Construida sobre **CustomTkinter**.
  - Ocultar/mostrar y reordenar columnas con persistencia de preferencias de usuario.
  - Pestañas especializadas para comprobantes y conciliación de pagos.
  - **Adaptable a laptops Mac/Windows**: tamaño inicial según pantalla y
    escalado CTk (sin excederla), sidebar compacto en ventana estrecha,
    totales colapsables y registro ocultable en poca altura, tablas con
    scroll horizontal/vertical y selector REP en ComboBox cuando hay poco ancho.

- **CLI Potente**: Comandos listos para procesar semanas contables o tareas programadas en lotes.

### Interfaz adaptable (laptops)
- Tamaño inicial ajustado a la pantalla y al escalado CTk; el tamaño mínimo
  habitual es 880x600 y se reduce si el espacio disponible es menor.
- `Configure` con debounce (~120 ms) y filtrado (`event.widget is root`);
  no recrea tablas ni pierde selección/datos.
- Ancho < 1100 px: sidebar de 240 → 140 px con etiquetas breves
  (Resumen, XML 4.0, Pagos, Nómina, Ajustes); se recupera al ampliar.
- Alto < 800 px: se oculta el registro y se colapsan los totales
  (botones visibles “Mostrar ▸”); operar no los reabre solos.
- Encabezados con `wraplength` dinámico, márgenes 32/24 → 12/12,
  fila de carpeta apilada y 47 columnas con scroll (sin comprimir ni
  achicar fuentes). Tabla ≥ 150 px en modo compacto.
  Comprobado en macOS con ventanas de 900x650 hasta 1920x1080; la validación
  en un equipo Windows real sigue pendiente.

### Flujo de clientes y Bóveda
- Al iniciar se recupera el último cliente y pantalla de la sesión local. Si no hay
  un cliente guardado, se abre una ventana independiente para seleccionar el cliente activo;
  desde esa ventana se pueden crear y editar la clave, nombre y RFC de cada cliente.
  Ya dentro del programa, **Cambiar cliente** vuelve a abrir esa ventana sin cerrar la aplicación.
- **Bóveda** copia carpetas masivas y organiza los XML en
  `boveda/<cliente>/Recibidos|Emitidos/<año>/<mes>/`. También crea las carpetas
  `Emitidos/Masivo` y `Recibidos/Masivo` para pegar XML descargados del SAT y
  revisarlos desde la pantalla Bóveda. La pantalla también permite examinar
  cualquier carpeta externa y cargar directamente los XML seleccionados a
  Administración de XML.
- La selección de dirección, año y mes se carga al catálogo con un botón; así
  el visor trabaja solo con el periodo elegido.
- Administración XML conserva sus vistas de CFDI, pagos y nómina y añade filtros
  por UUID, RFC, serie y folio.
- La descripción técnica de esta organización está en
  [`docs/arquitectura.md`](docs/arquitectura.md) y
  [`configuraciones/boveda.md`](configuraciones/boveda.md).

---

## 📁 Estructura del Proyecto

```text
ConXml/
├── src/conxml/
│   ├── catalog/         # Almacenamiento SQLite y motor de importación
│   ├── cfdi/            # Modelos y parsers CFDI 4.0, REP y Nómina
│   ├── export/          # Generadores de Excel (listado y conciliación)
│   ├── polizas/         # Módulo de pólizas contables
│   ├── sat/             # Cliente SOAP del SAT y gestión de caché de estatus
│   ├── ui/              # Interfaz gráfica (CustomTkinter, temas, diálogo de columnas)
│   ├── cli.py           # Interfaz de línea de comandos
│   ├── config.py        # Configuración global y rutas del sistema
│   └── semana.py        # Flujo y procesamiento de colas semanales
├── configuraciones/     # Documentación técnica de configuraciones modulares
├── tests/               # Pruebas unitarias con fixtures sintéticas
├── pyproject.toml       # Definición del paquete y dependencias
└── conxml.spec          # Configuración de compilación con PyInstaller
```

---

## 🛠️ Instalación

### Requisitos Previos
- **Python 3.10 o superior**
- `git` instalado en tu sistema

### Paso a Paso

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/Slush-04/ConXml.git
   cd ConXml
   ```

2. **Crear y activar un entorno virtual:**
   - **En macOS / Linux:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
   - **En Windows (PowerShell):**
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```

3. **Instalar el proyecto en modo editable con dependencias de desarrollo:**
   ```bash
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

---

## 🖥️ Uso del Sistema

### 1. Interfaz Gráfica (GUI)

Inicia la aplicación de escritorio:

```bash
conxml-gui
```
*(o también mediante `python -m conxml.ui_main`)*

Desde la interfaz gráfica podrás:
- Seleccionar o crear clientes.
- Cargar carpetas enteras de archivos XML.
- Personalizar qué columnas ver en pantalla y ocultar las que no utilices.
- Consultar el estatus SAT masivo con barra de progreso.
- Generar y abrir directamente los reportes en Excel.
- Abrir una vista previa PDF con doble clic y guardar PDF individuales o lotes ZIP.
- Crear y restaurar respaldos locales desde Ajustes, incluyendo clientes, catálogo,
  XML, preferencias y sesión. Al cerrar se guarda un respaldo automático (últimos 10).
- Continuar con el último cliente, pantalla, filtros y carpetas de trabajo.

La lectura conserva el catálogo por defecto. Consulta
[PDF y respaldos locales](docs/pdf-y-respaldos.md) para las opciones de exportación,
restauración y almacenamiento.

---

### 2. Interfaz de Línea de Comandos (CLI)

El proyecto expone el comando `conxml`:

#### Importar comprobantes
```bash
conxml import /ruta/a/carpeta/con/xmls CLIENTE_1
```

#### Validar estatus ante el SAT
```bash
# Validar los comprobantes pendientes de un cliente
conxml estatus --cliente CLIENTE_1

# Forzar revalidación de todo el catálogo
conxml estatus --cliente CLIENTE_1 --force
```

#### Exportar a Excel
```bash
# Listado general de comprobantes
conxml export listado salida_listado.xlsx --cliente CLIENTE_1 --desde 2026-01-01 --hasta 2026-01-31

# Reporte de conciliación de pagos REP
conxml export pagos salida_pagos.xlsx --cliente CLIENTE_1
```

#### Proceso semanal automatizado
```bash
conxml semana
```

---

## 📦 Compilación de Ejecutables Independientes

Puedes compilar ConXml como aplicación nativa independiente sin necesidad de instalar Python en los equipos de destino:

### 🍎 En macOS (`ConXml.app` y `conxml-cli`)
Ejecuta el script de compilación para Mac:
```bash
./scripts/build_mac.sh
```
El resultado se generará en la carpeta `dist/`:
- **`ConXml.app`**: Aplicación nativa de macOS (se puede mover a `/Applications`).
- **`conxml-cli`**: Binario ejecutable para Terminal.
- *Ubicación de datos*: En macOS, los datos del catálogo se gestionan de forma segura en `~/Library/Application Support/ConXml/`.

### 🪟 En Windows (`conxml.exe` y `conxml-cli.exe`)
Ejecuta el script de PowerShell:
```powershell
.\scripts\build_exe.ps1
```
El resultado se generará en la carpeta `dist\`:
- **`conxml.exe`**: Aplicación gráfica portátil.
- **`conxml-cli.exe`**: Ejecutable de línea de comandos.
- *Ubicación de datos*: En Windows portátil, crea y lee la carpeta `data\` junto al `.exe`.

---

## 🧪 Pruebas Unitarias

Para ejecutar la suite de pruebas unitarias:

```bash
pytest
```

> **Nota:** Las pruebas de integración con el SAT en vivo están marcadas con `@pytest.mark.integration` y están excluidas por defecto para ejecución offline rápida. Para ejecutarlas:
> ```bash
> pytest -m integration
> ```

---

## 🔒 Privacidad y Seguridad

- **100% Local**: Todos los datos se almacenan localmente en tu equipo dentro de una base de datos SQLite.
- Los únicos paquetes de red transmitidos son consultas cifradas HTTPS/SOAP directas a los servidores oficiales del SAT para validar estatus de facturas.
- Ninguna información fiscal, RFC, o XML es enviada a servidores de terceros.

---

## 📄 Licencia

Este proyecto es de uso privado para gestión contable. Consulta la información interna del repositorio para términos y condiciones.

### Instalador Windows y actualizaciones

El proceso de distribución genera un único `ConXml-Setup-X.Y.Z-windows-x64.exe`.
El Administrador solicita a GitHub Actions la compilación de una versión concreta;
el workflow compila en Windows, prueba y publica una Release. Subir cambios al repo
no publica por sí solo una versión. La app muestra **⬇** cuando existe una Release
nueva verificable; la descarga y la instalación requieren acción del usuario. Los
datos persisten en `%LOCALAPPDATA%\ConXml\data`.

Este repo conserva el código fuente y los scripts para crear builds locales de Mac
o Windows. El Administrador y su token viven en el repo separado
`ConXml-UpdateManager`.

Consulta [construcción, publicación y pruebas locales en Mac](docs/instalador-actualizaciones.md)
y el [contrato entre el Administrador y este repo](docs/flujo-administrador.md).
