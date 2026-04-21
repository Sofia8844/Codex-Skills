# Switching Selection

## Proposito

Usar este documento para explicar la seleccion de switches de acceso a partir de puertos, PoE y redundancia ya dimensionados.

## Puertos Y PoE

El motor debe dividir los puertos requeridos entre la cantidad de switches recomendada por el diseno tecnico y escoger un modelo con capacidad igual o superior. Si se requiere PoE, el producto debe declarar `poe` y `poe_ports` suficientes.

## Redundancia

Cuando la redundancia efectiva sea `high` o `mission_critical`, se debe preferir switches stackables o con mecanismos equivalentes. Si no existe candidato stackable, reportar advertencia.

## Uplinks

Los transceivers o cables asociados deben agregarse si el catalogo los marca como requeridos por uplink o stacking. En cotizaciones preliminares se puede usar una regla base de dos uplinks por switch, dejando claro que el detalle final depende del diseno de fibra/cobre.

## Gama Enterprise

La gama enterprise se justifica cuando hay alta densidad, uplinks de 10G, distribucion L3, alta disponibilidad o crecimiento esperado.
