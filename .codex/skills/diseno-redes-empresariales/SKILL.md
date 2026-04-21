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
4. Ejecutar el evaluador:

```bash
python .codex/skills/diseno-redes-empresariales/scripts/evaluate_network_design.py --input path/to/input.json --pretty
```

5. Exportar handoff y PDF:

```bash
python .codex/skills/diseno-redes-empresariales/scripts/export_design_outputs.py --input path/to/input.json --pretty
```

6. Leer solo los documentos de `knowledge/` necesarios para explicar el resultado.
7. Redactar una recomendacion estructurada basada en la salida del script. No agregar cantidades o decisiones que no aparezcan en `decision`, `sizing`, `rules_applied`, `constraints` o `technical_reasons`.

## Archivos De Salida

Nombres estables y predecibles en `output/`:

- `output/network_design_handoff.json`
- `output/network_design_explanation.pdf`

El skill no debe emitir `network_design_handoff.json` si el contrato queda invalido.

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
