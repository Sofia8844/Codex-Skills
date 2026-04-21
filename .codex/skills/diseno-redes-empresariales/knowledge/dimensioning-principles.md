# Dimensioning Principles

Use these notes to explain the deterministic output. Do not replace script calculations with free-form estimates.

## Access points

- Size Wi-Fi by capacity and coverage. Use the larger result.
- Capacity depends on concurrent clients, airtime, application mix, radio design and channel width.
- Coverage depends on area, walls, shelving, metal, RF noise and roaming needs.
- High and critical traffic reduce acceptable clients per AP because contention, retransmissions and latency matter more than association count.
- Multi-floor sites need AP distribution by floor. A single AP count for the whole building is not enough.
- Industrial sites require site survey validation because metal, machinery, dust and moving inventory can invalidate generic coverage estimates.

## Edge router/firewall

- The edge device is not the same as Wi-Fi coverage. It terminates WAN, routing, firewall, VPN, NAT and security inspection.
- Select edge capacity by concurrent users, inspected throughput, VPN throughput and feature licenses.
- If high availability is required, count edge devices as an HA pair and include dual WAN when uptime matters.

## Throughput

- Estimate traffic from concurrent users, not only registered devices.
- Apply headroom for bursts, retransmissions, updates, cloud sync, encrypted inspection and future growth.
- Critical services need latency and jitter control, not only raw Mbps.

## Switching

- Switch sizing must include wired endpoints, AP uplinks, phones, cameras, IoT and spare ports.
- PoE sizing must include APs, phones, cameras and powered IoT. Validate PoE budget per switch, not just port count.
- A distribution or L3 core layer is recommended when there are multiple floors, multiple access switches or several VLANs.

## Budget

- Budget constraints should change phasing and equipment class, not silently remove required availability.
- If the budget cannot support HA, state the conflict and propose a minimum viable phase plus later redundancy.
