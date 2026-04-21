# Segmentation And Security

Use segmentation to reduce blast radius, protect critical traffic and simplify policy.

## Baseline VLANs

- `management`: network devices, controllers and admin access.
- `corporate`: managed laptops and trusted internal clients.
- `guest`: internet-only access with no east-west access to corporate resources.

## Conditional VLANs

- `iot`: sensors, smart devices and unmanaged endpoints.
- `voice`: IP phones and voice gateways. Apply QoS markings and call-control ACLs.
- `security`: cameras, NVRs and physical security devices.
- `services`: printers and shared office devices.
- `server`: local servers or on-prem application hosts.
- `ot`: industrial control, PLCs, SCADA or production systems.
- `business_critical`: ERP, POS or revenue-critical applications.

## Policy guidance

- Use default-deny inter-VLAN policy where possible.
- Allow only required flows from IoT/OT/security networks to controllers, NVRs, DNS, NTP, update services or application endpoints.
- Keep management access restricted to admin workstations or VPN.
- For guest Wi-Fi, use client isolation and internet-only ACLs.
- For voice/video, preserve DSCP markings where the switching and WLAN infrastructure supports it.
