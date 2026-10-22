# Matriz de configuraciones · 2026-10-21

72 corridas del benchmark (corridas #107–#178), lanzadas con `launch_matriz.py`, `launch_matriz_e.py` y `launch_matriz_f.py`, en una copia temporal de prod (puerto 8099). Son 9 configuraciones × 4 sets × 2 repeticiones. El LLM que responde y el juez son el mismo modelo, Gemma-4-4B-8b. Los scores del set 3 ya incluyen la recalificación del 2026-10-21 (`corregir_set3.py` y `recalificar_set3.py`).

## Las configuraciones

Todas parten de la misma base, la configuración de la corrida #102 (la del estudio): buscador híbrido (vectores + BM25), los 10 primeros resultados del buscador + sus chunks vecinos, HyDE (el LLM escribe una respuesta hipotética para buscar con ella) y «descomponer» (el LLM divide la pregunta en sub-preguntas y se busca cada una).

| Config | Filtro por estado | Descomponer por delito | Remisiones | Prompt | Para qué |
|---|---|---|---|---|---|
| **A** | no | no | no | penal-original-v1 | Línea base: el sistema sin los cambios de esta semana |
| **B** | viejo | no | no | penal-original-v1 | Efecto del filtro (versión de prod) |
| **C** | viejo | sí (+3 chunks) | sí | penal-original-v1 | Todo lo nuevo junto |
| **D** | viejo | sí (+3 chunks) | sí | tlacua-v1-penas | Prompt nuevo, con todo lo demás como C |
| **E** | viejo | sí (+3 chunks) | sí | tlacua-secuencia-y-penas | Prompt del usuario, con todo lo demás como C |
| **B2** | **corregido** | no | no | penal-original-v1 | Como B, con el filtro corregido |
| **G2** | **corregido** | sí (+3 chunks) | **no** | penal-original-v1 | Como C2 sin remisiones: aísla el efecto de las remisiones |
| **C2** | **corregido** | sí (+3 chunks) | sí | penal-original-v1 | Como C, con el filtro corregido |
| **D2** | **corregido** | sí (+3 chunks) | sí | tlacua-v1-penas | Como D, con el filtro corregido |

- **Filtro por estado:** antes de buscar, un LLM lee la pregunta, detecta el estado donde ocurrieron los hechos y el tipo de asunto, y limita los códigos que el buscador puede traer. Si falta el estado y la respuesta depende de él, le indica a la respuesta que lo pida.
- **Filtro viejo:** el que está hoy en prod. Deja fuera el Código Penal Federal salvo en delitos federales, aunque la pregunta lo nombre, y trata las preguntas de teoría como casos sin estado.
- **Filtro corregido** (commit 50af8e3, sin desplegar): el CPF entra si la pregunta lo nombra («Código Penal Federal», «CPF», «ámbito federal»). Las preguntas teóricas, sin un caso concreto, no piden estado y pueden ver todos los códigos.
- **Descomponer por delito:** el LLM separa las conductas del caso (por ejemplo, «lesiones» y «amenazas») y el buscador trae 3 chunks extra por cada conducta adicional.
- **Remisiones:** si un artículo del contexto remite a otro («las penas del artículo 220»), se agrega ese artículo al contexto, hasta 4. Las remisiones salen de la tabla `corpus_remisiones`.
- **Prompts:** `penal-original-v1` es el prompt de la ronda 1 del estudio. `tlacua-v1-penas` es tlacua-v1 más una sección que pide dar las penas. `tlacua-secuencia-y-penas` es el prompt del usuario del 20 de octubre.

## Los sets

- **Set 3 (50 preguntas):** delitos sexuales, parte general y CNPP. Las preguntas dicen qué ley quieren, o son teóricas. Es la prueba de regresión: el filtro no debería cambiar su score.
- **Set 13 (31 preguntas):** preguntas en lenguaje cotidiano que dicen un solo estado. Mide si la respuesta usa solo el código de ese estado.
- **Set 14 (57 preguntas):** «¿cuándo pedir el estado?». Incluye preguntas sin lugar (hay que pedirlo), con lugar indirecto (dónde vive la persona), comparaciones, estados fuera del corpus y leyes nacionales (no hay que pedirlo).
- **Set 12 (3 preguntas):** casos complejos de Karen, con control de tipicidad. Con solo 3 preguntas, cada una pesa un tercio del score.

## Qué es cada columna

- **Score rep 1 / rep 2:** el score de cada una de las dos corridas. El juez revisa cada criterio de la pregunta (presente, parcial o ausente). El score es la suma ponderada de los criterios `must` y `should` cumplidos, menos los `must_not` violados, dividida entre el peso total de los `must` y `should`. Se promedia sobre las preguntas y va de 0 a 100.
- **Media:** el promedio de las 2 repeticiones. Primero se promedia cada pregunta entre las dos corridas, y luego entre preguntas.
- **IC 95 %:** el intervalo de confianza de la media, por bootstrap sobre las preguntas (2,000 remuestreos). Mide qué tanto cambiaría la media con otras preguntas del mismo tipo. **No es la desviación estándar entre repeticiones:** con 2 repeticiones, la desviación estándar no se puede estimar bien. Para el ruido entre corridas, compara rep 1 contra rep 2.
- **Must:** el porcentaje de criterios `must` que el juez marcó como presentes.
- **Pasa:** el porcentaje de preguntas con todos los `must` presentes y ningún `must_not`.
- **Recall:** el porcentaje de los artículos que la pregunta necesita (los que nombran sus `must` de cita) que llegaron al contexto del LLM. Lo calcula un script, sin LLM. Mide al buscador, no la respuesta.
- **Otro estado:** el porcentaje de respuestas que citan el código penal de un estado que no corresponde. Lo mide el verificador de citas (regex, sin LLM), solo en las preguntas donde aplica.
- **Citas sin respaldo:** el porcentaje de los artículos citados que no están en el contexto. Incluye los inventados (no existen en el corpus), los de memoria y los atribuidos a la ley equivocada.
- **De memoria:** la parte de las citas sin respaldo que son artículos reales, pero que el LLM citó sin tenerlos en el contexto.
- **Seg/preg:** los segundos promedio por pregunta: búsqueda, respuesta y juez.

### Set 3 · general (50 preguntas: delitos sexuales, parte general, CNPP)

| Config | Corridas | Score rep 1 | Score rep 2 | **Media** | IC 95 % | Must | Pasa | Recall | Otro estado | Citas sin respaldo | De memoria | Seg/preg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | #109, #125 | 89.7 | 91.4 | **90.5** | 86.8–94.0 | 95.2 | 80.0 | 90.6 | 1.7 | 11.3 | 10.3 | 10.3 |
| B | #113, #129 | 80.6 | 80.5 | **80.6** | 72.3–87.7 | 82.9 | 62.0 | 67.5 | 0.0 | 21.6 | 21.2 | 12.2 |
| C | #117, #133 | 77.6 | 77.5 | **77.6** | 69.9–84.7 | 80.3 | 55.0 | 67.5 | 0.0 | 21.1 | 21.1 | 12.9 |
| D | #121, #137 | 77.8 | 80.4 | **79.1** | 71.9–85.4 | 79.2 | 56.0 | 68.8 | 0.0 | 9.2 | 9.2 | 13.1 |
| E | #141, #145 | 78.1 | 78.2 | **78.1** | 70.8–84.5 | 77.4 | 45.0 | 69.4 | 0.0 | 11.5 | 10.8 | 13.2 |
| B2 | #147, #163 | 90.0 | 89.0 | **89.5** | 85.3–93.2 | 93.2 | 77.0 | 90.0 | 0.0 | 10.0 | 8.7 | 10.8 |
| G2 | #151, #167 | 90.1 | 90.7 | **90.4** | 87.1–93.5 | 94.1 | 76.0 | 88.8 | 0.0 | 5.8 | 5.1 | 12.8 |
| C2 | #155, #171 | 89.6 | 87.7 | **88.7** | 84.7–92.3 | 93.4 | 75.0 | 90.0 | 0.0 | 11.4 | 8.3 | 12.8 |
| D2 | #159, #175 | 89.5 | 90.3 | **89.9** | 86.1–93.3 | 93.4 | 76.0 | 90.0 | 0.0 | 4.2 | 3.8 | 13.0 |

### Set 13 · un solo estado (31)

| Config | Corridas | Score rep 1 | Score rep 2 | **Media** | IC 95 % | Must | Pasa | Recall | Otro estado | Citas sin respaldo | De memoria | Seg/preg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | #107, #123 | 64.5 | 71.0 | **67.7** | 55.6–79.0 | 79.0 | 69.3 | 82.3 | 21.0 | 6.8 | 3.2 | 9.5 |
| B | #111, #127 | 77.4 | 72.6 | **75.0** | 65.3–84.7 | 88.7 | 88.7 | 90.3 | 0.0 | 8.2 | 2.8 | 10.9 |
| C | #115, #131 | 75.8 | 72.6 | **74.2** | 64.5–83.1 | 87.1 | 87.1 | 93.5 | 0.0 | 7.1 | 0.7 | 11.7 |
| D | #119, #135 | 82.3 | 83.9 | **83.1** | 75.0–90.3 | 91.9 | 91.9 | 91.9 | 0.0 | 1.3 | 0.7 | 12.2 |
| E | #139, #143 | 81.5 | 87.1 | **84.3** | 78.6–89.9 | 91.9 | 91.9 | 93.5 | 0.0 | 0.7 | 0.7 | 12.3 |
| B2 | #148, #164 | 79.0 | 79.0 | **79.0** | 69.3–87.9 | 93.5 | 93.5 | 95.2 | 0.0 | 6.3 | 4.4 | 10.0 |
| G2 | #152, #168 | 75.8 | 77.4 | **76.6** | 69.3–83.9 | 91.9 | 91.9 | 96.8 | 0.0 | 8.4 | 1.4 | 11.6 |
| C2 | #156, #172 | 71.0 | 77.4 | **74.2** | 66.1–82.3 | 91.9 | 90.3 | 95.2 | 0.0 | 8.6 | 0.6 | 11.9 |
| D2 | #160, #176 | 81.5 | 82.3 | **81.8** | 75.8–87.9 | 91.9 | 90.3 | 95.2 | 0.0 | 1.3 | 1.3 | 12.2 |

### Set 14 · ¿cuándo pedir el estado? (57)

| Config | Corridas | Score rep 1 | Score rep 2 | **Media** | IC 95 % | Must | Pasa | Recall | Otro estado | Citas sin respaldo | De memoria | Seg/preg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | #108, #124 | 37.1 | 41.2 | **39.2** | 28.4–50.0 | 60.6 | 36.0 | 71.9 | 25.0 | 11.4 | 11.0 | 9.6 |
| B | #112, #128 | 80.1 | 81.6 | **80.8** | 72.1–88.2 | 87.1 | 81.6 | 82.3 | 0.0 | 12.2 | 9.9 | 11.2 |
| C | #116, #132 | 89.3 | 90.3 | **89.8** | 83.3–95.0 | 94.7 | 88.6 | 93.8 | 0.0 | 18.7 | 15.3 | 11.9 |
| D | #120, #136 | 79.4 | 81.6 | **80.5** | 71.9–88.4 | 77.3 | 79.8 | 94.8 | 0.0 | 24.1 | 22.5 | 12.2 |
| E | #140, #144 | 75.4 | 71.0 | **73.2** | 64.0–82.0 | 71.2 | 71.0 | 95.8 | 0.0 | 24.2 | 23.1 | 12.3 |
| B2 | #149, #165 | 85.4 | 80.7 | **83.0** | 75.0–90.3 | 87.9 | 82.5 | 82.3 | 0.0 | 15.5 | 11.4 | 9.9 |
| G2 | #153, #169 | 83.3 | 85.4 | **84.4** | 76.3–91.5 | 90.1 | 84.2 | 88.5 | 0.0 | 19.0 | 16.7 | 11.7 |
| C2 | #157, #173 | 91.2 | 87.7 | **89.5** | 83.8–94.3 | 96.2 | 91.2 | 95.8 | 0.0 | 18.9 | 15.7 | 11.8 |
| D2 | #161, #177 | 73.7 | 72.8 | **73.2** | 63.6–82.9 | 70.5 | 71.1 | 91.7 | 0.0 | 23.8 | 21.8 | 12.2 |

### Set 12 · casos de Karen (3)

| Config | Corridas | Score rep 1 | Score rep 2 | **Media** | IC 95 % | Must | Pasa | Recall | Otro estado | Citas sin respaldo | De memoria | Seg/preg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | #110, #126 | 28.5 | 25.5 | **27.0** | 9.5–36.4 | 36.1 | 0.0 | 50.0 | 50.0 | 5.6 | 0.0 | 17.2 |
| B | #114, #130 | 34.9 | 32.2 | **33.6** | 28.4–38.9 | 40.3 | 0.0 | 57.7 | 0.0 | 0.0 | 0.0 | 18.6 |
| C | #118, #134 | 40.7 | 37.2 | **39.0** | 36.4–42.6 | 45.8 | 0.0 | 76.9 | 0.0 | 0.0 | 0.0 | 21.6 |
| D | #122, #138 | 69.6 | 68.8 | **69.2** | 62.1–82.6 | 68.0 | 0.0 | 76.9 | 0.0 | 0.0 | 0.0 | 22.8 |
| E | #142, #146 | 56.2 | 61.6 | **58.9** | 57.4–60.6 | 62.5 | 0.0 | 76.9 | 0.0 | 11.1 | 11.1 | 22.9 |
| B2 | #150, #166 | 32.1 | 29.0 | **30.5** | 26.7–33.3 | 37.5 | 0.0 | 61.5 | 0.0 | 0.0 | 0.0 | 16.6 |
| G2 | #154, #170 | 31.3 | 29.1 | **30.2** | 27.3–31.9 | 36.1 | 0.0 | 69.2 | 0.0 | 0.0 | 0.0 | 20.8 |
| C2 | #158, #174 | 40.1 | 31.2 | **35.7** | 32.8–40.9 | 43.0 | 0.0 | 76.9 | 0.0 | 0.0 | 0.0 | 21.6 |
| D2 | #162, #178 | 62.7 | 63.3 | **63.0** | 60.6–67.2 | 61.1 | 0.0 | 76.9 | 0.0 | 0.0 | 0.0 | 22.4 |

## Comparaciones pareadas (misma pregunta, promedio de las 2 repeticiones)

| Comparación | Qué mide | Set 3 | Set 13 | Set 14 | Set 12 |
|---|---|---|---|---|---|
| A → B | filtro viejo | **-10.0 (-16.7 a -4.5)** | +7.3 (-1.6 a +16.9) | **+41.7 (+30.3 a +52.4)** | +6.6 (-3.0 a +19.0) |
| B → B2 | arreglo del filtro | **+9.0 (+2.8 a +16.2)** | +4.0 (-1.6 a +9.7) | +2.2 (-1.3 a +5.7) | -3.0 (-7.4 a +0.0) |
| A → B2 | filtro corregido | -1.0 (-3.4 a +0.9) | +11.3 (+0.0 a +22.6) | **+43.9 (+32.5 a +54.6)** | +3.5 (-3.7 a +17.2) |
| B2 → G2 | descomponer por delito | +0.9 (-2.0 a +4.1) | -2.4 (-12.9 a +9.7) | +1.3 (-4.4 a +7.5) | -0.3 (-6.1 a +5.2) |
| G2 → C2 | solo remisiones | -1.8 (-4.1 a +0.4) | -2.4 (-9.7 a +4.0) | +5.1 (-0.6 a +11.7) | **+5.5 (+0.9 a +13.6)** |
| C2 → D2 | prompt tlacua-v1-penas | +1.3 (-1.1 a +3.7) | +7.7 (-0.8 a +16.9) | **-16.2 (-26.3 a -6.6)** | **+27.3 (+19.7 a +34.5)** |
| C → D | prompt tlacua-v1-penas (filtro viejo) | +1.6 (-1.7 a +5.3) | +8.9 (-0.8 a +18.6) | **-9.4 (-17.0 a -2.3)** | **+30.2 (+20.4 a +46.2)** |
| D → E | tlacua-secuencia-y-penas vs tlacua-v1-penas | -1.0 (-3.1 a +1.2) | +1.2 (-6.9 a +8.9) | -7.2 (-16.0 a +1.8) | **-10.3 (-22.0 a -3.5)** |
En las comparaciones pareadas, cada pregunta se compara contra sí misma en las dos configuraciones. La diferencia está en puntos de score, con su IC 95 % por bootstrap. **En negritas:** el intervalo no incluye el 0, así que la diferencia probablemente no es ruido. El set 12 tiene solo 3 preguntas: sus intervalos no son confiables.

## Conclusiones

1. **El filtro corregido (B2) arregla el problema del viejo (B) sin perder lo ganado.**
   - En el set 3 sube +9.0 puntos (significativo) y queda igual que sin filtro (A): −1.0, que no es significativo.
   - En el set 14 mantiene la ganancia del filtro: +43.9 contra A.
   - Las respuestas que citan otro estado bajan de 21 % (set 13) y 25 % (set 14) en A a 0 %.
2. **Descomponer por delito (B2 → G2)** no cambia el score de forma significativa en ningún set.
3. **Las remisiones (G2 → C2)** dan +5.1 en el set 14 y −1.8 y −2.4 en los sets 3 y 13. Ninguna de estas diferencias es significativa. En el set 12 dan +5.5 (n = 3). Hoy no muestran un efecto claro.
4. **tlacua-v1-penas (C2 → D2):**
   - mejora mucho el set 12 (+27, n = 3) y el set 13 (+7.7, no significativo);
   - empeora el set 14 (−16.2, significativo; con el filtro viejo, −9.4, también significativo);
   - hay que revisar por qué antes de usarlo en la ronda 2.
5. **tlacua-secuencia-y-penas (E)** queda parecido o un poco abajo de tlacua-v1-penas (D) en los sets 3, 12 y 14, y un poco arriba en el set 13. En el set 12 baja −10.3 (n = 3).
6. **Ruido entre repeticiones:** hasta 6 puntos en los sets 13 y 14 (C2 en el set 13: 71.0 contra 77.4) y hasta 9 en el set 12. Diferencias menores a ~5 puntos entre configuraciones no son concluyentes.
