# Task List: Gestor CFDI Multi-RFC del Despacho (MVP)

## Task 1: Scaffolding del proyecto

**Description:** Crear el proyecto Python con estructura src layout, dependencias mínimas, entorno virtual y pytest configurado con un test trivial que pruebe el pipeline CI-local.

**Acceptance criteria:**
- [ ] `pyproject.toml` define el paquete `conxml` con deps: lxml, openpyxl, zeep, requests; dev-deps: pytest
- [ ] `python -m pytest` corre y pasa 1 test trivial
- [ ] Estructura: `src/conxml/{cfdi,catalog,sat,export}` y `tests/fixtures/`

**Verification:**
- [ ] Tests pass: `python -m pytest`
- [ ] Build succeeds: `pip install -e .`
- [ ] Manual check: `python -c "import conxml"` sin error

**Dependencies:** None

**Files likely touched:**
- `pyproject.toml`
- `src/conxml/__init__.py`
- `tests/test_smoke.py`
- `.gitignore`

**Estimated scope:** Small (1-2 files)

---

## Task 2: Parser CFDI 4.0

**Description:** Modelos y parser de comprobantes CFDI 4.0 con lxml: UUID, serie/folio, fecha, RFC/razón social emisor y receptor, uso de CFDI, método/forma de pago, moneda, tipo de cambio, subtotal/descuento/IVA/total, tipo de relación y datos del timbre (folio fiscal, fecha timbrado, RFC PAC). Parseo tolerante a atributos ausentes.

**Acceptance criteria:**
- [ ] `Comprobante.from_xml(path)` devuelve un dataclass tipado con todos los campos listados
- [ ] Se detecta la versión del CFDI y se rechaza/registra XMLs no-4.0 con error claro (no crash)
- [ ] 5 fixtures XML CFDI 4.0 (factura ingreso con IVA, sin IVA, con descuento, con traslados múltiples, con retenciones) se parsean correctamente en tests

**Verification:**
- [ ] Tests pass: `python -m pytest tests/test_parser.py`
- [ ] Manual check: parsear 5+ XMLs reales de clientes (facturas) sin error y comparar total/UUID contra el portal

**Dependencies:** Task 1

**Files likely touched:**
- `src/conxml/cfdi/models.py`
- `src/conxml/cfdi/parser.py`
- `tests/test_parser.py`
- `tests/fixtures/*.xml`

**Estimated scope:** Medium (3-5 files)

---

## Task 3: Parser Complemento de Pago 2.0 (REP)

**Description:** Parseo del Complemento de Pago (Pago20): por pago → fecha, forma de pago, método (PPD/PUE), monto, moneda/tipo de cambio, numOperacion, RFC cuenta ordenante/beneficiario; y sus `DoctoRelacionado` → UUID, método, parcialidad, impSaldoAnt, impPago, impSaldoInsoluto. Soporta REP como **archivo standalone** y como **complemento incrustado** en un CFDI.

**Acceptance criteria:**
- [ ] `parse_pagos(comprobante)` extrae pagos y documentos relacionados tipados
- [ ] Los dos formatos (standalone e incrustado) se parsean correctamente
- [ ] La relación UUID-de-factura ↔ pago queda verificable (campo `uuid_relacionado`)

**Verification:**
- [ ] Tests pass: `python -m pytest tests/test_pagos.py`
- [ ] Manual check: 3+ REPs reales del despacho parseados con montos y saldos coherentes vs. los XMLs

**Dependencies:** Task 2

**Files likely touched:**
- `src/conxml/cfdi/pagos.py`
- `tests/test_pagos.py`
- `tests/fixtures/pago*.xml`

**Estimated scope:** Medium (3-5 files)

---

## Task 4: Catálogo SQLite + importador multi-RFC

**Description:** Repositorio normalizado en SQLite (tablas `comprobantes` y `pagos`) con esquema v1. Importador que recorre una carpeta raíz (una subcarpeta por cliente/RFC según config), parsea cada XML, deduplica por UUID (el segundo archivo igual no duplica fila; se registra ruta extra), y organiza por cliente/año/mes.

**Acceptance criteria:**
- [ ] Importar una carpeta de 50+ XMLs (varios clientes) crea el catálogo sin duplicados de UUID
- [ ] Se importa el mismo XML dos veces → no se duplica (identidad por UUID + emisor/receptor/total)
- [ ] SQL consultable: por cliente, por mes, por estatus; pagos ligados a su comprobante
- [ ] XML inválido/no-CFDI se registra en tabla `errores` y no detiene la importación

**Verification:**
- [ ] Tests pass: `python -m pytest tests/test_catalog.py`
- [ ] Manual check: importar la carpeta real de 1 cliente; contar filas vs. archivos

**Dependencies:** Tasks 2, 3

**Files likely touched:**
- `src/conxml/catalog/db.py`
- `src/conxml/catalog/importer.py`
- `src/conxml/config.py`
- `tests/test_catalog.py`

**Estimated scope:** Medium (3-5 files)

---

## Task 5: Cliente estatus SAT (ConsultaCFDIService)

**Description:** Cliente SOAP del servicio público de estatus del SAT (sin e.firma): consulta por UUID, RFC emisor, RFC receptor y total → `Vigente` / `Cancelado` / `No Encontrado` (además del código de estado SAT). Modo lote con throttling configurable (delay entre peticiones), reintentos con backoff, y persistencia del resultado en el catálogo (caché — no re-consulta lo ya validado salvo `--force`).

**Acceptance criteria:**
- [ ] `consultar_estatus(uuid, rfc_emisor, rfc_receptor, total)` devuelve el estatus mapeado readable
- [ ] Lote sobre registros del catálogo sin estatus: respeta delay configurado, reintenta fallos transitorios, escribe caché
- [ ] Los tests corren con mock del servicio (sin red); existe test de integración marcado `@pytest.mark.integration`

**Verification:**
- [ ] Tests pass: `python -m pytest tests/test_estatus.py`
- [ ] Manual check (integración): consultar 10 folios reales del catálogo y comparar 3 contra el portal/QR del SAT

**Dependencies:** Tasks 2, 4

**Files likely touched:**
- `src/conxml/sat/estatus.py`
- `src/conxml/sat/soap.py` (cliente SOAP + fallback)
- `tests/test_estatus.py`

**Estimated scope:** Medium (3-5 files)

---

## Task 6: Export listado general a Excel

**Description:** Generador de Excel (openpyxl) con el listado general de comprobantes del catálogo: cliente, RFC, UUID, serie/folio, fecha, tipo (ingreso/egreso/traslado), emisor, receptor, uso CFDI, método, moneda, subtotal, IVA, total, estatus SAT (fecha de consulta). Filtros por cliente/periodo; encabezados con estilo mínimo; celda de estatus coloreada (verde vigente, rojo cancelado).

**Acceptance criteria:**
- [ ] Genera `.xlsx` con todas las columnas listadas y una fila por comprobante
- [ ] Filtro por cliente y por periodo funciona
- [ ] Test lee el archivo generado con openpyxl y verifica valores y coloreado de estatus

**Verification:**
- [ ] Tests pass: `python -m pytest tests/test_excel.py`
- [ ] Manual check: abrir el Excel generado en Excel 2016+ sin errores de formato

**Dependencies:** Tasks 2, 4, 5 (para estatus), 6 tiene el catálogo mínimo con Task 4

**Files likely touched:**
- `src/conxml/export/listado.py`
- `tests/test_excel.py`

**Estimated scope:** Medium (3-5 files)

---

## Task 7: Export conciliación de pagos a Excel

**Description:** Generador de Excel de conciliación de pagos por cliente: una hoja por cliente con cada pago (fecha, forma, monto, moneda, núm. operación) y sus documentos relacionados (UUID, método, parcialidad, saldo anterior, importe pagado, saldo insoluto), más columnas de estatus SAT de cada factura relacionada. Camino de **conciliación**: permite detectar facturas no liquidadas (saldo insoluto ≠ 0).

**Acceptance criteria:**
- [ ] Excel por cliente con pagos y sus DoctoRelacionado anidados (columnas repetidas por documento relacionado o formato tabla plana con UUID relacionado)
- [ ] Columna estatus de la factura relacionada (desde caché del catálogo)
- [ ] Resumen: total pagado por cliente/periodo; facturas con saldo insoluto pendiente destacadas

**Verification:**
- [ ] Tests pass: `python -m pytest tests/test_excel_pagos.py`
- [ ] Manual check: conciliación de un cliente real vs. su estado de cuenta de pagos

**Dependencies:** Tasks 3, 4, 5, 6 (reutiliza el writer base)

**Files likely touched:**
- `src/conxml/export/pagos.py`
- `tests/test_excel_pagos.py`

**Estimated scope:** Medium (3-5 files)

---

## Task 8: CLI end-to-end + README

**Description:** Interfaz CLI (`conxml import <carpeta>`, `conxml estatus [--force]`, `conxml export listado|pagos [--cliente] [--periodo]`) que orquesta importador → estatus → exportes, con checks previos (carpeta existe, catálogo abierto, resumen de resultados) y salida legible. README con instalación (venv Windows), configuración (mapeo cliente→carpeta, delays) y el flujo semanal recomendado.

**Acceptance criteria:**
- [ ] Las 3 órdenes funcionan end-to-end sobre el catálogo real y devuelven resumen claro (n, errores, duración)
- [ ] `--help` documenta cada orden y sus flags
- [ ] README permite a otra persona del despacho ejecutar el flujo semanal sin ayuda

**Verification:**
- [ ] Tests pass: `python -m pytest`
- [ ] Build succeeds: `pip install -e .`
- [ ] Manual check: flujo completo `import → estatus → export` sobre carpeta real de un cliente, Excel abierto sin error

**Dependencies:** Tasks 4, 5, 6, 7

**Files likely touched:**
- `src/conxml/cli.py`
- `pyproject.toml` (entry point `conxml`)
- `README.md`
- `tests/test_cli.py`

**Estimated scope:** Medium (3-5 files)

---

## Checkpoints

### Checkpoint 1: Fundación (después de Task 1)
- [ ] `python -m pytest` pasa
- [ ] `pip install -e .` y `import conxml` funcionan

### Checkpoint 2: Parser (después de Tasks 2-3)
- [ ] Todos los tests pasan
- [ ] 5+ XMLs reales (facturas + REP) parseados sin error
- [ ] Revisión con humano

### Checkpoint 3: Repositorio + SAT (después de Tasks 4-5)
- [ ] Carpeta real importada sin duplicados
- [ ] Estatus de muestra (10 folios) coincidente con el portal
- [ ] Revisión con humano

### Checkpoint 4: MVP completo (después de Tasks 6-8)
- [ ] Flujo `import → estatus → export` completo y revisado en pantalla con humano
- [ ] Listado coincide con Mi Admin XML sobre la misma carpeta
- [ ] Decisión con el humano: escalar Etapa 2 (descarga v4 + alertas) o pulir el MVP