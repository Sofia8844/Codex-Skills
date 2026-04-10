# Input Format

## Expected Table Shape

- Use one row per week.
- Keep headers on row 1.
- Keep the sheet flat in the managed area.
- Keep the file ordered by week if `previous_customers` is inferred from the prior row.
- Treat the workbook or CSV as the persistent base file that gets updated week after week.
- When the user does not name a file, use `assets/Datos_Financieros_Semanales.xlsx` as the source seed and keep the live file in `output/Datos_Financieros_Semanales.xlsx`.

## Required Fields

- `week` or `semana`
- `revenue` or `ingresos`
- `losses` or `perdidas`
- `customers` or `clientes`

## Optional Fields

- `previous_customers`
- `retained_customers`
- `retention_rate`
- `loss_percentage`
- `margin`

## Alias Rules

- The script normalizes headers to lowercase, removes accents, and converts spaces or symbols to `_`.
- Examples:
  - `Semana` -> `semana`
  - `Ingresos Netos` -> `ingresos_netos`
  - `Perdidas %` -> `perdidas`

## Metric Rules

- `retention_rate = retained_customers / previous_customers`
- If `retained_customers` is missing, use `min(customers, previous_customers)`.
- If `previous_customers` is missing, use the previous row customer value.
- `loss_percentage = losses / revenue`
- `margin = (revenue - losses) / revenue`

## Output Notes

- Ratios are written as decimal values between `0` and `1`.
- If `previous_customers` or `retained_customers` are inferred, the script materializes those columns in the output file so the retention inputs stay visible.
- Default mode updates the named source file in place.
- If the default seeded file is used, all live updates, backups, and summaries stay inside `actualizar-indicadores/output/`.
- When the file is updated in place, keep backups or summaries in `output/`.
