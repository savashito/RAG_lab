# FAccT 2027 — abstract v3 (25-oct-2026)

Deadlines: abstract **2026-10-27**, paper 2026-11-03 (AoE). Anonymous: no names, URLs or project names.
Focus areas: Evaluations and evaluation practices (primary), System development and deployment, Law and policy.

Changes from v2 (`facct_abstract_v2.md`, 24-oct): (1) the gap by legal training (who notices the error vs who would act);
(2) the second applicability condition: who the person is, not only where the facts occurred; (3) the reranker's
separate effect; (4) round 2 described as it is now (open, prompt assigned randomly, starting 25-oct). Shorter
evaluation-apparatus sentence.

## Title (options)

1. **Where You Are and Who You Are: Applicability Errors in a Legal RAG Assistant, Audited with Its Users**
2. The Right Law from the Wrong State: Auditing and Repairing Jurisdiction Errors in a Legal RAG Assistant
3. Whose Law Applies? Jurisdiction Errors, User Blindness and Fragile Evaluation in Legal RAG

## Abstract (~310 words)

Retrieval-augmented generation (RAG) is promoted to widen access to legal information, yet it is usually evaluated
with questions written by experts. In Mexico, criminal law is split across a
federal code, a national procedural code and 32 state penal codes, so whether a law applies depends on where the facts
occurred. We audit an open-weight, locally hosted RAG assistant over Mexican criminal law (51 sources, 8,557 passages)
with 45 participants (26 without legal training, 19 with it) who consulted it in their own words about three fictional
situations. In 57% of first answers the assistant named the penal code of a state other than the one where
the facts occurred, and in 120 of 121 cases that code came from retrieval, not from the model. Participants without legal training noticed a problem in 8% of situations (19% with legal training), yet more
often said they would act on the answer (64% vs 46%). A jurisdiction gate, an LLM step that identifies where the facts occurred and restricts retrieval to that state's
code plus national law, was replayed on all 108 real conversations: answers naming another state's code fall from 60% to 2% (−58 points, 95% CI −66 to −50), with no loss
in citing the correct law; adding a reranker raises correct-article citations in follow-up turns (+13 points, 95% CI
2 to 25). The repair exposed a second applicability condition: in a gender-neutral extortion scenario, answers citing
a law that protects only women rose from 13% to 33%. Our own place-name metrics also misled us, scoring correct
explanations as errors. A second round with the repaired system, randomly assigning each participant one of two
prompts, is under way. We
argue that legal RAG must be evaluated with the people it is meant to serve, and that its metrics must check whether
a cited law applies to where they are and who they are.

### Round-2 sentence (choose one before submitting)

- **If round 2 has no results by Oct 27 (likely):** keep «A second round … is under way.»
- **If it has results:** «In a second round (N = [n]) with the repaired system, in which each participant was randomly
  assigned one of two prompts, wrong-state citations seen by participants fell to [x%]; the new prompt [raised / did
  not change] comprehension ([a%] vs [b%]).»

## Where each number comes from

| Claim | Number | Source |
|---|---|---|
| Corpus (round 1) | 51 sources, 8,557 passages | prod DB, topic derecho_penal_mexicano, 24-oct. Since 25-oct, 9 sources are turned off for search (42 sources, 6,766 passages): round 2 uses that; round 1 and all replays used the 51 |
| Participants | 45 (33 completed): 26 without legal training, 19 with it | `estudio_participantes`, study piloto_penal; classification by profile |
| Wrong-state code in first answers | 57% (24 of 42), legal-prompt condition | strict metric, `replay_ronda1_2026-10-24/metrica_estricta.py` |
| Came from retrieval | 120 of 121 wrong-state codes named (in 76 answers) were in the retrieved context | all round-1 answers, 24-oct |
| Noticed a problem / would act | without legal training 8% / 64% (64 situations); with legal training 19% / 46% (37 situations) | final round-1 data by profile (this session, 25-oct) |
| Gate on real conversations | 59.7% → 1.9% (replay B), −57.9 [−66.2, −49.5]; correct law 72.7% → 72.2% | «🔁 Ronda 1 real», runs #1–#2 (A) vs #4–#5 (B), 108 conversations × 2 reps |
| Reranker | correct article, follow-up turns: +13.0 [1.9, 25.0] (A → B + rerank); B → B + rerank: +10.5 [−0.6, 21.5]; wrong-state code unchanged (1.9% → 2.8%) | runs #12–#13 (B_filtro_rerank) |
| Women-specific law, gender-neutral scenario | answers in «fotos» citing the Ley General de Acceso de las Mujeres a una Vida Libre de Violencia, both repetitions: A 15 of 112 (13%), B (gate) 37 of 112 (33%), C (gate + new prompt) 36 of 112 (32%), B + rerank 38 of 112 (34%) | replay runs #1–#2, #4–#5, #6–#7, #12–#13, all turns of «fotos» |
| Place-name metric | correct «not Mexico City» answers counted as errors | `metrica_estricta.py`; `study/analisis.py` (corrected 24-oct) |

Numbers dropped from v2: «plain-language prompt raised willingness to act without improving comprehension» (small
samples, no test; the gap by legal training is the clearer finding), the benchmark-tuned gate rule and run-to-run
variation (they go in the paper, not the abstract).

## Before submitting

- [ ] Decide the round-2 sentence.
- [ ] Anonymity: no Tlacua, no legis.tlacua.cloud, no UNAM/Boston College/author names.
- [ ] Karen: is «legal training» the right term for the 19, and are the three situations described fairly?
