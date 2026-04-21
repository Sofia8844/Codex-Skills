# Vendor Guidance

Use this as vendor-neutral RAG. Do not claim exact product limits unless a current datasheet is provided.

## What to verify in datasheets

- AP: radio generation, number of radios, spatial streams, supported bands, recommended clients, uplink speed and PoE class.
- Firewall/router: inspected throughput, VPN throughput, concurrent sessions, WAN interfaces, HA support and license requirements.
- Switch: PoE budget, per-port PoE class, uplink speed, stacking/MLAG support, VLAN scale and Layer 3 features.
- Controller/cloud: AP license model, roaming features, RF optimization, guest portal and multi-site management.

## Compatibility guidance

- Prefer one WLAN management ecosystem per site unless there is a deliberate multi-vendor operations model.
- Multi-vendor switching can work when VLANs, LACP, STP/RSTP/MSTP, LLDP, 802.1X and routing protocols are standard and documented.
- Avoid designs that require proprietary roaming, controller or stacking features across different manufacturers.
- If the user names manufacturers, keep the recommendation at architecture and capability level until final SKUs are available.

## Manufacturer-style best practices

- Validate RF with a site survey for high-density, industrial or critical voice deployments.
- Design for realistic concurrent client counts, not marketing maximum association counts.
- Keep firmware, controller versions and licenses aligned across APs and switches.
- Reserve capacity for growth, security inspection and software updates.
