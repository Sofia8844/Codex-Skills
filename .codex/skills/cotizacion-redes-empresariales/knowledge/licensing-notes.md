# Licensing Notes

## Proposito

Usar estas notas para explicar por que se agregan licencias y soporte. Los SKUs y precios validos estan en `catalog/licenses.json` y `catalog/support.json`.

## Licencias Obligatorias

Muchos equipos empresariales requieren licencias para gestion, seguridad o funcionalidades avanzadas. En una cotizacion preliminar, una licencia marcada como obligatoria debe agregarse de forma explicita para evitar una estimacion artificialmente baja.

## Terminos

El catalogo inicial usa terminos de 36 meses para mantener comparabilidad. Si el usuario pide 12, 60 o 84 meses, el motor actual debe reportar que el catalogo necesita terminos adicionales o que se requiere cotizacion formal.

## Seguridad Perimetral

En firewalls, diferenciar hardware de servicios de seguridad. El hardware puede enrutar o filtrar de forma basica, pero las funciones de threat prevention, malware, URL filtering o gestion cloud suelen depender de suscripciones.

## Soporte

El soporte debe incluirse si el usuario lo pide o si el producto esta marcado como `requires_support`. Para ambientes criticos, soporte sin reemplazo agil o sin cobertura contractual debe tratarse como riesgo comercial.
