# Cola de Trabajo Semanal (batch por cliente)

## Problema

¿Cómo acortamos el tiempo humano del ciclo semanal por cliente
(importar → validar SAT → exportar) en ConXml, cuando el SAT ya es
el cuello de botella y no se puede acelerar?

Contexto validado: semana típica del despacho = descargar XMLs a
carpeta → importar → validar estatus SAT → exportar listado + pagos,
por cliente. Estructura de carpetas real: `RFC/Emitidas o Recibidas/
Año/Mes/`. El SAT es el límite (~2 s/folio); la UX solo puede reducir
el tiempo humano (esperas, confusiones, repeticiones), no el total.

## Dirección recomendada

Una pantalla "Trabajo semanal": el auxiliar marca clientes y la app
procesa en cadena — importar su carpeta (RFC/Emitidas|Recibidas/Año/Mes),
validar pendientes con el throttling actual y exportar listado + pagos
a `data/salidas/`. Cada cliente termina con ficha de anomalías
(cancelados nuevos, no encontrados, sin validar restantes). Los errores
se aíslan por cliente: uno no detiene la cola. Botón "detener después
del cliente actual" sin pérdida de datos (caché de estatus: lo pendiente
se reintenta solo en la siguiente corrida).

Componentes absorbidos de la fase divergente: el orden sugerido se
vuelve el orden de la lista (clientes con más pendientes primero), la
revisión exprés es la ficha final por cliente, y la mensajería SAT
experta es el lenguaje de los resultados (por qué pasó y qué sigue).

## Asunciones por validar

- [ ] Las carpetas siguen el patrón RFC/Dirección/Año/Mes semana a semana — probar con las carpetas reales antes de implementar la auto-detección
- [ ] El auxiliar deja correr el lote sin mirar (confianza en el batch) — 2 semanas de uso real
- [ ] El SAT tolera la cadena con pausa entre clientes — monitorear fallos la primera semana (riesgo conocido de plan.md:71)
- [ ] Ahorro real ≥ 10-15 min por cliente — medir antes/después con el horario de la corrida

## MVP

- Pantalla de cola: clientes con estado por etapa y progreso por folio
- Config de carpetas por cliente (auto-detecta Año/Mes recientes)
- Cadena importar → validar → exportar por cliente, con pausa entre clientes
- Ficha final por cliente (anomalías + rutas de los Excel) + botón detener (seguro)
- Mensajes SAT en lenguaje llano en cada resultado

## No haremos (y por qué)

- **Descarga automática de XML** — Etapa 2 con e.firma, scope aparte; la cola empieza donde ya hay carpetas
- **2+ clientes a la vez (paralelo)** — el SAT lo ve como agresión; prohibido
- **Alertas 69-B / créditos fiscales** — solo señalar cancelados nuevos en la ficha
- **Cambios en el modelo de datos** — la BD no se toca; solo se agrega config de carpetas
- **Web/API para clientes** — ya descartado en docs/ideas/gestor-cfdi-multi-rfc.md

## Preguntas abiertas

- Emitidas y Recibidas: ¿juntas bajo la misma etiqueta de cliente o como etiquetas separadas?
- Lista de clientes: ¿auto-detectar RFCs de la carpeta raíz o config manual?
- ¿Pausa sugerida entre clientes (p. ej. 60 s) y configurable?
- ¿El periodo por defecto es el mes en curso, con opción "mes anterior"?