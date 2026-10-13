# Plan de Implementación: Gestor CFDI Multi-RFC del Despacho (MVP)

## Overview

Construir en Python una herramienta local (Windows) que replique los módulos pagados de Mi Admin XML que usa el despacho: **importación de XMLs sin límite de 50, parser CFDI 4.0 + Complemento de Pago 2.0 (REP), validación de estatus SAT en lote (ConsultaCFDIService público, sin e.firma) y export a Excel** (listado general + conciliación de pagos), con operación multi-RFC organizada por cliente/año/mes.

La Etapa 2 (descarga automática v4 con e.firma + alertas 69-B) queda **fuera del alcance** de este plan; se diseñará solo después de validar el parser contra XMLs reales.

## Architecture Decisions

- **Python 3 + package `conxml`** (src layout), dependencies mínimas: `lxml` (parser XSD-compatible), `openpyxl` (Excel), `zeep` (SOAP ConsultaCFDIService), `requests` (fallback SOAP manual si zeep falla), `pytest` (tests).
- **SQLite (stdlib `sqlite3`, sin ORM)** como repositorio normalizado: una tabla `comprobantes` (datos CFDI + estatus en caché) y una tabla `pagos` (registros del complemento Pago 2.0 con sus `DoctoRelacionado`). SQLite basta para miles de XMLs por cliente y elimina un servidor.
- **El parser es el corazón; todo lo demás es consumidor.** Importador, estatus SAT y exportes de Excel leen del parser/catálogo, nunca de los XMLs directamente.
- **Estatus con caché en catálogo:** el SAT limita la frecuencia de consulta; el catálogo guarda el último estatus y su fecha para no re-consultar lo ya validado salvo que se fuerce.
- **CLI-first** (`conxml import | estatus | export`): el MVP no necesita GUI — la salida real es el Excel. La interfaz gráfica se evalúa después del flujo end-to-end.

## Task List

### Fase 0: Fundación
- [ ] Task 1: Scaffolding del proyecto (pyproject, venv, estructura de paquetes, pytest funcionando)

### Checkpoint: Fundación
- [ ] `python -m pytest` pasa con un test trivial

### Fase 1: Parser (el corazón — riesgo alto, va primero)
- [ ] Task 2: Parser CFDI 4.0 (modelos + parseo + tests con fixtures reales)
- [ ] Task 3: Parser Complemento de Pago 2.0 (REP) (pagos + DoctoRelacionado + tests)

### Checkpoint: Parser (después de Tasks 2-3)
- [ ] Todos los tests pasan
- [ ] Prueba manual: parsea 5+ XMLs reales de tus clientes (facturas y REP) sin error, con datos coherentes
- [ ] Revisión con humano antes de continuar

### Fase 2: Repositorio multi-RFC
- [ ] Task 4: Catálogo SQLite + importador de carpetas (multi-RFC, dedupe por UUID, organización cliente/año/mes)

### Fase 3: Integración SAT
- [ ] Task 5: Cliente estatus SAT (SOAP ConsultaCFDIService, lote con throttling, reintentos, caché)

### Checkpoint: Repositorio + SAT (después de Tasks 4-5)
- [ ] Prueba manual: importa una carpeta real de un cliente y valida estatus de una muestra de 10 folios contra el portal
- [ ] Revisión con humano

### Fase 4: Exportes Excel
- [ ] Task 6: Export listado general de comprobantes (con estatus) a Excel
- [ ] Task 7: Export conciliación de pagos (REP) por cliente a Excel

### Fase 5: Orquestación
- [ ] Task 8: CLI end-to-end (`import` → `estatus` → `export`) + README de uso

### Checkpoint: Flujo completo (después de Tasks 6-8)
- [x] End-to-end sobre una carpeta real: importar → estatus → 2 Excel generados y abiertos sin error
- [x] Comparación del listado vs. Mi Admin XML (misma carpeta, mismos datos)
- [x] Revisión final con humano antes de declarar el MVP

## Post-MVP (verificado 2026-08-12)

### Mejora: paridad de columnas con Mi Admin XML
- [x] Listado de 47 columnas idénticas (mismos encabezados y orden que el export "Facturas")
- [x] Descripciones de catálogo SAT (UsoCFDI, FormaPago, RegimenFiscal, TipoComprobante); Método de Pago en crudo (como Mi Admin)
- [x] EsCancelable / EstatusCancelacion persistidos desde la consulta SAT
- [x] Columnas nuevas: CfdiRelacionados, FechaTimbradoXML, LugarDeExpedicion, RegimenFiscal Receptor, DomicilioFiscalReceptor, regímenes, certificados SAT/Emisor, Conceptos, Complementos, IVA por tasa (Exento/Cero/8/16), retenciones por impuesto y por tasa, Archivo XML
- [x] Migración idempotente de esquema + backfill de metadatos al reimportar (sin tocar caché de estatus)
- [x] Verificación automática vs. export real de Mi Admin XML: 20/20 UUIDs, 0 diferencias, totales idénticos
- [x] Export de conciliación de pagos con el mismo tratamiento: descripciones SAT (forma pago, tipo), EsCancelable/EstatusCancelacion, FechaTimbrado y Archivo XML del REP y de cada factura pagada; verificación automática (scripts/verificar_pagos.py): 21/21 comprobaciones OK contra el XML real del REP (invariantes de monto y saldos) — Mi Admin XML no exporta pagos a Excel (módulo de paga), así que la paridad es contra los datos del XML, no contra un export suyo

## Risks and Mitigations

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| ConsultaCFDIService limita/bloquea consultas frecuentes | Medio | Throttling configurable (delay entre peticiones), reintentos con backoff, caché de estatus en SQLite, consulta solo de pendientes |
| Variantes de CFDI 4.0 / REP en XMLs reales (casos raros, complementos en archivo separado vs. incrustado) | Medio | Validar contra corpus real del despacho desde Task 2; el parser tolera atributos ausentes |
| Zeep/SOAP con el servicio del SAT (issues de TLS/WSDL) | Bajo | Módulo con interfaz propia; fallback a SOAP manual con `requests` + construcción XML a mano |
| Rutas Windows / encoding (acentos, espacios, rutas largas) | Medio | `pathlib` en todo el código, lectura en UTF-8, pruebas con la carpeta real del despacho |
| SQLite sin migraciones formales | Bajo | Esquema v1 definido una sola vez en este plan; cambios de Etapa 2 se evalúan después |

## Open Questions

- **Fuente de los XML de pagos:** ¿los REP de tus clientes son archivos standalone o complemento incrustado dentro de CFDI de ingreso? (El parser soporta ambos — Task 3; confirma el caso real).
- **Carpeta de entrada:** ¿es la misma estructura que lee Mi Admin XML (una carpeta por cliente)? Definir el mapeo carpeta→RFC en la config del Task 4.
- **Volumen semanal de folios a validar** para calibrar el throttling (¿decenas? ¿cientos?).
- Interfaz: CLI confirmado para MVP; preguntar de nuevo después del checkpoint final si hace falta GUI.