# Wireless Product Selection

## Proposito

Usar este documento para justificar la seleccion de access points despues de que el skill tecnico ya definio la cantidad de APs.

## Criterios

Seleccionar APs por entorno, estandar Wi-Fi, modelo de gestion, presupuesto y compatibilidad de licenciamiento. No recalcular cantidad de APs desde este skill.

## Entornos

Para `small_office`, un AP Wi-Fi 6 de gama media suele ser suficiente si la densidad es moderada. Para `corporate` o `mixed`, priorizar equipos con gestion centralizada y soporte contractual. Para `high_density`, preferir APs con mayor capacidad, uplinks multigigabit o Wi-Fi 6E si el presupuesto lo permite.

## Compatibilidad

No mezclar familias cloud y controller-managed sin una decision explicita. Si se selecciona Meraki, incluir licencia cloud. Si se selecciona Catalyst, incluir licencia DNA u otra licencia asociada del catalogo.

## Accesorios

Los brackets o kits de montaje deben considerarse cuando el catalogo los marque como requeridos. Inyectores PoE solo deben agregarse si no existe switching PoE suficiente o si el diseno lo solicita.
