# Paper data package, 3 November 2026

*For the manuscript editor (ChatGPT) and co-authors. Everything here supersedes `paper_2026-10-31/`. Aggregates only:
no participant codes or text.*

## Rules applied to every number

| Rule | Detail |
|---|---|
| Data freeze | Study data up to **2 November 2026, 22:35 UTC** (`CORTE`). Round 2: 81 participants, 192 completed situations, last activity 20:20 UTC. Round 1 ended 15 October. |
| Round-1 exclusion | 2 participants who entered on 21 October after the round-1 definition was edited (version 9) are excluded as tests (`FIN_RONDA1`). Round 1: 43 participants, 100 completed situations. |
| "The photos" answer key | Extortion (General Law on Extortion, art. 15) **or** Querétaro Penal Code art. 167 Quinquies is correct, in both rounds, for the participant's answer and for what the assistant cites. See `recalificacion_fotos.md`. |
| Wrong-state metric | The first answer names the penal code of a state other than the one where the facts occurred (strict metric; independent of the answer key). |
| Legal training | Law students recruited through the law-school contact, or law as field of study or work in the profile. |
| Intervals | 95% CI, participant-level bootstrap, 4000 replicates. |

## Texts for the manuscript

| File | Content |
|---|---|
| `resultados_ronda1.md` | Round-1 results (Tables 1R, 2R); legally trained participants hesitated but did not report the wrong-state error; replacement text for Contribution 1 and Section 5.2 |
| `recalificacion_fotos.md` | Scoring rule for "the photos", what changes with it (Table R1) and required edits |
| `evaluacion_filtro_estado.md` | Independent evaluation of the jurisdiction gate (Tables G1–G4), response to Major concern 2 |
| `que_hace_cada_prompt.md` | What each system prompt changed in the answers (Tables P1, P2), response to Major concern 4 |

## Data files

| File | Content | Rounds |
|---|---|---|
| `resultados_ronda1.json` | Round 1 by prompt, situation and legal training; wrong-state answers; willingness to act by error | 1 |
| `resultados_ronda2.json` | Round 2 by prompt, situation and legal training, with differences and CIs; also round-1 wrong-state answers (`ronda1_1a_otro_estado_corregida`) | 2 (and 1) |
| `puente.json` | Bridge (Table 3): round 1 vs round 2 with the same formal prompt | 1 and 2 |
| `por_pregunta.json` | Correct answers per comprehension question and per situation, round 1 vs round 2 | 1 and 2 |
| `pruebas.json` | Test 1 (participants answer "which law" correctly when the assistant cited the expected article) and test 2 (recruitment date) | 1 and 2 |
| `como_preguntan.json` | How participants wrote their first message (state, offence, law) | 1 and 2 |
| `error_segun_mensaje.json` | Wrong-state answers by whether the message named the state | 1 and 2 |
| `recall_primer_mensaje.json` | Recall@10 of the first message, by whether it names the state | 2 |
| `estado_por_orden.json` | Giving the state by order of the situation | 2 |
| `pregunta_enterrada.json` | The "buried question" analysis | 2 |
| `filtro_real.json` | The jurisdiction gate on real round-2 messages (Table G4) | 2 |
| `que_hace_cada_prompt.json` | Answer features by prompt (Tables P1, P2) | 2 |
| `recalificacion_fotos/` | Same outputs with the previous key (`antes/`) and the rule (`despues/`); `cambios.txt` lists every value that changes | 1 and 2 |

Each JSON is produced by the script of the same topic in this folder (for example `puente_ronda1_ronda2.py` →
`puente.json`); the command is in each script's first lines. All scripts load data through `analisis_ronda2.py`, which
applies the rules above.

## Changes from `paper_2026-10-31/`

- Round 1 without the 2 test participants. Round-1 numbers change slightly: wrong-state first answers 57 of 107 → 56 of
  105 (53% in both); legally trained, would act with vs without error 23% vs 58% → 23% vs 61% (12 participants instead
  of 13).
- Round-2 point estimates and counts are identical. Some round-2 confidence limits moved slightly (up to 0.08 in small
  subgroups) because the bootstrap's random sequence is shared with round 1.
- New: `resultados_ronda1.json` and `resultados_ronda1.md`.
