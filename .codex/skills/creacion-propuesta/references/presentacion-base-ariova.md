# Presentacion base Ariova

Usar esta referencia cuando la base de la propuesta sea la presentacion inspeccionada de Ariova o una plantilla muy parecida en estructura.

Plantilla PowerPoint oficial por defecto: `./assets/plantillas/Industrias Ariova.pptx`

## Regla principal

- La informacion de empresa ya existe en la presentacion base.
- No reescribir contenido corporativo salvo instruccion explicita.
- Personalizar sobre todo la informacion del cliente, el proyecto y los valores economicos.

## Slides observadas

- Slide 1: portada. Editable para cliente, proyecto y nombre de la propuesta.
  - Si se reemplaza el logo o icono inferior, reutilizar el contenedor existente en la parte baja de la slide.
- Slide 2: agenda. Actualizar si cambia el orden o se agregan secciones.
- Slide 3: resumen ejecutivo. Editable y orientado al cliente.
- Slide 4: contexto y objetivos del proyecto. Editable con informacion del cliente.
  - Ubicacion sugerida para logo del cliente: zona central del slide.
  - Si ya existe una imagen en el centro del circulo, reemplazarla usando la geometria del elemento actual.
- Slide 5: propuesta de solucion. Editable con la solucion concreta ofertada.
- Slide 6: alcance y metodologia. Editable.
- Slide 7: arquitectura tecnologica. Editable si depende de la solucion propuesta o de los productos.
  - Ubicacion sugerida para logo del cliente: zona central del slide.
  - Si existe una imagen en el centro del circulo, eliminar la anterior y centrar el nuevo logo dentro del mismo contenedor.
- Slide 8 y 9: cronograma y duracion. Editables.
- Slide 10: sobre nosotros. Proteger por defecto.
- Slide 11: equipo. Proteger por defecto salvo actualizacion solicitada.
  - Mantener intactos los empleados ya presentes en la plantilla base.
  - Si se agregan integrantes nuevos, hacerlo en slides duplicadas despues de la 11 usando las cuatro tarjetas existentes como layout base.
  - Usar `./assets/Equipo/` solo como fuente de fotos para integrantes nuevos.
  - Si no aparece foto por nombre, usar `Empleado Default`.
- Slide 12: propuesta economica y condiciones. Editable para valores, forma de pago y notas comerciales.
  - El layout observado tiene capacidad visible limitada:
    - bloque de propuesta economica con cinco lineas
    - bloque de forma de pago con cuatro lineas
    - bloque de condiciones con cuatro lineas
  - Si llega mas contenido que esa capacidad, resumir o continuar en otra slide.
- Slide 13: layout opcional para mision o narrativa de producto.
- Slide 14: layout opcional para publico objetivo, segmentos o beneficios.
- Slide 15: cierre. Mantener estilo institucional; ajustar solo si el usuario lo pide.
- Slide 16: layout opcional para cronologia o roadmap adicional.
- Slide 17: layout opcional para comparativos, competidores o diferenciadores.
- Slide 18: layout opcional para estadisticas, KPIs o cifras de mercado.
- Slide 19: layout opcional para otra narrativa de producto o capacidades.
- Slides 20, 21 y 22: paginas de recursos de la plantilla. No deben salir en la entrega final.

## Uso para informacion de producto

- Reutilizar slides 13, 14, 16, 17, 18 y 19 como banco de layouts para contenido extra.
- Usar PDFs y documentos de producto para poblar esas slides con:
  - capacidades clave
  - beneficios
  - componentes
  - casos de uso
  - tendencias
  - comparativos
- Los PDFs pueden vivir en `assets/Informacion/` o en cualquiera de sus subcarpetas; no necesitan nombres de carpeta especiales.
- No copiar parrafos largos desde los PDFs.
- Si un documento aporta una imagen util, agregarla solo si respeta la composicion general.

## Uso para logos del cliente

- Si el usuario nombra una empresa y existe un archivo de logo coincidente en `./assets/logos/adicionales/`, usarlo automaticamente.
- Coincidencias esperadas por nombre normalizado, por ejemplo:
  - `Caja Social` -> `caja-social.png`
- Ubicar por defecto el logo del cliente en la zona central de los slides 4 y 7, salvo que el usuario pida otra posicion.
- Mantener proporcion original y evitar que el logo tape texto o diagramas.
- Si la plantilla ya tiene una imagen o icono en la posicion objetivo, reutilizar su caja original antes que insertar un logo centrado de forma generica.
- Si no se encuentra el objetivo esperado, continuar sin lanzar error fatal.

## Script reutilizable

- Inspeccionar la plantilla:

```bash
python ./.codex/skills/creacion-propuesta/build_presentation.py inspect --template <plantilla.pptx>
```

- Construir la salida desde un spec:

```bash
python ./.codex/skills/creacion-propuesta/build_presentation.py build --spec <spec.json>
```

- La salida final debe quedar dentro de `./output/`.

## Limitacion actual del script

- Reemplaza texto por slide y por shape.
- Permite reordenar slides existentes.
- Puede duplicar slides existentes cuando ya hay un layout base reutilizable, como la slide de equipo.
- Para "agregar" slides, reutilizar slides opcionales ya presentes en la plantilla o extender el script en una iteracion posterior.
