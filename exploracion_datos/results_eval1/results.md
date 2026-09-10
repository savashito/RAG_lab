# Resultados — evaluación de recuperación

- Test set: `golden_eval1_penal.json` · preguntas: 54 · chunks: 3616
- Embeddings (caché): `Qwen/Qwen3-Embedding-0.6B` · TEI sirve: `Qwen/Qwen3-Embedding-0.6B`
- Métodos: denso, bm25, híbrido · k = [5, 10, 20]
- Generado: 2026-09-09T20:07:22+00:00

## Global (todas las preguntas)

|  | denso | bm25 | híbrido |
| --- | --- | --- | --- |
| n | 54.0 | 54.0 | 54.0 |
| recall@5 | 0.685 | 0.426 | 0.611 |
| recall@10 | 0.741 | 0.5 | 0.685 |
| recall@20 | 0.852 | 0.574 | 0.833 |
| MRR | 0.533 | 0.309 | 0.454 |

## Por dificultad — híbrido

|  | easy | medium | hard |
| --- | --- | --- | --- |
| n | 8.0 | 35.0 | 11.0 |
| recall@5 | 0.25 | 0.714 | 0.546 |
| recall@10 | 0.25 | 0.829 | 0.546 |
| recall@20 | 0.75 | 0.914 | 0.636 |
| MRR | 0.296 | 0.554 | 0.252 |

## Por tipo — híbrido

|  | conceptual_distinction | direct_concept | direct_fact | direct_principle | semantic_paraphrase |
| --- | --- | --- | --- | --- | --- |
| n | 1.0 | 27.0 | 14.0 | 3.0 | 9.0 |
| recall@5 | 0.0 | 0.704 | 0.714 | 0.0 | 0.444 |
| recall@10 | 0.0 | 0.815 | 0.786 | 0.0 | 0.444 |
| recall@20 | 1.0 | 0.963 | 0.857 | 0.667 | 0.444 |
| MRR | 0.071 | 0.488 | 0.693 | 0.067 | 0.154 |

## 10 peores preguntas — híbrido

- rank 550 · [easy] ¿Qué finalidades tiene el proceso penal acusatorio?
- rank 396 · [medium] ¿Cómo se extingue la pretensión punitiva?
- rank 126 · [hard] ¿Qué se entiende por verdad material?
- rank 58 · [medium] ¿En qué término se debe dictar el auto de vinculación a proceso?
- rank 49 · [hard] En el caso de que existan violaciones al derecho de defensa adecuada, ¿qué figura jurídica procede y qué condición se requiere para que proceda?
- rank 39 · [hard] Una vez iniciada la investigación en sede ministerial, ¿en qué término el Ministerio Público debe determinar la situación jurídica del detenido?
- rank 38 · [hard] ¿Cuál es el papel de la víctima en el modelo abolicionista?
- rank 25 · [medium] ¿Cuál es el primer acto procesal en que intervienen las partes contrarias en la audiencia de juicio oral?
- rank 21 · [easy] Desarrolla el contenido y alcance del principio de concentración.
- rank 20 · [medium] ¿En qué plazo se debe presentar la acusación coadyuvante?
