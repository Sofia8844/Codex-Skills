# Compatibility Guidelines

## Proposito

Usar este documento para explicar compatibilidad entre equipos, licencias, soporte, accesorios y bundles. La compatibilidad operativa vive en los campos `compatible_with` y `related` del catalogo.

## Relaciones

Cada producto base puede declarar:

- `licenses`: licencias obligatorias o recomendadas.
- `support`: soporte asociado.
- `accessories`: brackets, cables, transceivers u otros elementos.
- `bundles`: paquetes sugeridos.

Antes de agregar un item relacionado, validar que el SKU padre aparezca en `compatible_with` del item relacionado cuando ese campo exista.

## Bundles

Un bundle no debe ocultar el desglose por SKU. Usarlo como sugerencia comercial o descuento adicional cuando sus categorias requeridas esten cubiertas por la recomendacion.

## Reemplazos

Si un producto esta EOL/EOS, no debe seleccionarse directamente. Cuando `replacement_sku` exista, usarlo como alternativa. Cuando no exista, reportar la restriccion y seleccionar el candidato activo mas cercano.
