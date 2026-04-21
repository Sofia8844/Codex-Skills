# Network Design To Quote Contract

## Purpose

This contract decouples `diseno-redes-empresariales` from `cotizacion-redes-empresariales`.
The design skill emits a deterministic `handoff` JSON.
The quote skill consumes that JSON without depending on the design skill internals.

## Rule

If the previous skill knows a value, it sends it.
If it does not know it, it omits it.

The sender must not invent or backfill unknown values.

## Canonical Structure

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

## Required Fields

- `site_name`
- `technical_design.recommended_access_points` if `needs.wireless = true`
- `technical_design.recommended_access_switches` if `needs.switching = true`
- `technical_design.required_switch_ports_with_reserve` if `needs.switching = true`
- `technical_design.required_poe_ports_with_reserve` if `needs.switching = true`
- `technical_design.edge_category` if `needs.edge = true`
- `technical_design.estimated_required_throughput_mbps` if `needs.edge = true`

## Optional But Recommended

- `manufacturer_preference`
- `budget_level`
- `budget_usd`
- `technical_design.effective_redundancy_level`
- `technical_design.edge_router_firewall_count`
- `technical_design.environment`
- `needs.support`

## Validation Notes

- The design skill must not emit an invalid handoff contract.
- The quote skill must reject or clearly report missing required fields for the active scope.
- Optional fields may be omitted.
- Fallback inference is allowed only inside the quote skill and only for fields documented there as inferable.
