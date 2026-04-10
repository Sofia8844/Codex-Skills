# Arquitectura de Jobs Asincronos para Skills

## Estado actual

La base ya esta implementada y validada con Docker Compose:

- `POST /jobs` crea el job en PostgreSQL con estado `PENDING`
- la API publica en `skill_jobs`
- `skill-worker` consume, cambia a `RUNNING`, ejecuta el proceso con `spawn`
- al terminar actualiza a `COMPLETED` o `FAILED`
- luego publica en `email_jobs`
- `email-worker` envia el correo y marca la notificacion como `SENT`

Prueba validada en este workspace:

- job `demo.echo` procesado correctamente
- `notificationStatus = SENT`
- correo visible en MailHog

## Estructura del proyecto

```text
src/
  apps/
    api/
      app.ts
      server.ts
      routes/
      services/
    skill-worker/
      index.ts
    email-worker/
      index.ts
  shared/
    config/
    db/
    jobs/
    logging/
    processes/
    rabbitmq/
skills/
  demo-skill.mjs
infra/
  docker/
    api.Dockerfile
    worker.Dockerfile
  sql/
    001_create_jobs.sql
docs/
  async-jobs-architecture.md
docker-compose.yml
package.json
tsconfig.json
```

## Tabla `jobs`

Campos principales:

- `id`
- `skill_name`
- `status`
- `notification_email`
- `notification_status`
- `payload`
- `attempts`
- `stdout`
- `stderr`
- `error_message`
- `output_file`
- `exit_code`
- `started_at`
- `finished_at`
- `notification_queued_at`
- `notification_sent_at`
- `notification_error`
- `created_at`
- `updated_at`

## Skills registradas hoy

- `demo.echo`: smoke test del pipeline
- `codex.exec`: preparado para invocar Codex CLI directamente
- `presentation.codex-script`: usa `generar_ppt_codex.js`

## Como levantar el entorno

1. Construir imagenes:

```bash
docker compose build api skill-worker email-worker
```

2. Levantar servicios:

```bash
docker compose up -d
```

3. Verificar salud:

```bash
curl http://localhost:3000/health
```

Servicios utiles:

- API: `http://localhost:3000`
- RabbitMQ UI: `http://localhost:15672`
- MailHog UI: `http://localhost:8025`

## Como probar el flujo

Ejemplo PowerShell:

```powershell
$body = @{
  skillName = "demo.echo"
  notifyEmail = "sofia@example.com"
  payload = @{
    message = "Prueba end-to-end"
    delayMs = 1500
    outputFile = "output/demo-job.txt"
  }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:3000/jobs" `
  -ContentType "application/json" `
  -Body $body
```

Luego consultar el job:

```powershell
Invoke-RestMethod -Uri "http://localhost:3000/jobs/<JOB_ID>"
```

## Consideraciones de diseño

- Se usa `spawn`, no `exec`
- El `ack` ocurre solo despues de completar la logica critica
- Los mensajes son persistentes y las colas son durables
- La topologia ya esta preparada para agregar DLQ via variables
- Hay reintentos de conexion a RabbitMQ al arrancar
- `attempts` se incrementa al entrar en `RUNNING`
- `output/` se monta como volumen para persistir archivos generados por skills

## Siguiente fase recomendada

1. Agregar un registry mas fuerte para skills reales de Codex por nombre y version.
2. Incorporar migraciones formales (`dbmate`, `node-pg-migrate` o similar).
3. Añadir autenticacion y autorizacion en la API.
4. Registrar eventos de auditoria en una tabla `job_events`.
5. Implementar DLQ y estrategia de retry por tipo de error.
6. Exponer un endpoint para descargar `output_file`.
