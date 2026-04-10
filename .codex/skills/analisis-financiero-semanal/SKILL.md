---
name: analisis-financiero-semanal
description: Analizar informacion financiera semanal combinando un Excel de indicadores con una base accesible via MCP. Use when Codex receives `Datos_Financieros_Semanales` or another weekly KPI workbook plus an available database MCP with tables such as `transactions`, `customers`, and `products`, and must validar cifras, cruzar KPIs con la base, calcular metricas derivadas y entregar insights sobre margen por producto, ingresos por cliente, clientes recurrentes, productos mas rentables, crecimiento semanal y comportamiento por segmento. Always use MCP for database access; if the MCP is unavailable or the session does not expose a usable query surface, stop quickly, report the limitation, and do not attempt shell-based or network fallbacks.
---

# Analisis Financiero Semanal

## Usar

- Activar este skill cuando el usuario entregue un Excel o CSV semanal y pida contrastarlo con la base de datos para obtener analisis de negocio.
- Tratar el Excel como resumen operativo de la semana y la base de datos como fuente de detalle para validar, explicar o ampliar los KPIs.
- Verificar el MCP al inicio con una sola comprobacion rapida.
- Usar solo herramientas MCP para descubrir esquema y consultar la base.
- Si la sesion no expone un MCP utilizable para la base, detener el cruce, explicarlo en 1 o 2 lineas y pedir confirmacion antes de entrar en depuracion.
- No leer `config.toml`, no instalar clientes, no usar `npx`, `npm`, `mysql`, ODBC ni scripts ad hoc para suplir el MCP salvo que el usuario pida depurar la integracion del skill.
- Leer `./references/sql-playbook.md` para descubrir el esquema y adaptar consultas a MySQL.
- Leer `./references/metricas-y-definiciones.md` para alinear formulas, definiciones y reglas de reconciliacion.
- Leer `./references/output-esperado.md` para estructurar el entregable final.
- Si la solicitud incluye actualizar primero el archivo semanal, usar el skill `actualizar-indicadores` antes de ejecutar el analisis.

## Resolver Archivo y Periodo

- Priorizar en este orden:
  - archivo entregado en la conversacion
  - ruta explicita del usuario
  - nombre exacto en `cwd`
  - asset por defecto del skill, si aplica
- Evitar exploraciones recursivas amplias para adivinar copias del workbook.
- Inspeccionar primero encabezados y solo las filas necesarias para identificar el periodo objetivo.
- No afirmar que falta `2026-W12` hasta verificar la convencion de periodo del archivo:
  - semana ISO como `2026-W12`
  - `YEARWEEK` como `202612` o `2026-12`
  - semana fiscal u ordinal
  - periodo mensual como `2026-03`
- Si el Excel usa otra convencion, documentar el mapeo entre el periodo pedido y la etiqueta real del archivo.
- Convertir siempre la semana ISO a fechas exactas antes del cruce y citarlas en la respuesta.

## Esperar Entrada

- Aceptar `xlsx`, `xlsm` o `csv` como archivo semanal.
- Esperar por defecto columnas compatibles con `week` o `semana`, `revenue` o `ingresos`, `losses` o `perdidas`, y `customers` o `clientes`.
- Esperar una base con al menos tres tablas funcionales o equivalentes:
  - `transactions`
  - `customers`
  - `products`
- Aceptar nombres distintos de tablas o columnas siempre que el MCP permita descubrir el esquema y mapear llaves de union.
- Pedir al usuario aclaracion solo si no existe forma segura de identificar periodo, fecha de transaccion o columnas de ingresos/costo.

## Flujo Principal

- Abrir el archivo semanal y detectar el periodo objetivo.
- Identificar si el analisis es de una semana puntual, de comparacion entre semanas o de tendencia.
- Ejecutar una unica fase de descubrimiento MCP para ubicar:
  - tabla de hechos transaccionales
  - llave hacia cliente
  - llave hacia producto
  - fecha de transaccion
  - monto de ingreso
  - costo, perdida o proxy de rentabilidad si existe
  - segmento de cliente o categoria de producto si existe
- Si el MCP no devuelve esquema consultable o datos utilizables, detener el analisis y reportar el bloqueo en vez de seguir explorando por otros canales.
- Recalcular desde la base los KPIs del mismo periodo del Excel.
- Comparar Excel contra base y reportar diferencias absolutas y relativas.
- Calcular metricas derivadas y cortes analiticos.
- Redactar insights claros, accionables y trazables a los datos.

## Descubrir y Cruzar Datos

- Confirmar primero el calendario del analisis:
  - semana ISO
  - fecha inicial y final
  - zona horaria aplicable
- Inspeccionar `information_schema.columns` o tablas equivalentes una sola vez por sesion para evitar asumir nombres de columnas.
- Priorizar estas relaciones logicas:
  - `transactions.customer_id -> customers.id`
  - `transactions.product_id -> products.id`
- Si los nombres reales cambian, documentar el mapeo usado en la respuesta.
- Excluir o separar transacciones canceladas, fallidas y reembolsadas si el modelo las registra.
- Usar ingresos netos cuando existan; si solo hay bruto, indicarlo explicitamente.
- No afirmar margen real por producto si no hay costo, COGS o perdida asignable por producto.
- Preferir consultas agregadas compactas y evitar repetir discovery o recorrer tablas completas sin necesidad.

## Entregar Analisis

- Incluir siempre un resumen ejecutivo corto.
- Mostrar una tabla de reconciliacion entre Excel y base para los KPIs principales.
- Cubrir como minimo estos frentes:
  - margen por producto
  - ingresos por cliente
  - clientes recurrentes
  - productos mas rentables
  - crecimiento semanal
  - comportamiento por segmento
- Senalar alertas de calidad de datos, diferencias de definicion o vacios del esquema.
- Cerrar con recomendaciones puntuales o siguientes preguntas para profundizar.

## Reglas

- No asumir que `losses` del Excel equivale a costo de producto si la base no lo soporta.
- No mezclar fechas de pago, pedido y facturacion sin decir cual se uso.
- No calcular recurrencia con una sola semana si existe historial disponible; usar una ventana historica suficiente.
- No ocultar discrepancias entre Excel y base; cuantificarlas.
- Explicar toda inferencia importante, especialmente cuando falten columnas de costo, segmento o estado.
- No sustituir un MCP ausente con conexiones manuales ni instalaciones temporales.
- No convertir una solicitud de analisis en una tarea de depuracion de infraestructura salvo que el usuario lo pida.

## Prompts Esperados

- `Analiza el archivo Datos_Financieros_Semanales.xlsx y cruza la semana 2026-W12 con mi base para explicar margen, recurrencia y crecimiento.`
- `Usa el Excel semanal y la base de datos para validar ingresos, clientes y productos rentables de esta semana.`
- `Cruza los KPIs del archivo semanal con transactions, customers y products y dame insights ejecutivos.`
- `Compara la semana actual contra la anterior usando el Excel y la base, y resume alertas de negocio por segmento.`
