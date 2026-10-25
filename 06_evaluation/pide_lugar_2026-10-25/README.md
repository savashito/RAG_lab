# Filtro por estado en conversaciones (24–25 oct 2026)

## El problema
En una conversación, Tlacua (Gemma) pregunta «¿en qué estado ocurrieron los hechos?» y la persona contesta solo
«Querétaro». El **filtro por estado** (una llamada a Gemma con el prompt `EXTRAER_SYSTEM`, en
`apps/rewrite_lab/jurisdiction_gate.py`) leía solo los mensajes de la persona, no veía la pregunta, y marcaba Querétaro
como **donde vive** la persona, no como **lugar de los hechos**. Tlacua entonces dudaba o volvía a pedir el estado.

## Los métodos comparados
| Método | Qué lee el filtro | Prompt del filtro |
|---|---|---|
| v1 | solo los mensajes de la persona | `EXTRAER_SYSTEM` |
| **v2** (ronda 2, `filtro_ve_pregunta: true` desde el 25-oct) | los mensajes de la persona + la frase donde Tlacua pidió el lugar, que saca una regex (`pregunta_de_lugar`) | `EXTRAER_SYSTEM_V2` |
| v3 | la conversación completa, con las respuestas de Tlacua marcadas como del asistente | `EXTRAER_SYSTEM_V3` |

## La regex que saca la frase donde Tlacua pidió el lugar
Set de referencia: Gemma etiquetó si cada respuesta guardada de Tlacua pide el lugar (2,220 respuestas: repeticiones
de la ronda 1 con filtro y benchmarks #211–#242), tabla `pide_lugar_etiquetas` en la base (`etiquetar.py`). Se compara
cualquier versión de la regex contra ese set en segundos (`comparar.py`).

| | regex v2 (24-oct) | **regex v3 (25-oct, en prod)** |
|---|---|---|
| Peticiones de lugar que encuentra (de 591) | 548 (92.7 %) | **578 (97.8 %)** |
| Falsos positivos (de 1,629 respuestas que no piden) | 29 (1.8 %) | **24 (1.5 %)** |

Una versión intermedia encontraba 98 % pero tenía 8.5 % de falsos positivos (confundía «el Estado» —el gobierno— y
«Indica que…» con peticiones); se descartó. Ojo: el set lo etiquetó Gemma, no una persona.

## Prueba del filtro: «Filtro por estado · métodos» (🧩 Componentes, corrida #31)
237 casos: 145 de un mensaje, 12 de dos mensajes inventados, y 80 de dos mensajes con la **respuesta real de Tlacua**
que pide el lugar (5 preguntas sin lugar del set 14 × 2 prompts de respuesta × 8 formas de contestar;
`generar_casos_dos_mensajes.py`).

| | v1 | **v2** | v3 |
|---|---|---|---|
| Aciertos, total (237) | 211 (89 %) | **230 (97 %)** | 229 (97 %) |
| Dos mensajes con respuesta real de Tlacua (80) | 62 | **80** | 78 |
| **Falsos positivos** del lugar de los hechos (de 100 casos que lo prueban) | 0 | **0** | 0 |
| **Falsos negativos** del lugar de los hechos | 21 | **2** | 3 |
| Segundos por llamada | 0.66 | 0.58 | 0.62 |

- **Aciertos** = el filtro dio exactamente lo esperado en los campos que prueba el caso.
- **Falso positivo** = marcó como lugar de los hechos un estado que no lo es. Es el error grave: Tlacua citaría el
  código de un estado que puede no aplicar (el hallazgo de la ronda 1).
- **Falso negativo** = no marcó el lugar de los hechos que sí dijo la persona. Tlacua vuelve a pedir el estado o duda.

Los 2 falsos negativos de v2 son casos de un mensaje que ya fallaban: «Vivo en Toluca y un vecino entró a mi casa» y
«Trabajo en Morelos y mi jefa me presiona…». Solo 23 casos prueban «no marcar ninguno»: 0 falsos positivos es buena
señal, no garantía.

## Conclusión
La ronda 2 usa v2 (con la regex v3). v3 (conversación completa, sin regex) salió casi igual de bien y no se confundió con
los estados que Tlacua menciona al explicar: es la alternativa si la regex da problemas.

## Archivos
- `etiquetar.py`: set de referencia (Gemma) en la tabla `pide_lugar_etiquetas`. Retoma donde se quedó.
- `comparar.py`: compara dos versiones de la regex contra el set.
- `generar_casos_dos_mensajes.py`: los 80 casos con respuesta real de Tlacua. **No deja transacciones abiertas mientras
  llama a Gemma** (una versión anterior bloqueó prod ~6 min el 25-oct).
- Prueba de punta a punta en la ronda 2: `../estudio_ronda2_2026-10-23/prueba_respuesta_corta.py`.
