# Expected Outputs

These summaries are generated from `scripts/evaluate_network_design.py` and help validate that the skill produces explainable decisions. Full JSON can be regenerated with `--pretty`.

The handoff contract and PDF can be regenerated with:

```bash
python .codex/skills/diseno-redes-empresariales/scripts/export_design_outputs.py --input .codex/skills/diseno-redes-empresariales/examples/corporate-multifloor-input.json --pretty
```

## corporate-multifloor-input.json

- Status: `ok`
- Decision: `Recommend 16 APs, 3 access switches, 2 business_router_firewall edge device(s), and 6 VLANs.`
- Key calculations:
  - Total devices: `225`
  - Estimated concurrent clients: `180.0`
  - Required throughput after headroom: `892.18 Mbps`
  - AP sizing: `max(capacity 4, coverage 16, floor minimum 3) = 16`
  - Edge sizing: `180 clients <= 200`, `892.18 Mbps <= 1000 Mbps`
  - VLANs: `collaboration`, `corporate`, `guest`, `iot`, `management`, `voice`
- Rules expected: `WIFI-001`, `WIFI-002`, `WIFI-003`, `EDGE-001`, `SW-001`, `SW-002`, `SEG-001`, `SEG-002`, `SEG-003`, `RED-001`, `QOS-001`

## small-office-input.json

- Status: `ok`
- Decision: `Recommend 2 APs, 1 access switches, 1 branch_router_firewall edge device(s), and 4 VLANs.`
- Key calculations:
  - Total devices: `42`
  - Estimated concurrent clients: `30.3`
  - Required throughput after headroom: `88.01 Mbps`
  - AP sizing: `max(capacity 1, coverage 2, floor minimum 1) = 2`
  - Edge sizing: `30.3 clients <= 80`, `88.01 Mbps <= 300 Mbps`
  - VLANs: `corporate`, `guest`, `management`, `services`
- Rules expected: `WIFI-001`, `WIFI-002`, `WIFI-003`, `EDGE-001`, `SW-001`, `SW-002`, `SEG-001`, `SEG-002`, `RED-001`

## industrial-critical-input.json

- Status: `ok`
- Decision: `Recommend 51 APs, 5 access switches, 2 enterprise_utm_firewall edge device(s), and 7 VLANs.`
- Key calculations:
  - Total devices: `277`
  - Estimated concurrent clients: `252.75`
  - Required throughput after headroom: `1326.48 Mbps`
  - AP sizing: `max(capacity 7, coverage 51, floor minimum 1) = 51`
  - Edge sizing: `252.75 clients <= 500`, `1326.48 Mbps <= 2500 Mbps`
  - VLANs: `corporate`, `guest`, `iot`, `management`, `ot`, `security`, `voice`
  - Constraint: numeric budget `85000` is below rough estimate `87188`
- Rules expected: `WIFI-001`, `WIFI-002`, `WIFI-003`, `EDGE-001`, `SW-001`, `SW-002`, `SEG-001`, `SEG-002`, `SEG-003`, `RED-001`, `QOS-001`, `BUD-002`
