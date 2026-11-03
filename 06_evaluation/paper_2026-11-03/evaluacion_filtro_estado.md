# Independent evaluation of the jurisdiction gate (response to Major concern 2)

*Text for the manuscript, in English. Data: component test run 32 (25 October 2026) and round-2 study turns (frozen
2 November 2026). Sources at the end. Aggregates only; no participant text.*

---

## What the gate does, and what it does not do

The jurisdiction gate is a restriction on retrieval, not a legal determination of competence. Before retrieval, an LLM
reads the user's messages (plus, in a follow-up, the single sentence in which the assistant asked where the facts
occurred) and labels each place it finds with one of two roles: *place of the facts*, or *a place mentioned for another
reason* (where the person lives, works or comes from). It also classifies whether the matter looks federal and whether
the question is theoretical. Retrieval is then restricted to:

- the penal code of the state where the facts occurred;
- national and general laws;
- the Federal Penal Code, **only** when the LLM classifies the matter as federal (or the question as theoretical).

If the user names no place of the facts, no state penal code can be retrieved and the assistant asks where the facts
occurred. If the user mentions only where they live or work, that state's code is retrieved as a hypothesis and the
answer must say so and ask where the facts occurred. If the user names a state whose code is not in the corpus, the
assistant says so and answers only with laws that apply nationwide.

The gate does not apply rules of territorial or subject-matter competence. When the facts occurred in more than one
state, it retrieves each state's code and the assistant answers for each, without deciding which one is competent.

> **Correction to the current manuscript (Section 4, "Round 2 configuration").** The text says retrieval is restricted
> to "that state's code plus federal and general law". The Federal Penal Code is included only when the gate classifies
> the matter as federal. National and general laws are always included.

## Evaluation 1: test cases with a known answer

We evaluated the gate as a separate component on 263 test cases, each with the expected output and no LLM judge. The
cases were written by the authors, partly from real assistant answers. The version used in round 2 was correct in 256 of 263 cases (97%).

**Table G1. Jurisdiction gate on test cases (version used in round 2).**

| Case type | Cases | Correct |
|---|---|---|
| Identifies the state mentioned (one message) | 81 | 81 |
| Theoretical question, no concrete facts | 12 | 12 |
| Role of the place: facts vs. where the person lives or works (one message) | 14 | 12 |
| Matter type: federal, state, or national law | 44 | 39 |
| Reply to the assistant's question: city, neighbourhood, abbreviated state, state only, only where they live, "I don't know where" | 60 | 60 |
| Reply mentions the place of the facts and where the person lives | 10 | 10 |
| Reply names a state whose code is not in the corpus | 10 | 10 |
| Distractors: family's state of origin, visiting another state, says where they work (facts online), says where they are from | 20 | 20 |
| Two-message controls (answers only the place; place plus other facts; assistant did not ask) | 12 | 12 |
| **Total** | **263** | **256 (97%)** |

**Table G2. Place of the facts: confusion on the 126 test cases that state it.**

| Expected \ Gate output | Correct state as place of the facts | Another state as place of the facts | No place of the facts |
|---|---|---|---|
| A state is the place of the facts (84) | 82 | **0** | 2 |
| No place of the facts given (42) | **0** | **0** | 42 |

No test case labelled a state as the place of the facts when it was not. That is the error that reproduces the
original problem: the assistant citing the code of a state that may not apply. The two misses go in the opposite
direction. In both, the facts occurred at the person's home or workplace ("I live in Toluca and a neighbour entered my
house"; "I work in Morelos and my boss pressures me…"), and the gate labelled the state as where the person lives or
works. In that case the system offers that state's code as a hypothesis and asks where the facts occurred.

**Table G3. Federal matters (10 test cases with a federal crime, 34 without).**

| Expected \ Gate output | Classified federal | Not classified federal |
|---|---|---|
| Federal crime (10) | 6 | **4** |
| Not a federal crime (34) | 0 | 34 |

Federal classification is the gate's main weakness. It missed counterfeit money, an illegal fireworks workshop, logging
in a protected natural reserve, and an assault by a National Guard officer. In those cases the Federal Penal Code is
left out of retrieval. One further case (police beating a detainee to obtain a statement) was wrongly marked as
depending on the state.

## Evaluation 2: the gate in the real round-2 conversations

The deployed system did not log the gate's decision for each message. We reconstructed it from the retrieved
candidates: for each of the 375 messages that participants sent in round 2, we recorded which state penal codes appeared
among the 50 candidates the retriever returned after filtering. We compared that with the state where the participant
said the facts occurred in their messages up to that point. First, a regular expression located every state name. The
277 messages where the states named and the codes retrieved agreed were accepted automatically. For the other 98, a
legal expert on the team (an author), blind to the gate's output, read each message with the participant's earlier
messages and coded the place of the facts (3 November 2026).

**Table G4. Jurisdiction gate in 375 real round-2 messages (three situations).**

| Place of the facts, as the participant described it \ State codes retrieved | Only that state's code | Another state's code | No state code |
|---|---|---|---|
| Querétaro (178) | 171 | **0** | 7 |
| Mexico City (45) | 45 | **0** | 0 |
| State of Mexico (10) | 10 | **0** | 0 |
| Compares two states in the corpus (1) | 1 (both) | 0 | 0 |
| No place of the facts given (141) | — | **0** | 141 |

The gate never let through the code of a state other than the one where the participant placed the facts (0 of 375).
It followed what participants wrote, not the scenario: when participants placed a situation in Mexico City or the State
of Mexico, it retrieved that state's code. In 76 messages of the summons situation, the conversation up to that message mentioned both Querétaro
and Mexico City. In 74, the gate retrieved only Querétaro's code. In one, the participant placed the fight in Mexico
City and said they were from Querétaro, and the gate retrieved only Mexico City's code, following the participant's
account. The remaining one is one of the two follow-ups that did not inherit the place (no state code). This is the
distinction a reviewer might worry it confuses (residence vs. place of the facts). When a participant mentioned only where they live, the code
of that state is retrieved by design as a hypothesis (see above). Messages that named only one state and retrieved only
that state's code were accepted automatically and are counted under that state, whether the participant described it
as the place of the facts or as their residence.

The gate missed in seven messages, all by retrieving no state code where the coder placed the facts in Querétaro.
Two were follow-up messages that did not mention a place (a closing remark and a detail about the summons) and did not
inherit the state named earlier. Five were in the photographs situation: the participant said they were in, lived in,
or had a partner in Querétaro, and the gate did not treat that as the place of the facts. The expected law in that
situation is a general law that applies nationwide, but Querétaro art. 167 Quinquies is also accepted, so these misses
could withhold an accepted answer. The gate retrieved the expected code in 368 of 375 messages (98%) and another
state's code in none.

## Limits of this evaluation

1. **The test cases are not independent of development.** The authors wrote them and adjusted the gate's prompt using
   the same cases. Table G4 uses messages the gate had not seen, but in three situations designed by the authors.
2. **One coder.** The place of the facts in the 98 flagged messages was coded by one legal expert, blind to the gate's
   output; agreement between coders was not measured. The 277 messages where the regular expression and the retrieved
   codes agreed were not read by a person.
3. **Reconstructed decisions.** Table G4 infers the gate's decision from the 50 retrieved candidates. A state allowed
   by the gate whose code produced no candidate would be counted as "no state code".
4. **Untested cases.** All three study situations occur in a single state and none is a federal crime. Neither the test
   set nor the study contains conduct spanning several jurisdictions, crimes committed at a distance, or concurrence of
   federal and state jurisdiction. We do not claim the gate determines the applicable law in those cases.

## Proposed changes to the manuscript

1. Add Tables G1–G4 (or G2–G4 in the main text and G1 in an appendix) to Section 5.3, under "The gate as a component".
2. Correct the description of the gate in Section 4 (Federal Penal Code only for federal matters).
3. State explicitly that the gate restricts retrieval and does not determine competence; keep the distinction between
   "does not cite another state" and "cites the applicable law", which Table 2 already reports separately.
4. Add limitations: weak federal classification (6 of 10); no multi-jurisdiction, at-a-distance, or concurrent-
   jurisdiction cases; test cases written by the authors; one coder.
5. Future work: a held-out test set written by a lawyer who did not see the gate's prompt, with territorial-competence,
   multi-state, and federal cases.

## Sources

| Table | Source |
|---|---|
| G1–G3 | Component test "filtro_metodos", run 32 (25 Oct 2026), production table `comp_resultados`; version "v2 · + the sentence where the assistant asked for the place"; `apps/rewrite_lab/componentes.py` (`eval_filtro`, `errores_lugar`) |
| G4 | `06_evaluation/paper_2026-11-03/filtro_en_conversaciones_reales.py` → `filtro_real.json` (regular-expression matrix), plus blind coding of the 98 discordant messages by one legal expert (the coded spreadsheet contains participant text and is kept outside the repository) |
| Gate logic | `apps/rewrite_lab/jurisdiction_gate.py` (`decidir`) |
