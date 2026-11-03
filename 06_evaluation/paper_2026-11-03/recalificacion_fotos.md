# Re-scoring "the photos" in both rounds: corrections for the manuscript

*Text for the manuscript, in English. Data: rounds 1 and 2 frozen at 2 November 2026, 22:35 UTC (last participant
activity 20:20 UTC; 81 round-2 participants, 192 completed situations). Round 1 excludes 2 participants who entered
after its definition was edited on 21 October (tests of the new version; see `resultados_ronda1.md`). The current draft
uses data frozen at 09:27 UTC and includes those 2 participants, so some "before" values differ slightly from the draft.
Use the "after" column. Aggregates only; no participant text. Sources at the end.*

---

## The scoring rule

On 14 October 2026, after the legal expert's review, the team decided how to score "the photos" (Cris is asked for
5,000 pesos under threat of publishing intimate photos). **Either** of these counts as correct:

- extortion under the General Law on Extortion (art. 15, aggravated under art. 17);
- Querétaro Penal Code art. 167 Quinquies (threatening to disseminate intimate images obtained with or without consent).

The scenario's own reference text already calls art. 167 Quinquies applicable. Querétaro art. 167 Quáter (obtaining
images *without* consent) remains incorrect, because Cris sent the photos voluntarily.

The rule applies to two measures, in both rounds:

1. **The participant's answer** to "which offence and which law apply to Cris?": options `lg_15` (extortion) and
   `qro_167quinquies` are both correct.
2. **What the assistant cites:** art. 167 Quinquies is an accepted alternative to art. 15 of the General Law on
   Extortion. "Cites the correct law/article" means citing either one; for recall@10, retrieving either one counts.

The previous analyses applied the rule inconsistently. The round-1 definition was updated to include it on 21 October
(version 9), after the round had closed, and the round-2 definition was created from an earlier copy without it. The
draft's analyses then pinned round 1 to version 7, which also dropped it. All numbers below apply the rule to both
rounds, during scoring only; the participant-facing study did not change.

## Table R1. Numbers that change

"Before" = previous scoring (extortion only); "After" = the rule above. Same data in both columns. Participant-level
bootstrap, 4000 replicates, 95% CI.

| Measure | Before | After | Does the conclusion change? |
|---|---|---|---|
| Participants answering "which law" correctly in "the photos", round 1 | 26% (of 34) | **56%** | — |
| Same, round 2 | 40% (of 63) | **75%** | — |
| Comprehension in "the photos", round 1 / round 2 | 53% / 61% | 68% / 79% | — |
| **Bridge (Table 3), participants without legal training, formal prompt: comprehension, round 1 → round 2** | 61% → 63%; +2 [−18, +22] | **64% → 69%; +5 [−16, +26]** | No: still no detectable change |
| Bridge, without legal training: first answer cites the correct law, round 1 → round 2 | 63% → 65%; +1 | 74% → 67%; −7 [−27, +14] | No |
| **Bridge, with legal training: first answer cites the correct law, round 2 − round 1** | **+31 [6, 56]** | **+22 [−6, +52]** | **Yes: no longer a clear difference** |
| Bridge, with legal training: first answer cites the correct article, round 2 − round 1 | +40 [11, 65] | +30 [2, 59] | No: still positive, interval close to zero |
| **Test 1: participants answer "which law" correctly when the assistant cited the expected article vs. when it did not (all)** | 64% vs 38%; +26 [12, 39] | **80% vs 53%; +27 [14, 40]** | No: holds |
| Test 1, participants without legal training | +22 [6, 39] | +27 [11, 42] | No: stronger |
| Test 1, participants with legal training | +32 [8, 55] | +25 [2, 49] | No |
| Round-2 comprehension by prompt (original / new / intermediate) | 65% / 73% / 68% | 69% / 79% / 75% | No: no clear difference between prompts |
| From 29 Oct, without legal training: comprehension, intermediate − original | +9 [−10, +28] | +12 [−8, +31] | No |
| Round 2: first answer cites the correct law, by prompt (original / new / intermediate) | 70% / 69% / 68% | 73% / 73% / 70% | No: equal across prompts |
| Recall@10 of the first message, message names the state vs. does not | 56% vs 15% | 61% vs 16% | No |
| Recall@10 in the message where a participant without legal training gave the state (round 2) | 59% | 68% | No: stronger |

## Numbers that do not change

- **Wrong-state citations** (strict metric, the paper's): round 1, 53% of first answers (57 of 107); round 2, 4%. The
  strict metric allows the code of the state where the facts occurred, independently of the answer key.
- **Willingness to act, noticing a problem, trust, and self-rated confidence:** they do not depend on the answer key.
- **The jurisdiction gate evaluation, the prompt-feature analysis, and the "buried question" analysis.**

## Required edits to the manuscript

1. **Abstract and Section 5.4.** Replace "their comprehension did not change detectably (61% vs 63%)" with "their
   comprehension did not change detectably (64% vs 69%)".
2. **Table 3 (bridge).** Update the comprehension and "first answer cites the correct law" rows. Remove the bold and any
   claim based on "+27 [1, 53]" for legally trained participants; it is now +22 [−6, +52].
3. **Test 1 (Section 5.8 and abstract).** Replace "64% … and in 32%" with "80% … and in 53%", and "+32 [20, 45]" with
   "+27 [14, 40]". For participants without legal training, use +27 [11, 42].
4. **Section 5.8, "The answer key" paragraph.** Replace it with:

   > **The answer key in "the photos".** Two answers are legally defensible: extortion under the General Law on
   > Extortion, and Querétaro art. 167 Quinquies (threatening to disseminate intimate images), which the scenario's
   > reference text calls applicable. Following the legal expert's review, we score either as correct, both for the
   > participant's answer and for the article the assistant cites, in both rounds. Participants chose the two almost
   > equally often (round 1: 9 and 10 of 34; round 2: 25 and 22 of 63). With this rule, 56% of round-1 and 75% of
   > round-2 participants answered this question correctly.

   Delete "⚠ The legal expert must decide whether the paper scores art. 167 Quinquies as correct."
5. **Section 4 (the photos).** Replace "Correct law: extortion under the General Law on Extortion, arts. 15 and 17;
   Querétaro art. 167 Quinquies is also relevant." with "Correct law: extortion under the General Law on Extortion,
   arts. 15 and 17, or Querétaro art. 167 Quinquies (either is scored as correct)." In the definition of comprehension,
   delete "which the answer key itself calls relevant but scores as incorrect".
6. **Appendix C.** Replace it with:

   > **Appendix C. The answer key in "the photos".** The study definition participants saw in round 1 (version 7) and
   > the round-2 definition list only the General Law on Extortion as correct. On 14 October, after the legal expert's
   > review, the team decided to accept Querétaro art. 167 Quinquies as well; the round-1 definition was updated on
   > 21 October (version 9), after the round had closed, and the round-2 definition was created from an earlier copy
   > without the change. Participants saw the same answer options in both rounds; only the scoring differs. All numbers
   > in this paper apply the rule in Section 5.8 to both rounds at analysis time.

7. **Appendix B.** Delete "(inflates round 2 from 4% to about 14% of first answers)". With art. 167 Quinquies among the
   expected articles, the dashboard metric no longer counts Querétaro's code as another state in "the photos".
8. **Table 2 (replay).** Remove the ⚠ in Appendix C about the replay's "correct law" row only after checking which
   answer key the replay used. *Not yet verified.*
9. **Every round-2 number.** Update all tables together from the same freeze (22:35 UTC on 2 November). The source
   files listed in Appendix A were regenerated with this freeze and the scoring rule.

## Sources

| Item | Source |
|---|---|
| Scoring rule | `06_evaluation/paper_2026-11-03/analisis_ronda2.py` (`CLAVE_FOTOS`, `LEY_FOTOS_CORRECTAS`, `GOLD_167Q`); every analysis script loads data through it. `CLAVE_FOTOS=solo_lg15` reproduces the previous scoring. |
| Table R1 | `06_evaluation/paper_2026-11-03/recalificacion_fotos/antes/*.txt` and `despues/*.txt`; every changed value is listed in `cambios.txt` |
| All paper tables | The JSON files in `06_evaluation/paper_2026-11-03/` (Appendix A), regenerated at the 22:35 UTC freeze with the scoring rule (`CORTE='2026-11-02 22:35:00'`) |
