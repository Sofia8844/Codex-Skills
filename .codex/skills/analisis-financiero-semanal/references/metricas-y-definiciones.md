# Metricas y Definiciones

## KPI Base

- `weekly_revenue`: sumar ingresos netos de la semana. Si solo existe ingreso bruto, indicarlo.
- `weekly_customers`: contar clientes unicos con al menos una transaccion valida en la semana.
- `weekly_transactions`: contar transacciones validas del periodo.
- `weekly_losses`: usar la perdida reportada en el Excel solo como KPI agregado, salvo que la base tenga una columna homologable.

## Reconciliacion Excel vs Base

- Tratar el Excel como resumen semanal entregado por analista.
- Tratar la base como detalle de soporte para validar y expandir el analisis.
- Calcular para cada KPI principal:
  - `excel_value`
  - `db_value`
  - `delta_abs = db_value - excel_value`
  - `delta_pct = (db_value - excel_value) / excel_value`
- Resaltar diferencias materiales cuando el delta porcentual supere el umbral operativo definido por el usuario o, si no existe, cuando el contexto lo vuelva relevante.

## Metricas Derivadas

### Margen por producto

- Calcular `product_margin = (product_revenue - product_cost) / product_revenue`.
- Calcular `product_profit = product_revenue - product_cost`.
- Si no existe costo por producto, no presentar margen real. Presentar `revenue_share` y anotar la limitacion.

### Ingresos por cliente

- Calcular ingreso total por cliente en la semana.
- Ordenar por valor absoluto y tambien por contribucion porcentual al ingreso total.
- Separar clientes nuevos y recurrentes si existe historial suficiente.

### Clientes recurrentes

- Definir cliente recurrente como cliente con compra en la semana analizada y al menos una compra anterior al inicio de esa semana.
- Calcular:
  - `recurring_customers`
  - `new_customers`
  - `recurring_revenue_share`
- Si el negocio maneja suscripciones, aclarar si la recurrencia se mide por compras o por renovaciones.

### Productos mas rentables

- Medir por `product_profit` cuando exista costo.
- Complementar con ranking por margen y por ingresos para evitar sesgos.
- Excluir productos con volumen marginal si distorsionan la lectura.

### Crecimiento semanal

- Calcular crecimiento contra la semana anterior con:
  - `wow_growth = (current_week - previous_week) / previous_week`
- Aplicar la formula a ingresos, clientes, transacciones y utilidad cuando sea posible.
- Si la semana previa es cero o no existe, reportar el cambio como no comparable.

### Comportamiento por segmento

- Agrupar por `customer_segment`, `product_category`, `channel` o el atributo disponible que mejor represente segmentos reales.
- Comparar por ingreso, clientes, ticket promedio, recurrencia y margen si aplica.
- Senalar segmentos que crecen con mala rentabilidad o segmentos pequenos con alto margen.

## Reglas de Calidad

- Excluir estados no validos como `cancelled`, `failed` o `refunded` cuando existan.
- Verificar duplicados de transaccion antes de agregar.
- Confirmar si el periodo se mide por fecha de compra, fecha de pago o fecha de contabilizacion.
- Indicar toda imputacion, filtro o suposicion usada en el analisis.
