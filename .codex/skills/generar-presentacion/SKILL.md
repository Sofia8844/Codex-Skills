---
name: generar-presentacion
description: Create presentations from a template and a source document while preserving colors, backgrounds, structure, and slide flow. Use when the user wants slides based on an uploaded template or base document, when one of those files is missing, or when the skill must decide between using the provided template, a default template, or asking for more input.
---

# Generar Presentacion

## Objetivo

- Crear una presentacion basada en una plantilla y un documento base.
- Respetar el sistema visual de la plantilla: colores, fondos, tipografia, espaciado y jerarquia.
- Mantener una narrativa clara de inicio, desarrollo y cierre.

## Decision de entrada

- Si hay plantilla y documento, generar la presentacion usando esa plantilla como base.
- Si solo hay plantilla, pedir el contenido faltante antes de continuar.
- Si solo hay documento, usar la plantilla fisica por defecto ubicada en `./assets/default-template.pptx` solo si ese archivo existe.
- Si no hay nada, pedir que suba archivos antes de seguir.
- Si no existe una plantilla fisica por defecto disponible, pedir al usuario que suba una antes de continuar.
- No guardar dentro de la skill la plantilla que suba el usuario; usarla solo como archivo de entrada para esa solicitud.

## Plantilla fisica por defecto

- La plantilla por defecto debe ser un archivo real, por ejemplo un `.pptx`.
- Guardar en `assets/` solo la plantilla por defecto propia de la skill, no las plantillas subidas por el usuario.
- Usar `./assets/default-template.pptx` como ruta por defecto.
- No asumir una plantilla solo a partir de reglas escritas si el objetivo es conservar diseno, fondos, placeholders o distribucion exacta.
- Si existe una plantilla fisica por defecto en la skill, usar siempre esa misma cuando el usuario no suba plantilla.
- Si no existe ese archivo, detener la generacion y pedir al usuario que suba una plantilla valida.

## Flujo de trabajo

- Inspeccionar primero la plantilla para extraer colores, fondos, estilos de titulo, espaciado y ritmo visual.
- Usar la informacion que el usuario suministre en el prompt o en archivos subidos como documento base.
- Si el usuario sube una plantilla nueva, usar esa plantilla solo para esa solicitud.
- Si el usuario no sube plantilla, usar `./assets/default-template.pptx`.
- Leer despues el documento base para identificar tesis, secciones, datos clave y cierre.
- Sintetizar el contenido en formato de slides, no copiarlo completo.
- Preferir el generador reutilizable `./build_presentation.py` para inspeccionar la plantilla y construir el `.pptx`.
- No modificar ejemplos existentes ni archivos de referencia de la skill, salvo que el usuario lo pida explicitamente.
- No dejar archivos intermedios persistentes para cada solicitud; el unico archivo final que debe quedar por defecto es la presentacion generada.
- Usar una estructura base:
  - Portada o apertura
  - Contexto o agenda
  - Desarrollo principal
  - Cierre o conclusiones
- Ajustar la densidad de texto para que cada diapositiva respire.
- Si la plantilla tiene lineamientos de marca, respetarlos por encima de preferencias genericas.

## Automatizacion recomendada

- Inspeccionar la plantilla:
  - `python ./.codex/skills/generar-presentacion/build_presentation.py inspect`
- Generar una presentacion desde especificacion persistida, si hace falta depurar o dejar un ejemplo:
  - `python ./.codex/skills/generar-presentacion/build_presentation.py build --spec <ruta-del-spec.json>`
- Generar una presentacion desde una especificacion transitoria, sin guardar JSON intermedio:
  - `python ./.codex/skills/generar-presentacion/build_presentation.py build --spec - --base-dir <ruta-base>`
- Si se usa una especificacion, debe contener:
  - `template_path`
  - `output_pptx`
  - `slide_order`
  - `slide_replacements`
- Puede incluir tambien:
  - `slide_images`
- Usar `notes_markdown` o `notes_markdown_path` solo cuando el usuario tambien necesite un archivo adicional con fuentes o notas.
- Si se necesita una copia adicional en otra ruta, usar `extra_output_paths`.
- `./ikusi-spec.json` es solo un ejemplo funcional de referencia, no el flujo normal para todas las presentaciones.
- `slide_images` permite insertar imagenes reales dentro del `.pptx` por numero de slide. Cada entrada puede usar:
  - una ruta simple de imagen, por ejemplo `"4": "./logo.png"`
  - o una lista de objetos con `image_path`, `placement`, `max_width`, `max_height`, `x`, `y`, `cx`, `cy`, `box`, `name`, `target_existing`, `use_target_geometry`, `remove_target_image` y `missing_ok`
- Si se usa `placement: "center"`, la imagen se centra automaticamente preservando proporcion.
- Si la plantilla ya trae una imagen o icono donde debe ir el nuevo logo, preferir `target_existing` para reutilizar la geometria del objetivo existente y evitar deformaciones.
- Selectores disponibles para `target_existing`:
  - `center`
  - `bottom-center`
- Cuando se use `target_existing`, normalmente conviene:
  - `use_target_geometry: true`
  - `remove_target_image: true`
  - `missing_ok: true`

## Criterios

- No inventar datos que no esten en el documento.
- No romper la composicion de la plantilla.
- No saturar las diapositivas con texto.
- Mantener coherencia visual entre apertura, cuerpo y cierre.

## Salida esperada

- Entregar la presentacion final o un esquema slide por slide listo para convertir.
- Incluir notas breves cuando ayuden a aplicar la plantilla correctamente.
