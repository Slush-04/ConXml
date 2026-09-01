# Gestor CFDI Multi-RFC del Despacho

## Problem Statement

> **Cómo podríamos** dar a nuestro despacho las herramientas avanzadas multi-RFC que hoy pagamos (gestión de clientes, parser CFDI 4.0, reportes Excel) sin suscripción, con base sólida y oficial, y de paso automatizar descargas y alertas de riesgo fiscal.

**Flujo real validado (semana típica del despacho):** descargar XMLs a carpeta → leerlos → validar estatus SAT → exportar lista a Excel → mismo proceso para control/conciliación de pagos (REP).

**Limitaciones concretas que hoy padece la suscripción:**
1. Plan normal de Mi Admin XML: solo lee **50 XMLs**; manejar más requiere pagar.
2. Control y conciliación de pagos: **no exporta a Excel** — es función de paga.

## Recommended Direction

**Una sola base: repositorio normalizado de CFDI + dos consumidores.** El corazón es un motor de procesamiento construido sobre los esquemas XSD oficiales del SAT (publicados, sin scraping ni hacks): ingesta de XML → parseo completo (CFDI 4.0, Complemento de Pago 2.0, Nómina) → almacenamiento normalizado multi-RFC. Del mismo repositorio salen (a) la réplica del módulo pagado: operación multi-RFC y reportes Excel, y (b) el plus: descarga automática por webservice oficial (e.firma, v4) y alertas pasivas (estatus/cancelación, cruce 69-B).

Elegirlo así tiene una razón arquitectónica: **todo el valor vive en el parser, y todo lo demás es un consumidor.** Si el parser es sólido, cada módulo posterior (reportes, alertas, API, portal) es barato. Y se responde a tu criterio de calidad total sin scatter — el trabajo que es caro y frágil (scraping CIEC) se elimina de raíz usando los webservices oficiales.

**Matiz que baja la barrera del MVP:** la validación de estatus puede hacerse con el **ConsultaCFDIService público del SAT** (folio/RFC/total, sin autenticación). La e.firma solo entra en la Etapa 2 (descarga masiva v4). El MVP de paridad no depende de webservices autenticados.

## Key Assumptions to Validate

- [x] **Los módulos realmente usados están identificados (VALIDADA):** lectura de XMLs en carpeta, validación de estatus SAT, export de listado a Excel, conciliación de pagos (REP) — contra las limitaciones: límite de 50 XMLs y export de pagos de paga.
- [ ] **El webservice v4 del SAT (e.firma) cubre todas las descargas que necesitas y es estable** — prueba de concepto de 2 semanas: autenticación con e.firma de un cliente real y una descarga masiva de prueba, ANTES de diseñar la Etapa 2.
- [ ] **El parseo 4.0/REP/Nómina cubre ≥90% de los XMLs reales de tus clientes sin casos raros** — valida con los XMLs que ya tienes descargados manualmente: parsa 50 XMLs reales de cada tipo y mide coherencia. (Los casos raros existen y no deben bloquear v1.)
- [ ] **Tu despacho gana con esto en vez de seguir pagando** — calcula el costo anual de la suscripción vs. tu tiempo de desarrollo. Si la suscripción cuesta menos de lo que valen tus 300 horas, acepta que esto es un proyecto de independencia/aprendizaje (legítimo), no de ahorro.

## MVP Scope

- Carga de XMLs desde carpeta existente, **sin límite de 50**.
- Parser CFDI 4.0 + Complemento de Pago 2.0 (REP) sobre esquemas oficiales.
- Validación de estatus SAT en lote vía **ConsultaCFDIService público** (sin e.firma).
- Export a Excel: listado general de comprobantes (con estatus) + export de la **conciliación de pagos** por cliente.
- Operación multi-RFC: organización automática por cliente/año/mes.
- Solo Windows/localhost, interfaz simple.
- **Etapa 2 (plus, no bloquea el MVP):** descarga automática por webservice v4 con e.firma + alertas de riesgo.

## Not Doing (y por qué)

- **Scraping CIEC del portal SAT** — frágil, zona gris de términos de uso, se rompe con cada cambio del portal. El webservice oficial existe; úsalo.
- **Emisión/timbrado de facturas** — Mi Admin XML gratuito ya cubre el lado receptor; tu ventaja es gestión multi-RFC, no timbrar.
- **Portal web para tus clientes** — scope creep para una herramienta interna; reconsiderar el día que el robot y la paridad ya estén funcionando.
- **API REST + webhooks** — el diferencial del documento original, pero sin consumidores externos todavía no genera valor en el despacho. El repositorio normalizado ya deja la puerta abierta.
- **Paridad feature-a-feature con todos los complementos** (IEPS, carta porte, hidrocarburos, etc.) — solo parsa lo que tus clientes realmente emiten: valida con el inventario de XMLs reales.

## Open Questions

- ¿SQLite vs. base de datos servidor para el almacenamiento normalizado? (Según volumen: si son miles de XMLs por cliente, SQLite basta; decide al validar la asunción del parseo).
- ¿Manijas e.firmas de varios clientes en un solo lugar? ¿Qué tan cómodo estás con la responsabilidad de custodiar esas firmas en una herramienta propia vs. la suscripción actual? (La e.firma es un secreto con consecuencias legales.)
- ¿El listado 69-B se integra vía DOF manual o desde una fuente automatizada del SAT? (Existe publicación oficial; la automatización es un proyecto aparte.)
