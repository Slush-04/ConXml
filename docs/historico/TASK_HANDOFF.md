# Handoff: Gestor CFDI Multi-RFC del Despacho (`ConXml`)

> Documento para retomar el trabajo en otra sesión. Fecha: 2026-08-12.

## Qué estamos construyendo
Herramienta local en Python (Windows) que replicará los módulos de pago de **Mi Admin XML** de un despacho contable: importar XMLs **sin límite de 50**, validar **estatus SAT**, reportes **Excel** (listado + conciliación de pagos REP) multi-RFC, sin suscripción. La descarga automática 24/7 es Etapa 2 (fuera del MVP).

## Dónde estamos
**MVP completo implementado** — las 8 tareas del plan terminadas, 39 tests pasando, validado con datos reales de julio 2026 del cliente real.

## Checklist del plan (estado)

| # | Tarea | Estado | Resultado real |
|---|---|---|---|
| 1 | Scaffolding (pyproject, venv, pytest) | ✅ | Python 3.12 + venv `.venv` |
| 2 | Parser CFDI 4.0 | ✅ | 70/70 XMLs parseados, 0 errores |
| 3 | Parser REP (complemento pago 2.0) | ✅ | REP real detectado (1 pago/docto) |
| — | **Checkpoint parser** | ✅ PASADO | 70/70 reales (65I, 4N, 1P) |
| 4 | Catálogo SQLite + importador multi-RFC | ✅ | 70 comprobantes, dedupe UUID, 0 errores |
| 5 | Estatus SAT (ConsultaCFDIService) | ✅ | 21+49 folios reales validados, caché OK |
| — | **Checkpoint repo+SAT** | ✅ PASADO | Validación en vivo vs SAT |
| 6 | Export listado a Excel | ✅ | 2 archivos reales (49+21 filas), colores, filtros |
| 7 | Export conciliación pagos | ✅ | 1 REP real liquidado (900 MXN), formato plano + Resumen |
| 8 | CLI + README | ✅ | `conxml import\|estatus\|export` |
| — | **Checkpoint MVP final** | 🔵 **PENDIENTE** | Comparar vs Mi Admin XML + decidir Etapa 2 |

## Estructura del proyecto
```
ConXml/
├── pyproject.toml            # deps: lxml, openpyxl, requests; pytest
├── README.md                 # instalación + flujo semanal
├── src/conxml/
│   ├── cfdi/                 # modelos.py, parser.py, pagos.py
│   ├── catalog/              # db.py (SQLite), importer.py
│   ├── sat/                  # soap.py, estatus.py (lote/caché)
│   ├── export/               # listado.py, pagos.py (Excel)
│   ├── config.py
│   └── cli.py
├── tests/                    # 39 tests (con fixtures XML)
├── docs/ideas/gestor-cfdi-multi-rfc.md
├── tasks/plan.md, tasks/todo.md
└── data/
    ├── muestra/07. JULIO/{1,2}/   # XMLs reales julio 2026
    ├── catalogo.db                # 70 comprobantes, 1 REP
    └── salidas/                   # Excel generados
```

## Datos de prueba
- RFC de prueba: **AAA010101AAA** (Despacho de ejemplo)
- Cliente 1: 49 XMLs | Cliente 2: 21 XMLs | Totales: 65 ingreso, 4 nómina, 1 REP
- El REP (900 MXN) pertenece al **cliente 2**; su factura relacionada no está en el catálogo (estatus "sin dato")

## Cómo usar (comandos)
```powershell
.\.venv\Scripts\python -m conxml.cli import <carpeta> <cliente>
.\.venv\Scripts\python -m conxml.cli estatus --cliente 1
.\.venv\Scripts\python -m conxml.cli export listado <destino.xlsx> --cliente 1 --desde 2026-07-01 --hasta 2026-07-31
.\.venv\Scripts\python -m conxml.cli export pagos <destino.xlsx> --cliente 1
```
> Entry point `conxml.exe` verificado funcionando en `.venv\Scripts\` (se regeneró tras instalar con `cli.py` presente).

## Pendientes / siguientes pasos
1. **Checkpoint final con humano (pendiente):** abrir los Excel que ya se compararon contra Mi Admin XML. El listado fue verificado automáticamente (20/20, 0 diffs) y la conciliación de pagos quedó verificada contra el XML real del REP (21/21, ficha en `data/salidas/VERIFICACION_PAGOS_*.txt`, Excel en `data/salidas/conciliacion_pagos_cliente2_julio2026.xlsx`). Falta la mirada humana.
2. **Decisión de Etapa 2:** descarga automática v4 con e.firma + alertas de riesgo (fuera del MVP).
3. Posibles mejoras:
   - Conectar la cola semanal a la **GUI** (el módulo `conxml/semana.py` ya está conectado al **CLI**: `conxml semana detect <raiz>` y `conxml semana run` — implementado y con 8 tests nuevos, suite total 59 pasando).
   - Generar `conxml.exe` (el entry point no creó el ejecutable). → HECHO: el .exe existe y funciona; se regenera con `pip install -e .` cuando hay código nuevo.
   - Visualizar los 4 XMLs tipo N (el parser de nómina lee percepciones/deducciones; integrarlo al export si se requiere).

## Notas de entorno
- No es repo git (no inicializado).
- El lote de estatus consulta el SAT en vivo (~2s/folio); solo folios pendientes por defecto, `--force` revalida todo.
- Los tests de integración SAT se corren con: `python -m pytest -m integration` (requieren red y `data/catalogo.db`).
