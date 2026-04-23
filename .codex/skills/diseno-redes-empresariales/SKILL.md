---
name: diseno-redes-empresariales
description: Analyze real enterprise network design requirements and generate technically grounded, explainable recommendations using deterministic rules plus a bundled knowledge base. Use when Codex must act as an expert network engineer for corporate multi-floor sites, small offices, industrial environments, high-density Wi-Fi, IoT/OT networks, critical voice/video traffic, redundancy, VLAN segmentation, load balancing, budget constraints, vendor compatibility, or network infrastructure sizing.
---

# Diseno Redes Empresariales

## Principio

Actuar como ingeniero de redes. Convertir el requerimiento en variables tecnicas, ejecutar el evaluador deterministico y explicar la recomendacion con calculos y reglas aplicadas.

Este skill sigue entregando respuesta en lenguaje natural, pero ahora tambien genera:

- un contrato JSON de handoff para `cotizacion-redes-empresariales`
- un PDF con la misma explicacion natural

La logica tecnica vive aqui. El contrato compartido vive fuera del skill en `.codex/contracts/network-design-to-quote/` para mantener desacople real.

## Contrato De Handoff

Proposito:

- desacoplar `diseno-redes-empresariales` de `cotizacion-redes-empresariales`
- permitir que cotizacion consuma un JSON estable sin depender de reglas internas del skill tecnico

Ubicacion del contrato:

- `.codex/contracts/network-design-to-quote/CONTRACT.md`
- `.codex/contracts/network-design-to-quote/handoff.schema.json`

Regla obligatoria:

- si el skill anterior lo sabe: lo envia
- si no lo sabe: lo omite

No inventar ni completar valores no calculados.

## Estructura Canonica

```json
{
  "handoff": {
    "contract_version": "1.0",
    "source_skill": "diseno-redes-empresariales",
    "target_skill": "cotizacion-redes-empresariales",
    "quote_ready_input": {
      "site_name": "Sede Norte",
      "manufacturer_preference": "Cisco",
      "budget_level": "medium",
      "budget_usd": 25000,
      "technical_design": {
        "recommended_access_points": 6,
        "recommended_access_switches": 2,
        "required_switch_ports_with_reserve": 72,
        "required_poe_ports_with_reserve": 40,
        "effective_redundancy_level": "high",
        "edge_category": "business_router_firewall",
        "edge_router_firewall_count": 2,
        "estimated_required_throughput_mbps": 850,
        "environment": "corporate"
      },
      "needs": {
        "wireless": true,
        "switching": true,
        "edge": true,
        "support": true
      }
    }
  }
}
```

## Campos Requeridos Y Opcionales

Requeridos segun alcance:

- `site_name`
- `technical_design.recommended_access_points` si `needs.wireless = true`
- `technical_design.recommended_access_switches` si `needs.switching = true`
- `technical_design.required_switch_ports_with_reserve` si `needs.switching = true`
- `technical_design.required_poe_ports_with_reserve` si `needs.switching = true`
- `technical_design.edge_category` si `needs.edge = true`
- `technical_design.estimated_required_throughput_mbps` si `needs.edge = true`

Opcionales pero recomendados:

- `manufacturer_preference`
- `budget_level`
- `budget_usd`
- `technical_design.effective_redundancy_level`
- `technical_design.edge_router_firewall_count`
- `technical_design.environment`
- `needs.support`

## Flujo

1. Extraer variables del requerimiento:
   - `devices` por tipo: `laptops`, `mobiles`, `iot`, `phones`, `cameras`, `printers`, `servers`, u otros.
   - `traffic_profile`: `low`, `medium`, `high`, o `critical`.
   - `floors` y/o `area_m2`.
   - `environment`: `small_office`, `corporate`, `high_density`, `industrial`, o `mixed`.
   - `redundancy_required`: `false`, `basic`, `high`, o `mission_critical`.
   - `budget_level`: `low`, `medium`, `high`; y `budget_usd` si existe.
   - `manufacturers` si el usuario menciona marcas.
   - `critical_services`: por ejemplo `voice`, `video`, `erp`, `pos`, `ot_control`, `security`.
2. Si faltan datos criticos, pedirlos antes de recomendar. Datos criticos: cantidad de dispositivos o `devices`, perfil de trafico, y al menos `floors` o `area_m2`.
3. Construir un JSON de entrada con claves canonicas en ingles.
4. Definir la carpeta de trabajo del caso. Por defecto debe ser `analysis_output/<site_name_slug>/`. Usar esa misma carpeta para el Markdown, el JSON de handoff y el PDF.
5. Ejecutar el evaluador para obtener el resultado tecnico deterministico que alimentara la explicacion y el contrato:

```bash
python .codex/skills/diseno-redes-empresariales/scripts/evaluate_network_design.py --input path/to/input.json --pretty
```

6. Leer solo los documentos de `knowledge/` necesarios para explicar el resultado.
7. Redactar una recomendacion estructurada basada en la salida del evaluador. No agregar cantidades o decisiones que no aparezcan en `decision`, `sizing`, `rules_applied`, `constraints` o `technical_reasons`.
8. Antes de ejecutar `export_design_outputs.py`, guardar esa explicacion final visible en:

```text
analysis_output/<site_name_slug>/network_design_explanation.md
```

9. Ejecutar el flujo operativo principal del skill con el exportador. Este script vuelve a evaluar internamente para construir el handoff, detecta `network_design_explanation.md` en la carpeta del caso y genera el PDF desde ese mismo texto:

```bash
python .codex/skills/diseno-redes-empresariales/scripts/export_design_outputs.py --input path/to/input.json --output-dir analysis_output/<site_name_slug> --pretty
```

Si ya existe una explicacion final visible en Markdown y se quiere forzar una ruta concreta, el exportador tambien acepta:

```bash
python .codex/skills/diseno-redes-empresariales/scripts/export_design_outputs.py --input path/to/input.json --explanation-file path/to/network_design_explanation.md --pretty
```

## Flujo Actual Del Skill

Hoy el flujo operativo real es este:

1. Codex o el usuario ejecuta `export_design_outputs.py`.
2. `export_design_outputs.py` carga el input estructurado.
3. El exportador llama internamente a `evaluate_network_design.py`.
4. El motor devuelve el resultado tecnico deterministico.
5. El exportador genera:
   - `network_design_handoff.json`
   - `network_design_explanation.md`
   - `network_design_explanation.pdf`

Importante:

- `evaluate_network_design.py` por si solo sirve para revisar calculos.
- `export_design_outputs.py` es el script principal del skill para producir salidas reales.
- No es obligatorio correr ambos scripts por separado.

## Flujo Objetivo Para Explicacion Unificada

Objetivo de evolucion del skill:

1. Codex evalua con el motor deterministico.
2. Codex redacta la explicacion final rica en lenguaje natural.
3. Codex guarda esa misma explicacion visible en `network_design_explanation.md`.
4. Codex ejecuta `export_design_outputs.py`.
5. El exportador detecta `network_design_explanation.md` y usa ese contenido para generar `network_design_explanation.pdf`.
6. Si el archivo `.md` no existe, el exportador usa como fallback la explicacion base del motor.

Esto permite que:

- la respuesta final de Codex y el PDF usen la misma explicacion visible
- el contrato JSON siga separado e intacto
- el motor deterministico siga siendo la fuente de datos tecnicos
- el PDF no dependa de una redaccion quemada en codigo como fuente principal

## Respuesta Obligatoria

La respuesta final al usuario no puede ser solo una lista de cantidades ni un resumen generico.
Debe responder como un ingeniero de redes experto y justificar explicitamente cada decision principal.

La salida al usuario debe incluir SIEMPRE estas secciones, en este orden:

1. `Resumen de la solucion`
2. `Decisiones de diseno`
3. `Calculos realizados`
4. `Reglas aplicadas`
5. `Segmentacion y seguridad`
6. `Redundancia y disponibilidad`
7. `Supuestos y restricciones`
8. `Recomendaciones adicionales`

## Justificacion Tecnica Obligatoria

Cada decision importante debe explicar:

- que se decidio
- por que se decidio
- que criterio tecnico o regla lo sostiene
- que limitacion, tradeoff o supuesto aplica

No basta con decir:

- "se recomiendan 6 APs"
- "se recomiendan 2 switches"

Se debe explicar, por ejemplo:

- si el conteo se definio por capacidad, por cobertura o por minimo por piso
- si el edge se eligio por throughput, concurrencia o redundancia
- si la segmentacion responde a IoT, voz, invitados, OT o seguridad

## Uso Explicito De Knowledge

La base `knowledge/` debe usarse activamente para justificar la respuesta, no solo para citar archivos o devolver referencias.

Usar estos documentos segun el caso:

- `knowledge/dimensioning-principles.md`
  - justificar APs, throughput, edge, puertos, PoE, crecimiento y criterios de dimensionamiento
- `knowledge/segmentation-and-security.md`
  - justificar VLANs, aislamiento, guest, IoT, voz, seguridad y politicas entre segmentos
- `knowledge/redundancy-and-availability.md`
  - justificar HA, dual WAN, stacking, core redundante, continuidad y manejo de fases por presupuesto
- `knowledge/vendor-guidance.md`
  - justificar cautelas de interoperabilidad, validaciones contra datasheet y limites de capacidades por fabricante

La respuesta debe incorporar ese conocimiento en lenguaje natural, por ejemplo:

- "segun los principios de dimensionamiento, el Wi-Fi debe definirse por el mayor valor entre capacidad y cobertura"
- "segun la guia de segmentacion, invitados e IoT no deben compartir el mismo dominio de confianza"
- "segun la guia de redundancia, voz, video, OT o seguridad elevan el objetivo minimo de disponibilidad"

No limitarse a poner:

- `knowledge/dimensioning-principles.md`
- `knowledge/segmentation-and-security.md`

## Calidad Esperada De La Explicacion

Una respuesta valida debe:

- explicar el razonamiento tecnico completo
- conectar calculos con decisiones
- conectar decisiones con reglas aplicadas
- conectar reglas con principios de `knowledge/`
- diferenciar hechos calculados, supuestos y restricciones

Una respuesta no es valida si:

- solo enumera cantidades
- repite el JSON en lenguaje natural
- omite el por que de las decisiones
- menciona `knowledge/` pero no lo usa para justificar

## Formato Y Presentacion

Cuando la informacion lo requiera, el skill debe organizar la respuesta con tablas claras y legibles.

Usar tablas especialmente para:

- dimensionamiento de equipos, cantidades y capacidades
- comparacion de opciones o alternativas
- distribucion de puertos, PoE o access points
- segmentacion de red y objetivo de cada VLAN

Usar listas estructuradas cuando no aplique tabla o cuando una tabla no aporte claridad real.

No devolver bloques largos de texto si una tabla mejora la comprension.

Ejemplo de uso esperado:

| Componente | Cantidad | Justificacion |
| --- | ---: | --- |
| Access Points | 6 | Cobertura por area segun densidad y minimo por piso |
| Switches | 2 | Capacidad de puertos con reserva y crecimiento |

Si se usan tablas, igual deben mantenerse la justificacion tecnica y las secciones obligatorias.

## Archivos De Salida

Por defecto, los artefactos se generan en `analysis_output/<site_name>/`.
Si se pasa `--output-dir`, se respeta esa ruta explicita.

Nombres estables y predecibles:

- `network_design_handoff.json`
- `network_design_explanation.md`
- `network_design_explanation.pdf`

El skill no debe emitir `network_design_handoff.json` si el contrato queda invalido.
Si existe `network_design_explanation.md`, el PDF debe generarse desde ese mismo texto visible.

## Reglas De Rigor

- No inventar capacidades de equipos especificos.
- No sumar "routers" para cubrir Wi-Fi.
- Dimensionar Wi-Fi por el mayor valor entre capacidad concurrente, cobertura por area y minimo por pisos.
- Para trafico `high` o `critical`, reducir la densidad aceptable por AP y exigir QoS para voz/video.
- Para IoT/OT o camaras, crear segmentacion dedicada.
- Si hay redundancia alta o servicios criticos, proponer dual WAN, HA en borde, core/distribution redundante o stacking segun tamano.
- Si el presupuesto contradice la disponibilidad requerida, reportar el conflicto.
- Si hay multiples fabricantes, no convertir automaticamente una lista de marcas en preferencia unica de cotizacion.

## Recursos

- `scripts/evaluate_network_design.py`: motor deterministico de evaluacion.
- `scripts/export_design_outputs.py`: exporta handoff JSON y PDF.
- `rules/technical_rules.json`: reglas numericas y umbrales.
- `knowledge/`: base RAG para explicar buenas practicas.
- `examples/`: entradas y salidas de referencia.
- `output/`: artefactos generados por el skill.
