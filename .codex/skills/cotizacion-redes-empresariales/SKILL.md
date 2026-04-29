---
name: cotizacion-redes-empresariales
description: Convertir salidas tecnicas de diseno o dimensionamiento de redes empresariales en cotizaciones preliminares con productos, SKUs, licencias, soporte, accesorios, bundles, reglas de compatibilidad, catalogos JSON y motor deterministico. debe aterrizar cantidades tecnicas de APs, switches, firewalls, PoE, throughput, redundancia o VLANs a una recomendacion comercial explicable por fabricante.
---

# Cotizacion Redes Empresariales

## Principio

Actuar como especialista de preventa tecnica. Tomar una salida tecnica previa de red y convertirla en una estimacion de productos, SKUs, costos y dependencias comerciales.

Este skill queda desacoplado del skill tecnico. Solo consume el contrato compartido definido en:

- `.codex/contracts/network-design-to-quote/CONTRACT.md`
- `.codex/contracts/network-design-to-quote/handoff.schema.json`

No debe depender de reglas ni estructuras internas de `diseno-redes-empresariales`.

## Entrada Aceptada

Puede consumir:

- el objeto directo `quote_ready_input`
- un wrapper `quote_ready_input`
- un wrapper `handoff.quote_ready_input`

Entrada esperada:

```json
{
  "handoff": {
    "contract_version": "1.0",
    "source_skill": "diseno-redes-empresariales",
    "target_skill": "cotizacion-redes-empresariales",
    "quote_ready_input": {
      "site_name": "Sede Norte",
      "manufacturer_preference": "Cisco",
      "budget_level": "medium",
      "budget_usd": 25000,
      "technical_design": {
        "recommended_access_points": 6,
        "recommended_access_switches": 2,
        "required_switch_ports_with_reserve": 72,
        "required_poe_ports_with_reserve": 40,
        "effective_redundancy_level": "high",
        "edge_category": "business_router_firewall",
        "edge_router_firewall_count": 2,
        "estimated_required_throughput_mbps": 850,
        "environment": "corporate"
      },
      "needs": {
        "wireless": true,
        "switching": true,
        "edge": true,
        "support": true
      }
    }
  }
}
```

## Campos Esperados

Requeridos segun alcance:

- `site_name`
- `technical_design.recommended_access_points` si `needs.wireless = true`
- `technical_design.recommended_access_switches` si `needs.switching = true`
- `technical_design.required_switch_ports_with_reserve` si `needs.switching = true`
- `technical_design.required_poe_ports_with_reserve` si `needs.switching = true`
- `technical_design.edge_category` si `needs.edge = true`
- `technical_design.estimated_required_throughput_mbps` si `needs.edge = true`

Opcionales pero recomendados:

- `manufacturer_preference`
- `budget_level`
- `budget_usd`
- `technical_design.effective_redundancy_level`
- `technical_design.edge_router_firewall_count`
- `technical_design.environment`
- `needs.support`

## Que Puede Inferir

Permitido inferir solo cuando el contrato no lo trae y el fallback esta controlado:

- `technical_design.edge_router_firewall_count`
  - fallback a `2` si la redundancia es `high` o `mission_critical`
  - fallback a `1` en otros casos
- seleccion vendor-neutral
  - si no hay `manufacturer_preference`, elegir la opcion activa mas economica que cumpla reglas

## Que No Debe Inventar

- cantidades tecnicas principales de APs
- cantidades tecnicas principales de switches
- puertos requeridos
- throughput requerido
- categoria edge
- preferencia unica de fabricante si el contrato no la define

Si un campo requerido falta para el alcance activo, debe devolver `needs_input` y reportarlo claramente.

## Flujo

1. Extraer o validar entrada estructurada a partir del contrato compartido.
2. Preservar las cantidades tecnicas provenientes del skill previo.
3. Definir la carpeta de trabajo del caso. Por defecto debe ser `analysis_output/<site_name_slug>/`. Usar esa misma carpeta para el Markdown, el JSON de salida y el PDF.
4. Ejecutar el motor para obtener la seleccion comercial deterministica:

```bash
python .codex/skills/cotizacion-redes-empresariales/src/quote_engine.py --input path/to/input.json --pretty
```

5. Revisar la salida: `selected_products`, `related_items`, `discarded_products`, `applied_rules`, `warnings`, `constraints`, `missing_information` y `estimated_total`.
6. Leer solo los documentos de `knowledge/` que correspondan.
7. Redactar la explicacion comercial final visible sin inventar SKUs, precios ni compatibilidades fuera del catalogo.
8. Antes de ejecutar `export_quote_outputs.py`, guardar esa explicacion final visible en:

```text
analysis_output/<site_name_slug>/network_quote_explanation.md
```

9. Exportar JSON y PDF. El exportador vuelve a ejecutar el motor, detecta `network_quote_explanation.md` en la carpeta del caso y genera el PDF desde ese mismo texto:

```bash
python .codex/skills/cotizacion-redes-empresariales/src/export_quote_outputs.py --input path/to/input.json --output-dir analysis_output/<site_name_slug> --pretty
```

Si ya existe una explicacion final visible en Markdown y se quiere forzar una ruta concreta, el exportador tambien acepta:

```bash
python .codex/skills/cotizacion-redes-empresariales/src/export_quote_outputs.py --input path/to/input.json --output-dir analysis_output/<site_name_slug> --explanation-file path/to/network_quote_explanation.md --pretty
```

## Comportamiento Del Exportador

Cuando se ejecuta `export_quote_outputs.py`, su comportamiento tecnico es este:

1. Carga el input estructurado.
2. Llama internamente a `quote_engine.py`.
3. Construye el JSON final de salida desde el resultado comercial.
4. Busca `network_quote_explanation.md` en la carpeta del caso o usa el archivo indicado por `--explanation-file`.
5. Si encuentra Markdown, genera el PDF desde ese texto visible.
6. Si no encuentra Markdown, genera un Markdown y un PDF usando la explicacion base del motor como fallback.
7. Genera:
   - `network_quote_output.json`
   - `network_quote_explanation.md`
   - `network_quote_explanation.pdf`

Importante:

- `quote_engine.py` por si solo sirve para revisar la seleccion comercial en consola.
- `export_quote_outputs.py` es el script principal para producir archivos reales.
- En el flujo de Codex, la explicacion final rica debe guardarse antes de ejecutar el exportador.
- Si se ejecuta el exportador sin Markdown previo, el PDF usara el fallback deterministico y no la explicacion inteligente de Codex.

## Archivos De Salida

Por defecto, los artefactos se generan en `analysis_output/<site_name>/`.
Si se pasa `--output-dir`, se respeta esa ruta explicita.

Nombres estables y predecibles:

- `network_quote_output.json`
- `network_quote_explanation.md`
- `network_quote_explanation.pdf`

Si existe `network_quote_explanation.md`, el PDF debe generarse desde ese mismo texto visible.

## Manejo De Ambiguedad

- Si falta una cantidad tecnica principal, devolver `needs_input` y listar `missing_information`.
- Si falta fabricante, cotizar vendor-neutral y declarar el supuesto.
- Si la preferencia de fabricante no tiene candidato valido, proponer alternativa activa y marcar advertencia.
- Si el presupuesto no alcanza, no reducir cantidades tecnicas; reportar conflicto y sugerir fases.
- Si un producto esta EOL/EOS, no cotizarlo como seleccionado; usar `replacement_sku` si existe.

## Recursos

- `src/quote_engine.py`: motor deterministico de seleccion y costo.
- `src/export_quote_outputs.py`: exporta JSON y PDF.
- `rules/quote_rules.json`: reglas auditables de cotizacion.
- `catalog/`: catalogo JSON migrable a tablas.
- `knowledge/`: base documental para RAG.
- `examples/`: entradas y salidas de referencia.
- `output/`: artefactos generados por el skill.
