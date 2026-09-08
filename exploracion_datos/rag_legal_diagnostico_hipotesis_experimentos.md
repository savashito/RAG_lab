# Diagnóstico de un Sistema RAG Legal
## Hipótesis y experimentos para descubrir al culpable

> **Pregunta central:** ¿Por qué el chunk correcto no llega suficientemente arriba en el ranking?

---

# 1. Mapa general del problema

```text
                    MAL RETRIEVAL
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
     Corpus            Query           Retriever
     / chunks        formulation       / embedding
        │                │                │
        ▼                ▼                ▼
    Chunking          Semantic gap     Model weakness
    Metadata          Colloquial       Similarity
    Duplicates        Negative         Ranking

                         │
                         ▼
                    Candidate pool
                         │
                         ▼
                      Reranker
                         │
                         ▼
                     Final ranking
```

---

# H1 — El chunking es el culpable

## Hipótesis

El contenido correcto existe, pero está:

- cortado incorrectamente;
- separado de información importante;
- demasiado pequeño;
- demasiado grande;
- repetido;
- mezclado con otros artículos.

## Evidencia actual

En el caso del Artículo 14 parece que el chunking **probablemente no es el principal culpable**, porque el chunk correcto está limpio.

Pero eso solo demuestra que **ese caso específico** no es un problema de chunking.

## Experimento

Para cada pregunta fallida, inspeccionar manualmente:

```text
Question
    │
    ▼
Gold chunk
    │
    ├── Clean?
    ├── Complete?
    ├── Contains answer?
    ├── Correct context?
    ├── Duplicate?
    └── Split across chunks?
```

Crear una tabla:

```python
failure_analysis = {
    'q': ...,
    'chunk_clean': True,
    'answer_complete': True,
    'duplicate_chunks': 3,
    'split_answer': False,
}
```

## Interpretación

Si muchos fallos tienen:

```text
split_answer = True
```

➡️ **Culpable: chunking**

---

# H2 — El corpus contiene demasiados duplicados

## Hipótesis

El embedder encuentra correctamente el concepto, pero los primeros resultados contienen:

```text
Artículo 14
Artículo 14 duplicate
Artículo 14 duplicate
Artículo 14 overlap
Artículo 14 partial
```

Esto puede distorsionar el ranking y ocupar posiciones con información casi idéntica.

## Experimento

Para cada documento, calcular similitud entre chunks:

```python
embedding_similarity(chunk_i, chunk_j)
```

Encontrar pares con:

```text
similarity > 0.95
```

y contar duplicados.

Luego comparar:

### A

```text
Original corpus
```

### B

```text
Deduplicated corpus
```

Medir:

```text
Recall@10
Recall@50
MRR
```

## Interpretación

Si mejora significativamente:

➡️ **Culpable parcial: corpus duplication**

---

# H3 — El lenguaje coloquial crea un semantic gap

## Hipótesis

Las preguntas están formuladas en lenguaje coloquial, mientras que el corpus utiliza lenguaje jurídico formal.

### Ejemplo

Query:

```text
¿Me pueden volver a acusar por algo
de lo que ya salí absuelto?
```

Documento:

```text
Principio de prohibición
de doble enjuiciamiento

No podrá ser sometida a otro proceso penal
por los mismos hechos.
```

La relación conceptual existe, pero el vocabulario es diferente.

## Experimento

Tomar exactamente las mismas preguntas y crear varias versiones.

### Original

```text
¿Me pueden volver a acusar por algo
de lo que ya salí absuelto?
```

### Legal rewrite

```text
¿Puede una persona absuelta ser sometida
nuevamente a un proceso penal por los
mismos hechos?
```

### Keyword expansion

```text
doble enjuiciamiento
non bis in idem
nuevo proceso penal
mismos hechos
```

Luego comparar los ranks.

## Interpretación

Si ocurre algo como:

| Question | Original | Rewrite |
|---|---:|---:|
| Q1 | 74 | 4 |
| Q2 | 66 | 7 |
| Q3 | 309 | 12 |

➡️ **Culpable: query formulation / semantic gap**

---

# H4 — El embedder no es suficientemente bueno para español jurídico

## Hipótesis

Incluso con una buena formulación de la pregunta, el modelo de embeddings no representa suficientemente bien:

- español;
- terminología jurídica;
- paráfrasis;
- lenguaje coloquial;
- distinciones jurídicas finas.

## Experimento

Mantener constantes:

```text
Corpus
Queries
Chunking
Evaluation
```

Cambiar únicamente el embedder:

```text
Embedder A
Embedder B
Embedder C
Embedder D
```

Medir:

```text
Recall@1
Recall@5
Recall@10
Recall@50
MRR
```

Especialmente por:

```text
type
```

Por ejemplo:

```text
semantic_paraphrase
colloquial_to_legal
conceptual_distinction
negative_question
```

## Interpretación

Si un modelo supera claramente a otro:

➡️ **Culpable: embedder**

---

# H5 — El problema es la métrica de similitud o su implementación

## Hipótesis

El embedder puede ser bueno, pero la comparación de embeddings puede estar implementada incorrectamente.

Posibles problemas:

- cosine similarity;
- dot product;
- embeddings no normalizadas;
- índices vectoriales mal configurados.

## Experimento

Verificar:

```python
np.linalg.norm(embedding)
```

Comparar:

```text
Cosine similarity
```

vs.

```text
Dot product
```

vs.

```text
Normalized embeddings + dot product
```

## Interpretación

Si las métricas cambian significativamente:

➡️ **Culpable: similarity implementation**

Este experimento es barato y debe hacerse temprano.

---

# H6 — El corpus es demasiado competitivo

## Hipótesis

Un dense rank de 74 no necesariamente significa que el modelo sea completamente malo.

Puede significar que existen muchos chunks jurídicamente similares.

Por ejemplo:

```text
Artículo 14
Artículo 15
Artículo 16
Artículo 17
```

Todos pueden hablar de:

```text
derechos
proceso
persona
imputado
autoridad
```

## Experimento

Para cada pregunta fallida, inspeccionar:

```text
Gold chunk
```

contra:

```text
Top 20 distractors
```

Clasificar cada distractor:

```python
{
    'same_document': True,
    'same_topic': True,
    'same_article': False,
    'legal_semantic_neighbor': True
}
```

Preguntar:

> ¿Por qué los primeros resultados ganaron al gold chunk?

## Interpretación

Si la mayoría son:

```text
legal semantic neighbors
```

➡️ **Problema: precision / fine-grained ranking del embedding**

---

# H7 — El sistema entiende el tema, pero no encuentra la fuente exacta

## Hipótesis

El modelo puede recuperar documentos sobre el tema correcto, pero no el artículo exacto.

Ejemplo:

```text
Query:
¿Pueden detenerme?
```

Resultados:

```text
1. Detención
2. Medidas cautelares
3. Prisión preventiva
4. Derechos del detenido
5. Libertad personal
...
74. Artículo correcto
```

El sistema entiende:

```text
DETENCIÓN
```

pero no:

```text
ESTE ARTÍCULO EXACTO
```

## Experimento

Medir dos métricas:

```text
Topic Recall
```

y:

```text
Exact Article Recall
```

Ejemplo:

```text
Top 10:

Topic relevant: YES
Correct article: NO
```

Crear:

```text
topic_hit@10
exact_hit@10
```

## Interpretación

Si:

```text
topic_hit@10 = 95%
exact_hit@10 = 50%
```

➡️ El sistema entiende el dominio, pero falla en **fine-grained retrieval**.

---

# H8 — BM25 ayuda solo cuando existe overlap léxico

## Hipótesis

BM25 funciona bien para preguntas directas:

```text
¿Qué es un dato de prueba?
```

Pero falla para paráfrasis:

```text
¿Eso que encontró la policía ya cuenta como prueba?
```

## Experimento

Dividir las preguntas por tipo:

```text
direct_lexical
semantic_paraphrase
colloquial_to_legal
```

Comparar:

```text
Dense
BM25
Hybrid
```

Agrupar resultados:

```python
results.groupby(['type', 'method'])
```

## Interpretación

Si:

```text
BM25:

Direct:       excellent
Semantic:     bad
Colloquial:   terrible
```

➡️ BM25 no es malo en general.

➡️ Tiene un **failure mode específico**.

---

# H9 — RRF está perjudicando ciertos tipos de query

## Hipótesis

Hay que distinguir:

> BM25 malo

de:

> RRF malo

## Experimento

Comparar:

### Dense

```text
Dense only
```

### BM25

```text
BM25 only
```

### RRF

```text
Dense + BM25
```

### Weighted fusion

Por ejemplo:

```text
0.8 Dense
0.2 BM25
```

y:

```text
0.9 Dense
0.1 BM25
```

Comparar por tipo de pregunta.

## Interpretación

Si ocurre:

```text
Colloquial:

Dense          74
RRF           180
Weighted RRF   81
```

➡️ **Culpable: fusion strategy**

---

# H10 — El parámetro `k` de RRF es inadecuado

## Hipótesis

RRF normalmente utiliza:

\[
score(d)=\frac{1}{k+r_1}+\frac{1}{k+r_2}
\]

El parámetro `k` puede modificar la influencia relativa de los rankings.

## Experimento

Probar:

```text
k = 10
k = 30
k = 60
k = 100
```

Comparar:

```text
Recall@10
Recall@50
MRR
```

---

# H11 — El candidate pool es demasiado pequeño

## Hipótesis

El gold chunk puede estar relativamente cerca, pero fuera del pool del reranker.

Ejemplo:

```text
Gold rank:

66
74
309
```

Pero:

```text
Candidates = 50
```

Entonces:

```text
66  ❌
74  ❌
309 ❌
```

El reranker nunca ve esos documentos.

## Experimento

Probar:

```text
Candidates

10
25
50
100
200
500
```

Medir:

```text
Recall@Candidates
```

Ejemplo:

| Candidates | Recall |
|---:|---:|
| 10 | 45% |
| 50 | 70% |
| 100 | 85% |
| 200 | 92% |
| 500 | 96% |

## Interpretación

Esto revela cuánto recall tiene realmente el **candidate generator**.

---

# H12 — El reranker sí funciona, pero nunca ve la respuesta

## Hipótesis

El reranker puede ser bueno, pero el problema ocurre antes.

## Experimento

Para preguntas donde:

```text
Dense rank = 50–200
```

pasar:

```text
Top 200
```

al reranker.

Comparar:

```text
Before rerank → 74
After rerank  → ?
```

### Caso A

```text
Dense:    74
Rerank:    2
```

➡️ Reranker excelente.

➡️ **Culpable: candidate generation**

### Caso B

```text
Dense:    74
Rerank:   80
```

➡️ El reranker tampoco entiende la relación.

---

# H13 — El reranker no funciona bien en español jurídico

## Hipótesis

El candidate pool contiene la respuesta correcta, pero el reranker no sabe identificarla como la mejor respuesta.

## Experimento

Mantener constante:

```text
Candidate pool
```

Comparar:

```text
Reranker A
Reranker B
Reranker C
```

Medir:

```text
MRR
NDCG@5
Hit@1
Hit@5
```

---

# H14 — El problema son las preguntas negativas

## Hipótesis

Los embeddings pueden ser débiles con palabras que cambian radicalmente el significado:

```text
no
excepto
salvo
nunca
prohibido
```

## Experimento

Crear pares mínimos.

```text
Q1:
¿Puede volver a ser procesada?

Q2:
¿No puede volver a ser procesada?
```

Otro:

```text
Q1:
¿Cuándo puede detenerse?

Q2:
¿Cuándo no puede detenerse?
```

## Interpretación

Este es un buen experimento porque solo cambia una variable.

---

# H15 — El problema son las distinciones conceptuales

## Hipótesis

Conceptos jurídicos cercanos pueden ser difíciles de distinguir:

```text
indicio
evidencia
dato de prueba
medio de prueba
prueba
```

## Experimento

Crear preguntas de contraste:

```text
¿Cuál es la diferencia entre indicio y evidencia?

¿Cuál es la diferencia entre evidencia y prueba?

¿Cuándo un dato adquiere calidad de prueba?
```

Medir:

```text
Conceptual distinction Recall@10
```

## Interpretación

Si este tipo falla especialmente:

➡️ El modelo tiene problemas con **distinciones conceptuales finas**.

---

# H16 — Falta metadata en los chunks

## Hipótesis

El contenido puede ser correcto, pero el embedding pierde información estructural.

## Experimento

Comparar:

### Corpus A

```text
Chunk text
```

### Corpus B

```text
Document:
Código Nacional de Procedimientos Penales

Section:
Artículo 14

Topic:
Prohibición de doble enjuiciamiento

Text:
...
```

Embebes ambos y comparas retrieval.

## Interpretación

Si mejora:

➡️ **Metadata enrichment ayuda**

---

# H17 — El tamaño del chunk afecta el ranking

## Hipótesis

La granularidad del chunk puede afectar:

- precisión;
- recall;
- contexto;
- cantidad de ruido.

## Experimento

Probar:

```text
256 tokens
512 tokens
1024 tokens
Article-based chunks
Semantic chunks
```

Manteniendo constantes:

```text
Same model
Same queries
Same corpus
Same evaluation
```

---

# H18 — Los artículos deberían ser la unidad de retrieval

## Hipótesis

Para legislación, quizá la unidad natural no es un chunk arbitrario sino:

```text
Artículo completo
```

## Experimento

Comparar:

### Strategy A

```text
Fixed-size chunks
```

### Strategy B

```text
Article-based chunks
```

### Strategy C

```text
Article + subsection
```

Medir las mismas métricas.

---

# H19 — Query rewriting resuelve el semantic gap

## Hipótesis

Traducir lenguaje coloquial a lenguaje jurídico puede mejorar el retrieval.

## Experimento

Comparar:

```text
Original
```

vs.

```text
Legal rewrite
```

vs.

```text
Original + legal expansion
```

Ejemplo:

### Original

```text
¿Me pueden volver a acusar por algo
de lo que ya salí absuelto?
```

### Rewrite

```text
¿Puede una persona absuelta ser sometida
a un nuevo proceso penal por los mismos hechos?
```

### Expansion

```text
prohibición de doble enjuiciamiento,
non bis in idem,
nuevo proceso penal,
mismos hechos
```

---

# H20 — Multi-query retrieval es mejor que un solo rewrite

## Hipótesis

En lugar de reemplazar la pregunta original, generar múltiples representaciones.

```text
                Query
                  │
       ┌──────────┼──────────┐
       │          │          │
       ▼          ▼          ▼
   Original     Legal      Keywords
       │          │          │
       ▼          ▼          ▼
     Dense      Dense      Dense
       │          │          │
       └──────────┼──────────┘
                  │
                  ▼
                Union
```

## Experimento

Comparar:

```text
Single query
```

vs.

```text
Multi-query
```

---

# H21 — HyDE mejora candidate generation

## Hipótesis

Una respuesta hipotética puede estar más cerca del lenguaje del documento que la pregunta original.

## Experimento

```text
Question
    ↓
LLM
    ↓
Hypothetical legal answer
    ↓
Embedding
    ↓
Retrieval
```

Comparar:

```text
Original Dense
Legal Rewrite
Multi-query
HyDE
```

---

# H22 — El benchmark está midiendo incorrectamente

## Hipótesis

El benchmark puede estar utilizando una única frase literal como proxy de relevancia.

Ejemplo:

```python
'answer': 'frase literal'
```

y luego:

```text
answer in chunk
```

Pero otro artículo puede responder correctamente sin contener esa frase exacta.

Entonces:

```text
Retrieval failed
```

puede ser un:

```text
False negative
```

## Experimento

Cambiar:

```text
One gold chunk
```

por:

```text
Multiple relevant chunks
```

Por ejemplo:

```python
{
    'q': ...,
    'acceptable_answers': [
        'Artículo 97...',
        'Artículo 357...'
    ]
}
```

O mejor:

```python
{
    'relevant_chunk_ids': [
        123,
        456
    ]
}
```

---

# H23 — Estás evaluando frase exacta, no relevancia

## Hipótesis

La evaluación puede estar midiendo:

```text
Exact retrieval
```

cuando realmente importa:

```text
Answer relevance
```

## Experimento

Para errores en Top-5, hacer evaluación humana.

Clasificar:

```text
0 = irrelevant
1 = topically related
2 = partially answers
3 = directly answers
```

Esto puede revelar:

```text
Hit@5 = 40%

pero

Relevant@5 = 85%
```

## Interpretación

Eso cambiaría completamente el diagnóstico.

---

# 2. Orden recomendado de experimentos

No probar todos los experimentos inmediatamente.

La estrategia debe ser descartar hipótesis de forma ordenada.

---

# Fase 1 — Sanity checks

## Experimento 1 — Verificar gold chunks

Confirmar:

```text
¿Existe?
¿Está limpio?
¿Contiene la respuesta?
¿Está duplicado?
```

---

## Experimento 2 — Verificar similitud

Confirmar:

```text
Cosine
Normalization
Dot product
```

---

## Experimento 3 — Validar benchmark

Inspeccionar:

```text
False negatives
```

---

# Fase 2 — Encontrar el failure mode

## Experimento 4 — Agrupar por dificultad

```python
results.groupby('difficulty')
```

---

## Experimento 5 — Agrupar por tipo

```python
results.groupby('type')
```

Comparar:

```text
Dense
BM25
Hybrid
```

Tabla objetivo:

| Type | Dense | BM25 | Hybrid |
|---|---:|---:|---:|
| direct | | | |
| semantic_paraphrase | | | |
| colloquial_to_legal | | | |
| negative_question | | | |
| conceptual_distinction | | | |

Esta tabla probablemente será una de las herramientas de diagnóstico más útiles.

---

# Fase 3 — Candidate generation

## Experimento 6 — Curva de recall

Medir:

```text
Recall@10
Recall@25
Recall@50
Recall@100
Recall@200
Recall@500
```

---

## Experimento 7 — Distribución del rank correcto

Para cada pregunta:

```text
Correct chunk rank
```

Visualizar la distribución:

```text
Questions
│
│ ████  rank 1–10
│ █████ rank 10–50
│ ███   rank 50–100
│ ██    rank 100–200
│ █     rank >200
└──────────────────────
```

---

# Fase 4 — Reranker

## Experimento 8

```text
Candidates = 50
```

## Experimento 9

```text
Candidates = 100
```

## Experimento 10

```text
Candidates = 200
```

Medir:

```text
Hit@1
Hit@5
MRR
NDCG@5
```

---

# Fase 5 — Query gap

## Experimento 11

```text
Original
vs
Legal rewrite
```

---

## Experimento 12

```text
Original
vs
Multi-query
```

---

## Experimento 13

```text
Original
vs
HyDE
```

---

# Fase 6 — Cambiar modelos

Solo después de entender el failure mode.

## Experimento 14

```text
Embedder A
Embedder B
Embedder C
```

---

## Experimento 15

```text
Reranker A
Reranker B
Reranker C
```

---

# 3. Árbol de decisión

```text
                    BAD RETRIEVAL
                          │
                          ▼
              Is gold chunk in corpus?
                          │
                   NO ───┴─── YES
                   │            │
                   ▼            ▼
               CORPUS      Is chunk clean?
                              │
                       NO ─────┴──── YES
                       │              │
                       ▼              ▼
                   CHUNKING      Rank <= 200?
                                      │
                              NO ─────┴──── YES
                              │              │
                              ▼              ▼
                     RETRIEVER / QUERY    Reranker
                                          │
                                  Does reranker improve?
                                          │
                                  NO ──────┴──── YES
                                  │               │
                                  ▼               ▼
                              RERANKER       CANDIDATE
                                             POOL
```

---

# 4. Ranking actual de sospechosos

Basado en los resultados observados hasta ahora:

```text
🥇 Query semantic gap / colloquial language
🥈 Candidate pool too shallow
🥉 Dense embedding ranking precision
4️⃣ Hybrid fusion / RRF configuration
5️⃣ Benchmark false negatives
6️⃣ Near-duplicate chunks
7️⃣ Reranker quality
8️⃣ Chunking
```

> Este ranking es una hipótesis de trabajo, no una conclusión definitiva.

---

# 5. Principio experimental

Para hacer el diagnóstico de forma científica:

```text
Experiment | Hypothesis | Variable changed | Metric | Result | Conclusion
```

## Regla principal

> **No cambiar más de una variable importante por experimento.**

Ejemplo:

❌ Malo:

```text
Cambiar embedder
+ chunking
+ reranker
+ RRF
```

No sabrás qué produjo la mejora.

✅ Bueno:

```text
Baseline
```

↓

```text
Solo cambiar candidate pool: 50 → 200
```

↓

```text
Solo agregar query rewrite
```

↓

```text
Solo cambiar embedder
```

---

# 6. Resultado final que buscamos

Después de los experimentos deberías poder hacer una afirmación como:

> **El X% de los fallos proviene de candidate generation. Dentro de ellos, el failure mode dominante es `colloquial_to_legal`. Query rewriting aumentó Recall@100 de X a Y. El reranker mejoró MRR únicamente cuando el gold chunk estaba dentro del candidate pool. BM25 ayudó principalmente en queries con alto overlap léxico y perjudicó parte del subconjunto coloquial.**

Ese sería un diagnóstico real del sistema, en lugar de simplemente decir:

> “El RAG no funciona.”

---

# 7. Experimentos prioritarios

Si hubiera que empezar mañana, el orden recomendado sería:

1. **Validar los gold chunks.**
2. **Validar el benchmark y buscar false negatives.**
3. **Verificar normalización y similarity implementation.**
4. **Medir resultados por `difficulty`.**
5. **Medir resultados por `type`.**
6. **Construir la curva Recall@10 → Recall@500.**
7. **Probar reranker con candidates 50, 100 y 200.**
8. **Comparar Original vs Legal Rewrite.**
9. **Comparar Dense vs BM25 vs Hybrid por tipo.**
10. **Probar weighted RRF.**
11. **Probar multi-query retrieval.**
12. **Comparar embedders.**
13. **Comparar rerankers.**
14. **Experimentar con chunking y metadata.**
15. **Probar HyDE.**

---

# Conclusión

La evidencia actual sugiere que el sistema probablemente no tiene un único culpable.

El objetivo de estos experimentos es separar el problema en componentes:

```text
Corpus
   ↓
Chunking
   ↓
Query formulation
   ↓
Embedding
   ↓
Candidate generation
   ↓
Fusion
   ↓
Reranking
   ↓
Evaluation
```

Solo después de identificar **en qué etapa se pierde el gold chunk** tiene sentido optimizar esa parte.

La prioridad actual es descubrir si el problema dominante es:

1. **la pregunta**;
2. **el embedder**;
3. **el candidate pool**;
4. **la fusión híbrida**;
5. **el reranker**;
6. **o la evaluación misma**.
