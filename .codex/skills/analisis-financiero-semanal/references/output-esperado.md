# Output Esperado

## Estructura Recomendada

- `Resumen ejecutivo`
- `KPIs reconciliados`
- `Insights de negocio`
- `Alertas y calidad de datos`
- `Siguientes acciones`

## Resumen Ejecutivo

Incluir de 3 a 5 hallazgos maximo, priorizados por impacto.

## KPIs Reconciliados

Presentar una tabla compacta con:

- KPI
- valor del Excel
- valor de la base
- diferencia absoluta
- diferencia porcentual
- comentario corto

## Insights de Negocio

Cubrir como minimo:

- margen o rentabilidad por producto
- ingresos por cliente
- clientes recurrentes vs nuevos
- productos mas rentables
- crecimiento semana contra semana
- comportamiento por segmento

## Alertas

Listar explicitamente:

- faltantes de costo o margen
- diferencias entre Excel y base
- definiciones ambiguas de fecha o estado
- campos inferidos o aproximados

## JSON Opcional

Si ayuda a automatizacion o trazabilidad, emitir ademas un resumen JSON como este:

```json
{
  "analysis_period": "2026-W12",
  "source_file": "Datos_Financieros_Semanales.xlsx",
  "reconciled_kpis": {
    "revenue": {
      "excel_value": 125000,
      "db_value": 123840,
      "delta_abs": -1160,
      "delta_pct": -0.0093
    }
  },
  "insights": {
    "top_product_by_profit": "Producto A",
    "top_customer_by_revenue": "Cliente 102",
    "recurring_customers": 148
  },
  "alerts": [],
  "recommended_actions": []
}
```
