# Round 1 results, and what legally trained participants did with wrong-state answers

*Text for the manuscript, in English. Data: round 1 (study `piloto_penal`, definition version 7), last message 15 October
2026. Aggregates only; no participant text. Participant-level bootstrap, 4000 replicates, 95% CI. Source at the end.*

---

## Data and exclusions

- 43 participants: 12 in the pilot phase, 15 with the formal prompt and 16 with the plain prompt (random assignment in
  the main phase). 33 finished the study; 100 situations have a completed questionnaire; 105 first answers.
- **Excluded: 2 participants** who entered on 21 October, 1 and 4 minutes after a team member edited the round-1 study
  definition (version 9). Their profile answers use age ranges that exist only in version 9, so they saw a different
  version and were almost certainly tests. Together they had 1 completed situation and 2 first answers. Earlier
  drafts included them; the numbers below do not.
- Legal training: law students recruited through the law-school contact, or a profile answer of law as field of study or
  work. 15 participants with legal training (12 with at least one completed situation), 26 without.
- "The photos" is scored with the rule in `recalificacion_fotos.md` (extortion or Querétaro art. 167 Quinquies).

## Table 1R. Round 1 by prompt (all participants)

| | Formal | Plain | Pilot | All |
|---|---|---|---|---|
| Participants with at least one situation | 14 | 15 | 12 | 41 |
| First answer names another state's penal code | 58% (of 40) | 38% (of 39) | 69% (of 26) | **53% (56 of 105)** |
| Any answer in the situation names another state's code | 65% | 44% | 77% | 60% |
| First answer cites the correct law | 70% | 82% | 73% | 75% |
| First answer cites the correct article | 45% | 67% | 42% | 52% |
| Recall@10, first message | 21% | 31% | 27% | 26% |
| Comprehension (share of questions answered correctly) | 76% | 73% | 70% | 74% |
| Self-rated confidence (1–5) | 4.2 | 4.0 | 3.7 | 4.0 |
| Would act on the answer ("yes") | 54% | 62% | 59% | 58% |
| Noticed a problem ("yes") | 8% | 18% | 9% | 12% |

Origin of the wrong-state codes (all round-1 answers, not only first answers): 117 of the 118 other-state penal codes
named, in 74 answers, belonged to a passage in the context the assistant received; the model did not invent them. With
the 2 excluded test participants the count was 120 of 121, in 76 answers.

Wrong-state first answers, 95% CI: all 53% [42, 65]; without legal training 68% [57, 79]; with legal training 27%
[12, 45]. Difference, with − without legal training: −41 points [−60, −19].

## Table 2R. Willingness to act and noticing a problem, by whether an answer in the situation named another state's code

Completed situations. "With error" = at least one assistant answer in the situation named another state's penal code.

| | Without legal training | With legal training |
|---|---|---|
| Participants (with at least one situation with an error) | 22 (21) | 12 (8) |
| Situations with / without an error | 46 / 18 | 13 / 23 |
| Would act: "yes", with vs without error | 63% vs 67%; −4 [−31, +20] | **23% vs 61%; −38 [−72, 0]** |
| Would act: "no" | 15% vs 6% | 31% vs 17% |
| Would act: "not sure" | 22% vs 28% | 46% vs 22% |
| Noticed a problem: "yes" | 9% vs 6%; +3 [−9, +17] | 15% vs 22%; −6 [−40, +28] |
| Noticed a problem: "not sure" | 28% vs 28% | 31% vs 13% |

## What this supports, and what it does not

Participants without legal training acted on wrong-state answers as often as on correct ones and rarely noticed a
problem. The error was invisible to them.

Participants with legal training were less willing to act when an answer named another state's code. Three
observations limit how far this goes:

1. **Mostly "not sure", not "no".** Of the 13 situations with an error, they answered "yes" in 3, "no" in 4 and "not
   sure" in 6.
2. **They did not report the error.** They were no more likely to say they noticed a problem (15% vs 22%). In their
   free-text comments on these situations, none mentioned the state, jurisdiction or the code cited. The reasons they
   gave were general: the answer was generic or did not follow a thread, the law and whether it is in force should be
   checked, or a lawyer should be consulted.
3. **Small and concentrated.** 12 participants, 8 of whom saw an error; two of them received a wrong-state answer in
   all three situations and contribute 6 of the 13 situations. Among the 6 participants with situations both with and
   without an error, 3 were less willing to act in the situation with the error, 3 answered the same, and none was more
   willing.

The data therefore support hesitation without attribution, not recognition of the error. The wrong-state answers may
also have been the most confusing ones, which would explain "not sure" without the participants naming the state; the
data cannot separate the two.

## Required edits to the manuscript

1. **Every round-1 number** (abstract, Sections 5.1–5.3, Table 3): use the numbers above and in the JSON files of this
   folder. The main changes from the previous draft are 57 of 107 → **56 of 105** first answers (still 53%), and for
   legally trained participants 23% vs 58% (−35 [−66, 0], 13 participants) → **23% vs 61% (−38 [−72, 0], 12
   participants)**.
2. **Contribution 1 and Section 5.2.** Replace "legally trained participants did notice the error" (or "felt but not
   named") with:

   > Legally trained participants were less willing to act on answers that cited another state's code (23% vs 61%;
   > −38 points, 95% CI −72 to 0), mostly by answering "not sure" rather than "no". They were not more likely to report
   > a problem, and none mentioned jurisdiction in their free-text comments; they cited generic or confusing answers and
   > the need to verify the law or consult a lawyer. The difference rests on 12 participants, two of whom received a
   > wrong-state answer in all three situations. We read it as unease the participants did not attribute to its cause,
   > not as recognition of the error.

   In the list of contributions: "invisible to lay users, and producing unease but not recognition among legally
   trained users".
3. **Data section.** Add: "Two round-1 participants who entered after the study definition was edited (21 October)
   were excluded as tests of the new version."
4. **Section 8 (future work).** Add a round-3 item: after "would you act on this answer?", ask why not, with options
   that include "it cited the law of another state".

## Source

| Table | Source |
|---|---|
| 1R | `06_evaluation/paper_2026-11-03/resultados_ronda1.py` → `resultados_ronda1.json` (`por_condicion`, `1a_otro_estado_ic95`, `con_menos_sin_formacion_ic95`) |
| 2R | same file, `actuaria_segun_error_de_estado`; `actuar_segun_error.py` gives the same rates |
| Free-text comments | read by one author in the study database; not published (participant text) |
| Exclusion | `analisis_ronda2.py`, `FIN_RONDA1`; used by every script that loads round 1 |
