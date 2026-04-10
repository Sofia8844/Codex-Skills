---
name: actualizar-indicadores
description: Update a named base CSV or Excel financial indicators file with weekly data. Use when Codex receives an existing spreadsheet path or uploaded file plus weekly values in natural language, and must update that same file by replacing the row for the requested week or appending it if the week does not exist, then recalculate retention_rate, loss_percentage, and margin. If the user does not specify a file, use `assets/Datos_Financieros_Semanales.xlsx` as the base and keep the working file inside `actualizar-indicadores/output/`. Trigger on requests such as "actualiza el archivo indicadores.xlsx con estos datos", "actualiza indicadores de esta semana" or "carga datos semanales y recalcula metricas".
---

# Actualizar Indicadores

## Usar

- Activar este skill cuando el usuario entregue un archivo base de indicadores y pida actualizar una semana o recalcular metricas financieras.
- Tomar como modo principal: archivo existente + datos nuevos en lenguaje natural.
- Si el usuario nombra un archivo especifico, actualizar ese mismo archivo por defecto.
- Si el usuario no nombra un archivo, usar `./assets/Datos_Financieros_Semanales.xlsx` como semilla y trabajar sobre `./output/Datos_Financieros_Semanales.xlsx`.
- Preferir `./scripts/update_indicators.py` para hacer la actualizacion de forma determinista.
- Leer `./references/input-format.md` solo si hace falta confirmar columnas, alias o formulas.

## Flujo Principal

- Esperar un archivo base existente, por ejemplo `indicadores.xlsx` o `./output/indicadores.csv`.
- Si no se indica archivo, crear o reutilizar el archivo vivo `./output/Datos_Financieros_Semanales.xlsx` a partir de `./assets/Datos_Financieros_Semanales.xlsx`.
- Tomar del prompt los nuevos datos semanales, por ejemplo semana, ingresos, perdidas y clientes.
- Buscar la fila de esa semana en el archivo:
  - Si existe, sobrescribir sus valores con los nuevos datos.
  - Si no existe, agregar una nueva fila al final.
- Recalcular las metricas del archivo.
- Actualizar el mismo archivo por defecto.
- Guardar una copia de respaldo o resumen en `./output/` cuando ayude a trazabilidad o recuperacion.

Ejemplos de prompts esperados:

- `Actualiza el archivo indicadores.xlsx con la semana 2026-W12, revenue 125000, losses 9300 y customers 1820.`
- `Actualiza indicadores-base.csv con estos datos: semana 2026-W12, ingresos 125000, perdidas 9300, clientes 1820.`
- `En el archivo output/indicadores.xlsx reemplaza la semana 2026-W12 con estos valores y recalcula metricas.`
- `Actualiza los indicadores de esta semana con ingresos 125000, perdidas 9300 y clientes 1820 usando el archivo por defecto.`

## Esperar Entrada

- Aceptar archivos `csv`, `xlsx` o `xlsm`.
- Esperar una tabla plana con encabezados en la primera fila y una fila por semana.
- Requerir una columna de semana con alguno de estos encabezados o equivalentes: `week`, `semana`, `period`, `periodo`.
- Requerir columnas base para ingresos, perdidas y clientes con encabezados compatibles con:
  - `revenue` o `ingresos`
  - `losses` o `perdidas`
  - `customers` o `clientes`
- Aceptar columnas opcionales:
  - `previous_customers`
  - `retained_customers`
  - `retention_rate`
  - `loss_percentage`
  - `margin`
- Mantener el archivo ordenado cronologicamente cuando la retencion dependa de la fila anterior.

## Contrato JSON Opcional

Usar este payload como contrato interno del script cuando haga falta estructurar la llamada. No pedirlo al usuario salvo que la automatizacion lo requiera.

```json
{
  "file_path": "Datos_Financieros_Semanales.xlsx",
  "sheet_name": "Indicadores",
  "week": "2026-W12",
  "summary_path": "indicadores-W12-summary.json",
  "updates": {
    "revenue": 125000,
    "losses": 9300,
    "customers": 1820,
    "previous_customers": 1885,
    "retained_customers": 1790
  }
}
```

- Tratar `file_path`, `sheet_name`, `summary_path`, `previous_customers` y `retained_customers` como opcionales.
- Si `file_path` no llega, usar `./assets/Datos_Financieros_Semanales.xlsx` como base y `./output/Datos_Financieros_Semanales.xlsx` como archivo de trabajo.
- Resolver `summary_path` siempre dentro de `./output/` cuando se pase como ruta relativa.
- Requerir `week` y `updates.revenue`, `updates.losses`, `updates.customers`.

## Flujo

- Cargar el archivo base.
- Resolver la ruta del archivo nombrado por el usuario.
- Si no se especifica archivo, sembrar el archivo vivo dentro de `./output/` usando el Excel de `./assets/`.
- Detectar columnas existentes con alias compatibles en ingles o espanol.
- Crear las columnas calculadas faltantes sin romper el resto de la tabla.
- Materializar tambien `previous_customers` y `retained_customers` cuando se infieran para que la retencion quede visible en el archivo.
- Aplicar los valores de la semana solicitada.
- Actualizar la fila si la semana ya existe.
- Agregar una fila nueva si la semana no existe.
- Validar campos requeridos, valores negativos, duplicados de semana y datos no numericos en columnas financieras.
- Recalcular para todas las filas:
  - `retention_rate`
  - `loss_percentage`
  - `margin`
- Actualizar siempre el mismo archivo de trabajo.
- Guardar la copia de respaldo en `./output/`.

## Formulas

- Calcular `retention_rate` como `retained_customers / previous_customers`.
- Si `retained_customers` no existe, derivarlo como `min(customers, previous_customers)`.
- Si `previous_customers` no existe, usar los clientes de la fila anterior como base.
- Materializar `previous_customers` y `retained_customers` en el archivo cuando hayan sido inferidos.
- Calcular `loss_percentage` como `losses / revenue`.
- Calcular `margin` como `(revenue - losses) / revenue`.
- Guardar las metricas como ratios decimales entre `0` y `1`.

## Comandos

- Ejecutar con JSON:

```bash
python ./.codex/skills/actualizar-indicadores/scripts/update_indicators.py --input-json payload.json
```

- Ejecutar con JSON desde stdin:

```bash
Get-Content payload.json | python ./.codex/skills/actualizar-indicadores/scripts/update_indicators.py --input-json -
```

- Ejecutar con argumentos:

```bash
python ./.codex/skills/actualizar-indicadores/scripts/update_indicators.py ^
  --week 2026-W12 ^
  --revenue 125000 ^
  --losses 9300 ^
  --customers 1820 ^
  --previous-customers 1885 ^
  --summary-output indicadores-W12-summary.json
```

## Salida

- Actualizar el archivo original por defecto.
- Si se usa el archivo por defecto, mantener el archivo vivo en `./output/Datos_Financieros_Semanales.xlsx`.
- Guardar una copia de respaldo en `./output/`.
- Entregar opcionalmente un resumen JSON con cambios, advertencias y metricas recalculadas.
- Imprimir tambien un resumen JSON en stdout para facilitar automatizacion.

## Validaciones

- Rechazar archivos sin columna de semana.
- Rechazar semanas duplicadas en el archivo base.
- Rechazar formatos no soportados como `.xls`.
- Rechazar valores negativos o no numericos en ingresos, perdidas y clientes.
- No asumir formulas de Excel en columnas gestionadas; esperar valores ya materializados.
- En Excel, esperar una hoja plana con encabezados en la fila 1 y sin celdas combinadas en las columnas gestionadas.
- Si el entorno restringe escrituras dentro de `.codex/skills`, pedir permiso antes de escribir en `./output/`.

## Triggers

- `actualiza el archivo indicadores.xlsx con estos datos`
- `actualiza indicadores de esta semana`
- `carga datos semanales y recalcula metricas`
- `actualiza el archivo base de indicadores financieros`
- `recalcula retencion, perdidas y margen del corte semanal`
