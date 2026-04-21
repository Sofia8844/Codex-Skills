# Vendor Guidance

## Proposito

Usar este documento para explicar criterios comerciales y de familia. No usarlo como fuente de precio, SKU ni compatibilidad operativa; esos datos viven en `catalog/`.

## Lineas SMB vs Enterprise

Una linea SMB o branch suele ser adecuada cuando el sitio tiene bajo numero de usuarios, menor criticidad, administracion simple y presupuesto restringido. Una linea enterprise se justifica cuando hay alta densidad, multiples VLANs, necesidad de HA, soporte avanzado, stacking, QoS estricto, seguridad inspeccionada o integracion con plataformas corporativas.

## Preferencia De Fabricante

La preferencia de fabricante debe tratarse como criterio comercial, no como permiso para incumplir capacidad tecnica. Si el fabricante preferido no tiene un producto activo que cumpla, se debe explicar la brecha y presentar la alternativa activa de mayor ajuste.

## Cisco Catalyst Y Meraki

Catalyst tiende a ser mejor ajuste cuando la organizacion requiere control detallado, integracion con LAN enterprise, stacking, uplinks flexibles o operacion con controladora. Meraki tiende a ser mejor ajuste cuando el cliente prioriza gestion cloud, despliegue rapido y operaciones centralizadas con menor carga administrativa.

## Presupuesto

Cuando el presupuesto es inferior al subtotal, no reducir cantidades tecnicas del dimensionamiento previo. La respuesta debe sugerir fases, por ejemplo: fase 1 edge y switching critico, fase 2 WLAN completa, fase 3 soporte avanzado o licencias superiores.
