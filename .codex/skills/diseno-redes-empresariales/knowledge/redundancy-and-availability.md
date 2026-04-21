# Redundancy And Availability

Use this reference when explaining failover, HA and service continuity.

## Levels

- `false`: single edge, single WAN and no HA. Appropriate only when downtime is acceptable.
- `basic`: dual ISP or WAN failover. Protects against provider outage but not edge hardware failure.
- `high`: HA edge pair, dual WAN, stacked/MLAG switching where practical and redundant core/distribution for multi-floor sites.
- `mission_critical`: high availability plus diverse paths, stronger monitoring, documented failover testing and spare capacity.

## Design criteria

- Voice, video, POS, OT and security systems raise the minimum availability target.
- Redundant hardware is useful only when cabling, power, uplinks and ISP paths do not share the same single failure point.
- For multi-floor buildings, avoid a single access switch or single uplink becoming the outage point for the whole site.
- Use monitoring for WAN status, AP health, switch uplinks, DHCP/DNS reachability and critical VLAN gateways.

## Budget handling

When budget is low but redundancy is required:

1. Keep segmentation and correct cabling in phase 1.
2. Deploy a primary edge sized for the final load.
3. Add second WAN first if provider outages are likely.
4. Add HA edge and redundant core/distribution in the next phase.
5. Document residual risk until the final phase is funded.
