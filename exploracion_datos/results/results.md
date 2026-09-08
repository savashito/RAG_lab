# Resultados — evaluación de recuperación

- Test set: `golden_penal.json` · preguntas: 34 · chunks: 3616
- Embeddings (caché): `Qwen/Qwen3-Embedding-0.6B` · TEI sirve: `Qwen/Qwen3-Embedding-0.6B`
- Métodos: denso, bm25, híbrido, multi-query · k = [5, 10, 20]
- Generado: 2026-09-08T21:03:02+00:00

## Global (todas las preguntas)

|  | denso | bm25 | híbrido | multi-query |
| --- | --- | --- | --- | --- |
| n | 34.0 | 34.0 | 34.0 | 34.0 |
| recall@5 | 0.176 | 0.118 | 0.235 | 0.265 |
| recall@10 | 0.294 | 0.176 | 0.353 | 0.441 |
| recall@20 | 0.412 | 0.265 | 0.441 | 0.588 |
| MRR | 0.176 | 0.075 | 0.176 | 0.196 |

## Por dificultad — híbrido

|  | easy | medium | hard | very_hard |
| --- | --- | --- | --- | --- |
| n | 2.0 | 9.0 | 18.0 | 5.0 |
| recall@5 | 0.5 | 0.333 | 0.111 | 0.4 |
| recall@10 | 0.5 | 0.444 | 0.222 | 0.6 |
| recall@20 | 1.0 | 0.444 | 0.333 | 0.6 |
| MRR | 0.525 | 0.099 | 0.103 | 0.439 |

## Por tipo — híbrido

|  | causal_reasoning | colloquial_to_legal | conceptual_distinction | conceptual_reasoning | direct_concept | direct_principle | legal_paraphrase | multi_concept_reasoning | negative_question | precise_conceptual_retrieval | semantic_paraphrase |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| n | 2.0 | 5.0 | 7.0 | 2.0 | 1.0 | 1.0 | 1.0 | 1.0 | 3.0 | 1.0 | 10.0 |
| recall@5 | 0.0 | 0.0 | 0.0 | 0.5 | 1.0 | 0.0 | 0.0 | 0.0 | 0.333 | 0.0 | 0.5 |
| recall@10 | 0.0 | 0.0 | 0.143 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 0.333 | 0.0 | 0.6 |
| recall@20 | 0.0 | 0.0 | 0.286 | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 0.667 | 0.0 | 0.6 |
| MRR | 0.011 | 0.005 | 0.038 | 0.238 | 1.0 | 0.05 | 0.007 | 0.167 | 0.363 | 0.006 | 0.289 |

## 10 peores preguntas — híbrido

- rank 1781 · [medium] Si la policía obtiene una prueba violando derechos, ¿esa prueba puede usarse en el juicio?
- rank 565 · [hard] Si los policías consiguieron algo importante para inculparme pero lo obtuvieron violando mis derechos, ¿todavía lo pueden usar?
- rank 540 · [hard] ¿Por qué una entrevista tomada durante la investigación no puede simplemente copiarse en una sentencia?
- rank 487 · [medium] ¿Puede la víctima llegar a un arreglo con el acusado para resolver el asunto sin llegar a juicio?
- rank 344 · [hard] ¿Puede algo ser útil para orientar una investigación sin haber alcanzado todavía el nivel de prueba?
- rank 285 · [hard] Si los policías agarran a alguien y no lo dejan ir, ¿qué límite legal existe para que eso no sea arbitrario?
- rank 180 · [hard] ¿Me pueden volver a acusar por algo de lo que ya salí absuelto?
- rank 176 · [hard] ¿Puede mi abogado pelearse legalmente con las pruebas que presenta el Ministerio Público?
- rank 174 · [medium] ¿Qué permite que la defensa cuestione la evidencia utilizada por la fiscalía?
- rank 160 · [very_hard] ¿Qué distingue a un elemento que solo permite orientar una inferencia de uno que puede utilizarse formalmente para acreditar un hecho en una sentencia?
