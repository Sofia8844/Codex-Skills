---
name: creacion-propuesta
description: Cree o complete propuestas económicas basadas en diapositivas a partir de una plantilla fija de PowerPoint corporativa, además de datos del cliente, precios, archivos PDF locales, archivos de referencia y logotipos proporcionados por el usuario. Úselo cuando Codex necesite personalizar una propuesta base que ya contenga información de la empresa, reemplazando solo los campos de cliente y comerciales, extrayendo el contexto del producto o servicio de los archivos PDF almacenados en la skill, agregando diapositivas de productos opcionales a partir de documentos o imágenes de respaldo y generando una salida PPTX desde el propio generador de la skill cuando sea necesario.
---

# Creacion Propuesta

## Objetivo

- Trabajar sobre una propuesta economica en formato presentacion.
- Tratar la base corporativa como un activo protegido: la informacion de la empresa ya viene incluida y no debe reescribirse salvo instruccion explicita.
- Personalizar la propuesta con datos del cliente, del proyecto y de la oferta economica.
- Permitir la adicion de diapositivas extra cuando el usuario pida incluir informacion de producto sustentada en PDFs, documentos de referencia o imagenes.

## Usar

- Activar este skill cuando el usuario pida crear, completar o ajustar una propuesta economica, propuesta comercial, oferta, cotizacion o alcance con precios en formato PowerPoint o esquema slide por slide.
- Tratar `./assets/plantillas/propuesta-economica-base.md` como mapa de contenido y placeholders de la propuesta.
- Leer `./references/presentacion-base-ariova.md` cuando la base viva sea la presentacion inspeccionada de Ariova o una presentacion con estructura equivalente.
- Leer `./references/perfil-empresa-base.md` solo para confirmar informacion institucional, no para reescribir la narrativa corporativa ya presente en la presentacion base.
- Aceptar informacion adicional escrita en el prompt, en PDFs, en documentos de referencia o en archivos cargados por el usuario.
- Cuando el usuario pida informacion de producto, capacidades, beneficios, caracteristicas, diferenciales, arquitectura o casos de uso, consultar `./scripts/pdf_reader.py` sobre los PDFs locales del skill antes de responder o redactar slides nuevas.
- Incorporar logos que vengan en los archivos del usuario o en `./assets/logos/` cuando el usuario pida agregarlos.
- Si el usuario no define formato de salida, entregar primero un esquema editable y luego materializar el `.pptx` si hay plantilla PowerPoint disponible.

## Base obligatoria

- Preferir una plantilla PowerPoint real cuando exista.
- Usar `./assets/plantillas/Industrias Ariova.pptx` como plantilla PowerPoint oficial por defecto.
- Si la skill dispone de una plantilla `.pptx` propia, usarla como base fija.
- Si no existe una plantilla `.pptx` dentro de la skill, usar la presentacion proporcionada por el usuario para esa solicitud y conservarla como plantilla viva solo para esa ejecucion.
- Usar `./assets/plantillas/propuesta-economica-base.md` como guia de contenido, no como sustituto visual del PowerPoint.

## Contenido protegido

- No reemplazar por defecto:
  - descripcion de la empresa
  - historia corporativa
  - equipo propio
  - claims institucionales
  - logos corporativos existentes
  - identidad visual, colores, tipografia, diagramacion y fondos
- No cambiar informacion institucional ni textos de posicionamiento de la empresa salvo que el usuario lo solicite de forma explicita.
- Mantener intactas las diapositivas corporativas como "Sobre Nosotros", equipo y cierres institucionales, salvo ajuste puntual pedido por el usuario.

## Contenido editable

- El usuario si puede reemplazar o completar:
  - nombre del cliente
  - nombre del proyecto
  - contexto del cliente
  - objetivos del proyecto
  - resumen ejecutivo orientado al cliente
  - solucion propuesta para el cliente
  - alcance y metodologia
  - cronograma
  - valores economicos
  - forma de pago
  - condiciones comerciales
  - equipo del proyecto cuando el usuario lo pida de forma explicita
  - logos del cliente o de aliados si el usuario los solicita
- Al actualizar montos o condiciones, mantener consistencia entre subtotal, total, impuestos, forma de pago y notas comerciales.
- No tratar los placeholders numerados del mapa Markdown como un limite funcional absoluto; son la capacidad visible del layout base.
- Si el usuario entrega mas condiciones, formas de pago o bullets de los que caben en una slide:
  - condensar y agrupar cuando siga siendo legible
  - si no caben, continuar en una slide adicional reutilizada o duplicada desde la plantilla oficial

## Flujo principal

- Inspeccionar primero la presentacion base para identificar que diapositivas son corporativas, cuales son comerciales y cuales sirven como reserva para contenido extra.
- Completar primero los campos editables obligatorios: cliente, proyecto, contexto, objetivo, solucion, cronograma, costos y condiciones.
- Enriquecer la propuesta con informacion relevante encontrada en PDFs y archivos de referencia, sin inventar datos.
- Si la consulta menciona productos, soluciones o servicios, correr primero una busqueda local en PDFs con `./scripts/pdf_reader.py search --query "<consulta>"` para ubicar paginas y snippets relevantes antes de sintetizar.
- Resumir los documentos de apoyo en lenguaje comercial claro en vez de pegar texto completo.
- Si el usuario pide "agregar informacion del producto", convertir los hallazgos del documento en una o mas diapositivas concretas con titulo, beneficios, diferenciadores, casos de uso y, si aplica, una imagen.
- Si hay varios logos, priorizar asi:
  - logo principal de la empresa
  - logo del cliente si el usuario lo solicita
  - logos de aliados, certificaciones o fabricantes en una banda secundaria o en anexos
- Mantener la propuesta coherente: problema, solucion, entregables, inversion, tiempos y cierre.

## Control de overflow

- Nunca insertar texto sin validar primero la capacidad visual del shape o placeholder.
- Respetar siempre el ancho, alto, margenes internos, alineacion y estructura del contenedor original.
- No permitir texto fuera del shape.
- No permitir texto cortado.
- No truncar frases ni usar `...` como solucion de overflow.
- No permitir superposicion sobre otros textos, imagenes o elementos graficos.
- Dentro de una misma diapositiva, los bloques equivalentes deben conservar un tamano de texto uniforme.
- No ajustar el tamano de fuente de una columna o bloque de forma aislada si pertenece al mismo grupo visual que otros.
- Si el contenido no cabe, priorizar este orden:
  - resumir
  - compactar bullets
  - reducir cantidad de texto por diapositiva
  - reutilizar o duplicar una slide de continuidad
- Mantener legibilidad por encima de exhaustividad.
- No intentar forzar texto completo dentro de un contenedor pequeno solo porque existe un placeholder.
- Cuando una seccion tenga mucho contenido, repartirlo entre varias diapositivas antes de deteriorar la plantilla.

## Limites de contenido por placeholder

- Titulo: corto, idealmente una linea; permitir hasta dos solo si el layout lo soporta.
- Subtitulo o encabezado secundario: version breve, sin frases largas.
- Bullets: preferir 4 a 6 como maximo segun la plantilla; cada bullet debe ser compacto, claro, completo y con tono profesional.
- Bullets de propuesta economica: apuntar a 10-18 palabras por bullet cuando el layout lo permita.
- Evitar bullets tipo keyword o frases excesivamente cortas; siempre dar suficiente contexto para que la idea se entienda sola.
- Parrafos: resumidos y orientados a idea principal, no bloques extensos.
- Formas de pago y condiciones: condensar cada punto en una frase corta y accionable.
- Si el placeholder ya viene con pocos renglones visibles en la plantilla, asumir que esa es la capacidad real aunque el prompt traiga mas informacion.
- Si varias columnas o listas son equivalentes, usar el mismo tamano efectivo de fuente entre ellas.
- Si un bullet o parrafo excede la capacidad del contenedor, reescribirlo como una idea mas breve sin perder el significado original.
- Mantener frases completas y profesionales; permitir quiebres de linea dentro del mismo shape antes de degradar la redaccion.
- No cortar bullets en conectores como `con`, `para`, `mediante`, `durante` o equivalentes.
- Si una lista no cabe con bullets completos, reducir cantidad de bullets antes de degradarlos a frases demasiado cortas.

## Manejo de titulos

- Identificar siempre el `title-primary` de la diapositiva antes de reemplazar el titulo.
- Insertar todo el titulo unicamente en ese shape principal.
- No dividir un mismo titulo entre multiples shapes.
- No mover partes del titulo a placeholders secundarios, decorativos o de apoyo.
- Mantener el tamano base, la posicion, la alineacion y la jerarquia visual del titulo segun la plantilla original.
- Si el titulo es largo:
  - permitir quiebre de linea dentro del mismo shape
  - resumir antes de reducir demasiado la fuente
  - nunca repartir el texto en otros contenedores
- Si una diapositiva tiene varios shapes de estilo titulo, tratar solo uno como `title-primary` y dejar los demas intactos salvo instruccion explicita.

## Prioridad de fuentes

- Dar prioridad a instrucciones explicitas del usuario sobre cualquier archivo.
- Usar la presentacion base como estructura visual y como fuente protegida de contenido corporativo.
- Usar el mapa Markdown de la plantilla como esquema de placeholders y validacion del contenido esperado.
- Usar el perfil de empresa por defecto solo para rellenar informacion institucional faltante, no para sobreescribir contenido corporativo ya aprobado.
- Usar PDFs y documentos de referencia para reforzar descripcion, alcance, beneficios, credenciales, metodologia, anexos y slides nuevas de producto.
- Priorizar siempre lo encontrado en los PDFs locales del skill sobre conocimiento generico del modelo cuando el usuario pida detalles de productos o servicios.
- Si dos fuentes se contradicen, mencionar la inconsistencia y preferir la mas reciente o la que el usuario indique.

## Lectura local de PDFs

- Usar `./scripts/pdf_reader.py` como lector local de PDFs del skill.
- Buscar primero en `./assets/Informacion/` y aceptar tambien `./assets/informacion/` si esa carpeta existe.
- El lector recorre recursivamente esa carpeta, asi que puede tomar PDFs dentro de subcarpetas con cualquier nombre.
- Usar `search` cuando el usuario pida hallar contenido relevante dentro de brochures, fichas, reportes o anexos PDF.
- Usar `extract` cuando haga falta revisar el texto completo de un documento antes de convertirlo en contenido comercial.
- Priorizar la salida de `search` como punto de partida: tomar archivo, pagina y snippet para fundamentar la respuesta o la slide que se va a redactar.
- Si el usuario ya menciona un documento concreto, filtrar con `--file "<nombre.pdf>"` para evitar ruido de otros PDFs.
- Comandos de referencia:
  - `python ./.codex/skills/creacion-propuesta/scripts/pdf_reader.py list --pretty`
  - `python ./.codex/skills/creacion-propuesta/scripts/pdf_reader.py search --query "managed network services" --pretty`
  - `python ./.codex/skills/creacion-propuesta/scripts/pdf_reader.py search --file "Critical_Capabilitie_806273_ndx.pdf" --query "benefits" --pretty`
  - `python ./.codex/skills/creacion-propuesta/scripts/pdf_reader.py extract --file "Critical_Capabilitie_806273_ndx.pdf" --pretty`
- El script intenta usar `pypdf` como backend principal.
- Si `pypdf` no esta disponible, el script usa un parser local de respaldo sin descargas ni APIs externas.
- No instalar dependencias en tiempo de ejecucion.
- Si la busqueda no devuelve evidencia suficiente, decirlo de forma explicita y no inventar caracteristicas, beneficios ni cifras.
- Al transformar hallazgos del PDF en slides o narrativa comercial:
  - sintetizar el contenido
  - conservar el sentido tecnico
  - no copiar bloques extensos de texto literal
  - mencionar cuando algo provenga de un PDF o brochure especifico

## Diapositivas adicionales de producto

- Permitir diapositivas nuevas o reutilizadas cuando el usuario pida incluir informacion de productos, capacidades, comparativos, tendencias o beneficios.
- Usar como fuente documentos tipo fichas tecnicas, brochures, PDFs de fabricantes, reportes de analistas, comparativos o imagenes provistas por el usuario.
- Convertir cada bloque de informacion adicional en una slide con un objetivo claro. Ejemplos:
  - resumen del producto
  - capacidades clave
  - arquitectura o componentes
  - beneficios para el cliente
  - comparativo o diferenciadores
  - estadisticas o tendencias de mercado
- Si un documento incluye imagenes utiles, incorporarlas solo si ayudan a explicar el producto y no rompen la composicion.
- No llenar la presentacion con texto copiado; sintetizar y adaptar el contenido al tono comercial de la propuesta.
- Actualizar la agenda cuando se agreguen secciones nuevas a la presentacion.

## Manejo de logos

- Buscar logos en este orden:
  - archivos adjuntos por el usuario para la solicitud actual
  - logos existentes en `./assets/logos/base/`
  - logos existentes en `./assets/logos/adicionales/`
- Intentar resolver el logo del cliente por coincidencia de nombre de empresa con el nombre del archivo.
- Normalizar para buscar coincidencias:
  - ignorar mayusculas y minusculas
  - tratar espacios, guiones y guion bajo como equivalentes
  - ignorar tildes cuando sea posible
- Ejemplo: si el usuario dice que la propuesta es para "Caja Social" y existe `./assets/logos/adicionales/caja-social.png`, usar ese archivo como logo del cliente por defecto.
- No deformar proporciones ni mezclar demasiados logos en portada si eso rompe la jerarquia visual.
- Si un PDF contiene un logo util pero no un archivo separado, extraer la referencia visual solo si el flujo de trabajo disponible lo permite; si no, mencionar que se detecto el logo y dejar el marcador listo para reemplazo.
- Si no hay logos disponibles, dejar un marcador claro en la plantilla en vez de inventar una imagen.
- Si se detecta un logo del cliente y el usuario no indica otra ubicacion, colocarlo por defecto en la zona central de las diapositivas 4 y 7.
- Si solo debe aparecer una vez, priorizar la diapositiva 4.
- Si hay conflicto entre logo del cliente y elementos graficos existentes, mantener la composicion de la plantilla y ajustar tamano antes que moverlo a otra zona.
- Cuando la plantilla ya traiga una imagen o icono en la posicion objetivo, no insertar el logo con geometria generica:
  - reutilizar la caja o contenedor visual ya existente
  - mantener posicion, tamano y alineacion del elemento original
  - ajustar el logo con proporcion contenida dentro de esa caja para evitar deformaciones
- Reglas especificas para la plantilla Ariova:
  - slide 1: sustituir el icono o imagen inferior usando el contenedor inferior existente
  - slide 4: reemplazar la imagen ubicada en el centro del circulo usando la geometria del objetivo existente
  - slide 7: eliminar la imagen actual del centro del circulo y reemplazarla por el logo solicitado, centrado dentro del mismo contenedor
- Si no se encuentra la imagen objetivo en un slide, continuar con el resto de la construccion sin fallar toda la propuesta.

## Builder propio

- Usar `./build_presentation.py` como builder propio del skill cuando la salida final deba ser un `.pptx`.
- Pasar por defecto `./assets/plantillas/Industrias Ariova.pptx` como template cuando el usuario no entregue otra plantilla para esa solicitud.
- Dejar siempre la salida final dentro de `./output/`, aunque el spec proponga otra ruta fuera de esa carpeta.
- Para solicitudes normales, construir con un spec transitorio enviado por `stdin` usando `build --spec -`.
- No guardar archivos auxiliares por solicitud en `./output/`, como `spec.json`, notas Markdown o trazas, salvo que el usuario los pida de forma explicita para auditoria, depuracion o reutilizacion.
- Si por alguna razon excepcional se materializa un spec transitorio en disco, eliminarlo al final de la ejecucion y no dejarlo como parte del entregable.
- Usar `slide_images` en el spec cuando haya que insertar logos o imagenes reales dentro de la presentacion final.
- Usar `team_section` solo cuando haya que agregar integrantes nuevos del proyecto sin tocar el equipo corporativo ya presente en la plantilla.
- Para slides con imagen previa en la plantilla, preferir `slide_images` con reemplazo sobre objetivo existente en vez de insercion centrada generica.
- Selectores recomendados para esta plantilla:
  - slide 1: `target_existing: "bottom-center"`
  - slides 4 y 7: `target_existing: "center"`
- Cuando se use un objetivo existente:
  - activar `use_target_geometry: true` para conservar la caja original
  - activar `remove_target_image: true` para quitar la imagen previa antes de insertar el logo
  - activar `missing_ok: true` para no fallar si el elemento no aparece en esa plantilla
- Para la seccion de equipo:
  - usar `team_section.template_slide` para indicar la slide base, normalmente la 11 en Ariova
  - dejar intactos los empleados que ya existen en la slide base
  - conservar por defecto el titulo original de la slide base en las slides clonadas
  - enviar `team_section.members` como lista de integrantes nuevos con `name`, `role` y opcionalmente `image_path`
  - usar `./assets/Equipo/` o `./assets/equipo/` solo como fuente de fotos para esos integrantes nuevos
  - prioridad de imagen: `image_path` del usuario, luego coincidencia por nombre en `Equipo`, y si no existe usar `Empleado Default`
  - el builder reutiliza la tarjeta original del template en slides clonadas, mantiene la mascara de la foto y crea slides adicionales si hay mas de cuatro personas nuevas
  - si realmente se quiere cambiar ese titulo, enviar `team_section.title` junto con `team_section.replace_title: true`
- Usar `inspect` para mapear texto editable por slide antes de construir el reemplazo.
- Leer la salida de `inspect` y usar el shape marcado como `title-primary` para cualquier titulo principal de la diapositiva.
- Usar `build` con un `spec` transitorio para reemplazar textos y reordenar diapositivas.
- Confiar en el control interno de overflow del builder para:
  - medir la caja util del shape
  - resumir semanticamente el contenido si excede el contenedor
  - mantener bullets con redaccion consultiva y suficiente contexto
  - mantener tamano uniforme entre shapes equivalentes de la misma diapositiva
  - bajar fuente solo de manera uniforme por grupo equivalente cuando haga falta
  - conservar el texto dentro del shape sin invadir otros elementos
- En titulos:
  - no repartir texto en varios shapes
  - no degradar el tamano del titulo por culpa de otros bloques de la diapositiva
  - preservar el contenedor principal del titulo como unica caja editable para ese texto
- Aun con ese control, preparar siempre una version breve del contenido antes de construir la diapositiva.
- Tener presente la limitacion actual del script:
  - si puede inspeccionar la plantilla
  - si puede reemplazar textos por shape
  - si puede reordenar slides existentes
  - puede duplicar slides existentes cuando el layout ya existe, por ejemplo para continuidad o para la seccion de equipo
  - no debe expandir una shape de texto mas alla de la capacidad visual que permite la plantilla
- Cuando el usuario pida "agregar mas diapositivas", resolver asi:
  - preferir slides de reserva ya existentes en la plantilla base
  - o usar otra plantilla que ya traiga layouts reutilizables
  - o extender el script despues, si realmente hace falta clonar slides
- Cuando un layout tenga capacidad fija, por ejemplo cuatro lineas de condiciones, no perder informacion:
  - resumir dentro de la capacidad visible del slide
  - o repartir el contenido en una slide de continuidad
- Comandos de referencia:
  - `python ./.codex/skills/creacion-propuesta/build_presentation.py inspect --template <plantilla.pptx>`
  - `python ./.codex/skills/creacion-propuesta/build_presentation.py build --spec <spec.json>`
  - `Get-Content <spec.json> | python ./.codex/skills/creacion-propuesta/build_presentation.py build --spec - --base-dir <repo>`
- Ejemplo conceptual para logos del cliente:
  - insertar `./assets/logos/adicionales/caja-social.png` en los slides 4 y 7 usando `slide_images`
  - reemplazar imagen previa en slide 1 usando `target_existing: "bottom-center"`
  - reemplazar imagen previa en slides 4 y 7 usando `target_existing: "center"`

## Contenido minimo esperado

- Portada
- Resumen ejecutivo
- Contexto o necesidad del cliente
- Alcance y entregables
- Metodologia o forma de trabajo
- Cronograma
- Inversion o propuesta economica
- Condiciones comerciales
- Cierre y siguientes pasos
- Anexos o referencias usadas

## Criterios

- No inventar cifras, certificaciones, logos, arquitecturas ni casos de exito.
- Mantener trazabilidad de que informacion vino del prompt, de la plantilla base y de archivos de referencia.
- Reescribir el contenido para que suene a propuesta profesional, no a notas internas ni a texto pegado desde el PDF.
- Mantener los placeholders cuando falten datos criticos.
- Si el usuario pide completar una descripcion con base en PDFs o anexos, sintetizar y aterrizar esa informacion dentro de la seccion correcta de la propuesta.
- Si el usuario pide detalles de un producto o servicio y no aparecen en los PDFs o documentos disponibles, indicarlo y pedir solo el dato faltante en vez de completarlo con suposiciones.
- Excluir slides de recursos o placeholders tecnicos de la plantilla antes de la entrega final.
- Si un bloque sigue sin caber correctamente despues de compactarlo, mover parte del contenido a otra slide en vez de romper el layout.

## Archivos de la skill

- Plantilla PowerPoint oficial por defecto: `./assets/plantillas/Industrias Ariova.pptx`
- Builder propio: `./build_presentation.py`
- Lector local de PDFs: `./scripts/pdf_reader.py`
- Plantilla base: `./assets/plantillas/propuesta-economica-base.md`
- Mapa de la presentacion base inspeccionada: `./references/presentacion-base-ariova.md`
- Perfil institucional por defecto: `./references/perfil-empresa-base.md`
- Carpeta de PDFs de producto: `./assets/Informacion/`
- Logos base: `./assets/logos/base/`
- Logos adicionales: `./assets/logos/adicionales/`

## Salida esperada

- Entregar una propuesta editable y ordenada.
- Entregar por defecto solo el `.pptx` final como artefacto persistente.
- Indicar que fuentes se usaron para completar la propuesta y cuales slides nuevas se agregaron o reutilizaron.
- Senalar claramente los campos pendientes cuando el usuario no haya dado suficiente informacion.
