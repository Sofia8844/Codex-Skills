# Propuesta economica base

Usar este archivo como guia de contenido para una presentacion base en PowerPoint. No es la plantilla visual final; es el mapa editable de la propuesta.

Plantilla PowerPoint oficial por defecto: `./assets/plantillas/Industrias Ariova.pptx`

## Reglas

- No reemplazar por defecto la informacion institucional de la empresa.
- Reemplazar principalmente informacion del cliente, del proyecto y de la propuesta economica.
- Si se agregan slides de producto, usar los layouts opcionales o slides de reserva de la plantilla PowerPoint.
- Mantener sincronizada la agenda con las secciones realmente incluidas.

## Slide 1. Portada

- Empresa: {{empresa_nombre}}
- Cliente: {{cliente_nombre}}
- Proyecto: {{proyecto_nombre}}
- Fecha: {{fecha}}
- Logo principal: {{logo_principal}}
- Logos adicionales: {{logos_adicionales}}

## Slide 2. Agenda

- {{agenda_1}}
- {{agenda_2}}
- {{agenda_3}}
- {{agenda_4}}
- {{agenda_5}}
- {{agenda_6}}
- {{agenda_7}}

## Slide 3. Resumen ejecutivo

{{resumen_ejecutivo}}

## Slide 4. Contexto y objetivos del cliente

- Contexto: {{contexto_cliente}}
- Objetivos: {{objetivos_cliente}}
- Logo del cliente en zona central: {{logo_cliente_slide_4}}

## Slide 5. Propuesta de solucion

{{propuesta_solucion}}

## Slide 6. Alcance y metodologia

- Alcance: {{alcance}}
- Metodologia: {{metodologia}}
- No incluido: {{no_incluye}}

## Slide 7. Arquitectura o componentes

{{arquitectura_componentes}}

- Logo del cliente en zona central: {{logo_cliente_slide_7}}

## Slide 8 y 9. Cronograma y equipo del proyecto

- Fase 1: {{fase_1}} - {{fase_1_fecha}}
- Fase 2: {{fase_2}} - {{fase_2_fecha}}
- Fase 3: {{fase_3}} - {{fase_3_fecha}}
- Fase 4: {{fase_4}} - {{fase_4_fecha}}
- Duracion total: {{duracion_total}}

## Slide 10. Sobre nosotros

Contenido corporativo protegido. No editar salvo instruccion explicita.

## Slide 11. Equipo

Contenido corporativo protegido por defecto. Si el usuario pide actualizarlo:

- mantener intactos los empleados ya presentes en la plantilla
- reutilizar las tarjetas existentes como base visual para integrantes nuevos en slides duplicadas
- poblar `name` y `role` solo para los integrantes nuevos pedidos por el usuario
- buscar fotos locales del equipo en `./assets/Equipo/` solo para esos integrantes nuevos
- si no existe una foto por nombre, usar `Empleado Default`
- crear una slide adicional por cada bloque de hasta cuatro integrantes nuevos

## Slide 12. Propuesta economica y condiciones

### Valores

- Concepto 1: {{concepto_1}}
- Valor 1: {{concepto_1_valor}}
- Concepto 2: {{concepto_2}}
- Valor 2: {{concepto_2_valor}}
- Concepto 3: {{concepto_3}}
- Valor 3: {{concepto_3_valor}}
- Concepto 4: {{concepto_4}}
- Valor 4: {{concepto_4_valor}}
- Total propuesta: {{total_propuesta}}
- Impuestos: {{impuestos}}

### Forma de pago

- {{forma_pago_1}}
- {{forma_pago_2}}
- {{forma_pago_3}}
- {{forma_pago_4}}

### Condiciones

Estas lineas representan la capacidad visible del slide base para condiciones comerciales.

- {{condicion_1}}
- {{condicion_2}}
- {{condicion_3}}
- {{condicion_4}}

Si existen mas condiciones:

- agruparlas o resumirlas dentro de estas cuatro lineas cuando siga siendo legible
- si no caben, mover el excedente a una slide de continuidad reutilizada o duplicada desde la plantilla oficial
- conservar el detalle completo en `{{condiciones_adicionales}}` cuando haga falta trazabilidad

## Slides opcionales para producto

Usar estas secciones cuando el usuario pida agregar informacion tomada de documentos, PDFs o imagenes de producto.

### Slide opcional A. Capacidades del producto

- Producto: {{producto_nombre}}
- Capacidades: {{producto_capacidades}}
- Beneficios: {{producto_beneficios}}

### Slide opcional B. Segmentos o casos de uso

- Segmentos: {{producto_segmentos}}
- Casos de uso: {{producto_casos_uso}}
- Diferenciadores: {{producto_diferenciadores}}

### Slide opcional C. Roadmap o cronologia extendida

- Hito 1: {{hito_1}}
- Hito 2: {{hito_2}}
- Hito 3: {{hito_3}}

### Slide opcional D. Comparativo o competencia

- Opcion 1: {{comparativo_1}}
- Opcion 2: {{comparativo_2}}
- Opcion 3: {{comparativo_3}}

### Slide opcional E. Estadisticas o mercado

- KPI principal: {{kpi_principal}}
- Dato 1: {{dato_1}}
- Dato 2: {{dato_2}}
- Fuente: {{fuente_datos}}

## Cierre y anexos

- Documentos usados: {{documentos_usados}}
- Imagenes usadas: {{imagenes_usadas}}
- Logos usados: {{logos_usados}}
- Notas pendientes: {{pendientes}}
