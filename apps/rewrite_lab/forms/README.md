# Formularios guiados (asistente de trámites)

Cada carpeta es un formulario que el asistente de trámites puede llenar con la persona usuaria.
**El texto legal sale de la plantilla revisada por una abogada o abogado; Gemma solo conversa y
recaba datos.** El documento lo arma el código (`plantilla.py`), así el LLM no puede inventar
cláusulas ni artículos.

```
forms/
├── README.md                     ← este archivo
├── plantilla.py                  ← llena una plantilla con los datos (sin LLM)
└── divorcio_unilateral_cdmx/
    ├── formulario.yaml           ← qué es, cuándo aplica (triaje), avisos, instrucciones para Gemma y CAMPOS
    ├── plantilla.md              ← el escrito con {campos} y bloques condicionales
    ├── ejemplos.yaml             ← datos ficticios para probar
    └── ejemplo_*.md              ← la plantilla ya llenada con esos datos (para revisar cómo queda)
```

## Sintaxis de la plantilla

| Marca | Qué hace |
|---|---|
| `{nombre_solicitante}` | pone el dato que dio la persona |
| `[SI hay_hijos_menores] … [/SI]` | el bloque solo aparece si el dato es «sí» o no está vacío |
| `[SI NO hay_hijos_menores] … [/SI]` | solo si es «no» o está vacío |
| `[SI regimen = sociedad_conyugal] … [/SI]` | solo si el dato tiene ese valor |
| `[CADA hijo EN hijos] {hijo.nombre} [/CADA]` | se repite por cada elemento de una lista |
| `{#pruebas}` · `{#R medidas}` · `{#A pretensiones}` | numeración automática 1, 2, 3 · I, II, III · A, B, C (no brinca números si se omite un bloque) |
| `<!-- REVISAR (Karen): … -->` | nota de revisión; no aparece en el documento final |

Un dato que falte no se inventa: aparece como `[FALTA: campo]` en el documento.

## Campos (`formulario.yaml`)

Cada campo tiene `id`, `pregunta` (lo que pregunta el asistente), `tipo` (`texto`, `texto_largo`,
`fecha`, `si_no`, `opcion`, `lista`), y opcionalmente `si:` (solo se pregunta si se cumple la
condición, con la misma sintaxis que la plantilla), `obligatorio: false`, `ayuda` y `opciones`.
El orden de la lista es el orden de las preguntas.

Para un formulario nuevo: copiar la carpeta, cambiar `formulario.yaml` y `plantilla.md`, y correr
`uv run --with pytest pytest tests/test_forms.py` (verifica que cada `{campo}` de la plantilla
esté definido en el formulario y que los ejemplos se llenen completos).

## Revisión jurídica pendiente — divorcio unilateral CDMX (estado: **borrador**)

Basado en los modelos de 2008-2009 del *Formulario Práctico Forense en Materia Familiar*,
actualizado con el texto del Código Civil y del CNPCF que están en el corpus. Decisiones tomadas
que conviene confirmar:

1. **Procedimiento: CNPCF, no el Código de Procedimientos Civiles del DF.** Según el Congreso de la
   CDMX, el CNPCF rige en materia familiar desde el 1 de junio de 2026. Se citan los arts. 235
   (requisitos de la demanda), 663-665 (juicio oral familiar) y 677 (disolución del vínculo).
   Falta el artículo de **competencia** en el divorcio unilateral (el 654 es del bilateral).
2. **Sin requisito de «un año de matrimonio».** El art. 266 vigente del Código Civil ya no lo
   menciona; confirmar.
3. **Pruebas:** se quitaron la confesional y la testimonial del modelo de 2008 (en el divorcio sin
   causa no hay causa que probar); quedan documentales, instrumental y presuncional. ¿Falta alguna
   cuando se piden alimentos (p. ej. ingresos del deudor)?
4. **Convenio (art. 267):** fracciones I a VI y los animales de compañía. Falta la cláusula para
   **hijas o hijos mayores que requieren apoyo** (267-I, 283-VI).
5. **Defensa técnica (art. 666 CNPCF):** el asistente avisa que se necesita abogada o abogado, o la
   Defensoría Pública. Confirmar el texto del aviso y el teléfono de Línea Mujeres.
6. **Triaje:** si ambos están de acuerdo, el asistente sugiere divorcio bilateral (arts. 655-662
   CNPCF, incluso Registro Civil o notaría si no hay hijos menores ni bienes).
7. **Domicilio desconocido del cónyuge:** se manifiesta bajo protesta, se piden oficios de búsqueda
   (IMSS, ISSSTE, SAT, INE, CFE y demás instituciones con registro de domicilios) y, si no se le
   localiza, emplazamiento por edictos (arts. 203 y 209-II CNPCF). Confirmar la lista de
   instituciones y si se pide algo sobre el costo de los edictos.
8. Lenguaje: se modernizó (Jueza o Juez, «hijas e hijos», Ciudad de México). Las referencias al
   «Código Civil para el Distrito Federal, aplicable en la Ciudad de México» siguen el nombre del
   documento del corpus; confirmar la denominación correcta.

Para cambiar el estado a `revisado`, editar `estado:` en `formulario.yaml`. El asistente solo
ofrecerá al público los formularios con `estado: publicado`.
