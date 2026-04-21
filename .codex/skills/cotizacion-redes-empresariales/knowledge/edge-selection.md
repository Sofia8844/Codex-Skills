# Edge Selection

## Proposito

Usar este documento para explicar la seleccion de firewall, router o edge device despues de que el diseno tecnico entrega tier y throughput requerido.

## Throughput

El producto seleccionado debe tener `throughput_mbps` igual o superior al `estimated_required_throughput_mbps`. Si el catalogo no diferencia throughput firewall, threat y VPN, aclarar que la cifra es preliminar y debe validarse en datasheet.

## Categoria

`branch_router_firewall` corresponde a sucursales pequenas o bajo trafico. `business_router_firewall` corresponde a sedes medianas con seguridad perimetral. `enterprise_utm_firewall` corresponde a sedes con inspeccion, HA y mayor throughput.

## Alta Disponibilidad

Para redundancia `high` o `mission_critical`, requerir `ha_capable` y cotizar al menos dos unidades salvo que el diseno tecnico indique una arquitectura distinta.

## Licencias

Separar hardware de suscripciones de seguridad. Una estimacion que omite licencias de threat, malware, URL filtering o cloud management puede subestimar significativamente el costo.
