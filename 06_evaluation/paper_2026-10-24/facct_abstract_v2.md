# FAccT 2027 — abstract v2 (24-oct-2026)

Deadlines: abstract **2026-10-27**, paper 2026-11-03 (AoE). Anonymous: no names, URLs or project names.
Focus areas: Evaluations and evaluation practices (primary), System development and deployment, Law and policy.

## Title (options)

1. **The Right Law from the Wrong State: Auditing and Repairing Jurisdiction Errors in a Legal RAG Assistant**
2. Confident in the Wrong State: A User-Grounded Audit of Retrieval-Augmented Legal Assistance in Mexico
3. Whose Law Applies? Jurisdiction Errors, User Blindness and Fragile Evaluation in Legal RAG

## Abstract (~270 words)

Retrieval-augmented generation (RAG) is promoted as a way to widen access to legal information where legal aid is
scarce, yet it is usually evaluated with questions written by experts. In Mexico, criminal law is split across a
federal code, a national procedural code and 32 state penal codes, so a valid answer depends on citing the law of the
state where the facts occurred. We audit an open-weight, locally hosted RAG assistant over Mexican criminal law
(51 sources, 8,557 passages) with 45 participants — mostly university students without legal training, plus law
students — who consulted it in their own words about three fictional situations. In 57% of first answers the
assistant named the penal code of a state other than the one where the facts occurred; in 120 of 121 cases that code
had been retrieved into the model's context, not invented by the model. Participants reported noticing a problem
in only 12% of situations, and a plain-language prompt raised willingness to act without improving comprehension.
We then add a jurisdiction gate — an LLM step that identifies where the facts occurred and restricts retrieval to that
state's code plus national law — and replay all 108 real conversations from the study: answers naming another state's
penal code fall from 60% to 1% (−58 points, 95% CI −66 to −50), with no loss in citing the correct law. Along the way,
the evaluation apparatus repeatedly misled us: metrics that matched place names scored correct explanations
("Querétaro's courts, not Mexico City's") as errors; a gate rule tuned to an expert benchmark reintroduced the very
error that confused users; and run-to-run variation exceeded many reported gains. [ROUND 2 — see options below.] We
argue that legal RAG should be evaluated with the people it is meant to serve, using jurisdiction-aware metrics that
are themselves audited.

### Round-2 sentence (choose one before submitting)

- **If round 2 has no results by Oct 27 (likely):** «A second, randomized round with the repaired system is under
  way.» (Then report it in the paper if it finishes by Nov 3.)
- **If it has results:** «In a second, randomized round (N = [n]), the repaired system [reduced / did not reduce]
  wrong-state citations seen by participants to [x%] and comprehension [rose / did not change] ([a%] vs [b%]).»

## Where each number comes from

| Claim | Number | Source |
|---|---|---|
| Corpus | 51 sources, 8,557 passages | prod DB, topic derecho_penal_mexicano, 24-oct (after removing the INEGI classification) |
| Participants | 45 (33 completed); 12 pilot + 33 randomized | `estudio_participantes`, study piloto_penal |
| Wrong-state code in first answers | 57% (24 of 42), «actual» condition | strict metric, `replay_ronda1_2026-10-24/metrica_estricta.py` |
| Came from retrieval | 120 of 121 wrong-state codes named (in 76 answers) were in the retrieved context | all round-1 answers, 24-oct (strict metric + the context saved with each turn) |
| Noticed a problem | 12% of 101 situations | final round-1 data, 24-oct |
| Plain vs legal prompt | comprehension 68% vs 71%; would act 62% vs 52% | final round-1 data, 24-oct (n = 39 / 40 situations; small, no test yet) |
| Gate on real conversations | 59.7% → 1.4%, −58.3 [−66.2, −50.0]; correct law 72.7% → 72.2% | replay, 108 conversations, 2 reps (`replay_ronda1_2026-10-24/`) |
| Place-name metric | correct «not Mexico City» answers counted as errors; old «asks for state» regex: 16 of 31 false | `metrica_estricta.py`; `study/analisis.py` (corrected 24-oct) |
| Gate rule tuned to benchmark | v2 theory rule: 5 of 8 theory questions cited a state code; v3: 0 of 8 | report section 7 |
| Run-to-run variation | SD between repetitions 15–30 points per question | report section 8 |

## Before submitting

- [ ] Decide the round-2 sentence.
- [ ] Anonymity: no Tlacua, no legis.tlacua.cloud, no UNAM/Boston College/author names.
- [ ] Karen: is «law students» accurate for the legal-training group, and are the three situations described fairly?
