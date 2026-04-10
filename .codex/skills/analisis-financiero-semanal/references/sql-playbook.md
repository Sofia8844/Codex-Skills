# SQL Playbook

## Descubrir Esquema

Usar primero consultas de descubrimiento antes de escribir agregaciones definitivas.

```sql
SELECT
  table_name,
  column_name,
  data_type
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name IN ('transactions', 'customers', 'products')
ORDER BY table_name, ordinal_position;
```

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = DATABASE()
ORDER BY table_name;
```

## Confirmar Campos Operativos

Buscar equivalentes de estas columnas:

- En `transactions`:
  - id de transaccion
  - fecha de transaccion
  - customer_id
  - product_id
  - net_amount o gross_amount
  - cost_amount, cogs o campo similar
  - status
- En `customers`:
  - id
  - created_at
  - segment, tier, region o canal
- En `products`:
  - id
  - product_name
  - category
  - unit_cost o costo

## Agregacion Semanal Base

Adaptar nombres de columnas al esquema real.

```sql
SELECT
  YEARWEEK(t.transaction_date, 3) AS iso_week,
  SUM(t.net_amount) AS revenue,
  SUM(COALESCE(t.cost_amount, 0)) AS cost,
  COUNT(DISTINCT t.customer_id) AS customers,
  COUNT(*) AS transactions
FROM transactions t
WHERE t.transaction_date >= @week_start
  AND t.transaction_date < @week_end
  AND COALESCE(t.status, 'paid') NOT IN ('cancelled', 'failed', 'refunded')
GROUP BY YEARWEEK(t.transaction_date, 3);
```

## Ingresos y Margen por Producto

```sql
SELECT
  p.id,
  p.product_name,
  p.category,
  SUM(t.net_amount) AS product_revenue,
  SUM(COALESCE(t.cost_amount, 0)) AS product_cost,
  SUM(t.net_amount) - SUM(COALESCE(t.cost_amount, 0)) AS product_profit
FROM transactions t
JOIN products p ON p.id = t.product_id
WHERE t.transaction_date >= @week_start
  AND t.transaction_date < @week_end
  AND COALESCE(t.status, 'paid') NOT IN ('cancelled', 'failed', 'refunded')
GROUP BY p.id, p.product_name, p.category
ORDER BY product_profit DESC;
```

Si no existe costo en `transactions`, revisar si `products` tiene `unit_cost` y multiplicar por cantidad solo si el modelo lo soporta.

## Ingresos por Cliente

```sql
SELECT
  c.id,
  c.segment,
  SUM(t.net_amount) AS customer_revenue,
  COUNT(*) AS customer_transactions
FROM transactions t
JOIN customers c ON c.id = t.customer_id
WHERE t.transaction_date >= @week_start
  AND t.transaction_date < @week_end
  AND COALESCE(t.status, 'paid') NOT IN ('cancelled', 'failed', 'refunded')
GROUP BY c.id, c.segment
ORDER BY customer_revenue DESC;
```

## Clientes Recurrentes

```sql
SELECT
  COUNT(DISTINCT CASE WHEN h.customer_id IS NOT NULL THEN w.customer_id END) AS recurring_customers,
  COUNT(DISTINCT CASE WHEN h.customer_id IS NULL THEN w.customer_id END) AS new_customers
FROM (
  SELECT DISTINCT customer_id
  FROM transactions
  WHERE transaction_date >= @week_start
    AND transaction_date < @week_end
) w
LEFT JOIN (
  SELECT DISTINCT customer_id
  FROM transactions
  WHERE transaction_date < @week_start
) h ON h.customer_id = w.customer_id;
```

## Comportamiento por Segmento

```sql
SELECT
  c.segment,
  SUM(t.net_amount) AS revenue,
  COUNT(DISTINCT t.customer_id) AS customers,
  COUNT(*) AS transactions
FROM transactions t
JOIN customers c ON c.id = t.customer_id
WHERE t.transaction_date >= @week_start
  AND t.transaction_date < @week_end
  AND COALESCE(t.status, 'paid') NOT IN ('cancelled', 'failed', 'refunded')
GROUP BY c.segment
ORDER BY revenue DESC;
```

## Comparacion Semanal

- Ejecutar la misma consulta para la semana previa.
- Unir resultados por producto, cliente o segmento.
- Calcular diferencias absolutas y porcentuales fuera de SQL si eso simplifica la lectura.

## Notas

- Sustituir `@week_start` y `@week_end` por el rango real del periodo.
- Ajustar `YEARWEEK(..., 3)` si el negocio no usa calendario ISO.
- Documentar toda adaptacion de nombres de tabla o columna en la respuesta final.
