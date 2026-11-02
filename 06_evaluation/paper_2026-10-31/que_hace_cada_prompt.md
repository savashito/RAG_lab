# What each prompt changes in the answers (response to Major concern 4)

*Text for the manuscript, in English. Data: all round-2 situations with a completed questionnaire (frozen 2 November
2026): 192 situations (original 64, new 63, intermediate 65), of which 143 from participants without legal training
(46, 47, 50). Aggregates only; no participant text. Source at the end.*

---

## The concern

The three system prompts differ in more than tone. They also change length, structure, caution, clarifying questions,
legal explanations and offers to draft documents. The design therefore cannot attribute the effect on trust and
willingness to act to plain language. We agree, and we measured what each prompt actually did to the answers.

## Method

A script measured every assistant answer in round 2 with fixed rules (regular expressions and counts; no LLM). For
each situation, we averaged its answers' features. The features are approximate: they count expressions, not meaning.

## Table P1. Features of the assistant's answers, by prompt (mean over all answers)

| Feature | Original (formal) | New | Intermediate |
|---|---|---|---|
| Words per answer | 436 | 473 | 418 |
| Words per sentence | 30 | 16 | 18 |
| Readability (INFLESZ; higher = easier) | 40 | 58 | 52 |
| Lines in bullets or numbered lists | 26% | 41% | 48% |
| Headings per answer | 0.1 | 4.1 | 3.4 |
| Articles cited per answer | 5.3 | 2.8 | 2.7 |
| Technical legal terms per 100 words | 1.0 | 0.6 | 0.6 |
| Hedging expressions per 100 words | 0.59 | 0.42 | 0.42 |
| Refers the person to a lawyer or public defender | 9% | 55% | 51% |
| Concrete next steps ("go to", "keep", "report"…) per answer | 0.8 | 3.5 | 3.0 |
| Offers to draft the complaint or another document | 0% | 30% | 2% |
| Questions to the person per answer | 0.2 | 2.3 | 1.5 |
| Contains an expression of empathy | 1% | 89% | 51% |
| Addresses the person formally ("usted") | 39% | 0% | 3% |
| States whether the facts are or may be a crime | 2% | 37% | 33% |
| Answers per situation | 1.7 | 2.0 | 2.0 |

Three findings correct our own description of the prompts:

1. **Length did not differ.** All three prompts produced answers of about 420–470 words.
2. **The intermediate prompt was not more cautious.** It used fewer hedging expressions than the formal prompt (0.42 vs
   0.59 per 100 words). It referred people to a lawyer more often (51% vs 9%) and gave more concrete next steps (3.0 vs
   0.8 per answer).
3. **Offers to draft a document appeared almost only with the new prompt** (30% vs 2% with the intermediate prompt), so
   they cannot explain the intermediate prompt's effect.

The formal prompt differed from the other two on almost every feature: longer sentences, more technical terms, more
articles cited, formal address, and almost no next steps, questions or statement of whether the facts may be a crime.
The new and intermediate prompts were similar. The new prompt asked more questions, expressed empathy more often and
offered to draft documents.

## Table P2. Effect of the intermediate prompt vs the formal prompt, adjusted for groups of features (participants without legal training)

Linear models with prompt indicators, adjusted for one group of standardized features at a time. Willingness to act is
a linear probability; trust is the participant's rating of the assistant on a five-point scale. Participant-level
bootstrap, 4000 replicates, 95% CI.

| Adjusted for | Would act (points) | Trust in the assistant (1–5) |
|---|---|---|
| Nothing | **+43 [22, 64]** | **+0.76 [0.24, 1.38]** |
| Length and structure (words, words per sentence, bullets, headings) | +36 [−13, +87] | +1.20 [0.08, 2.56] |
| Language (readability, technical terms, formal address) | +33 [−2, +75] | +0.66 [0.02, 1.61] |
| Caution and limits (hedging, lawyer referral, mentions limits of the sources) | +44 [22, 66] | +0.80 [0.26, 1.32] |
| Action (next steps, states whether it is a crime, offers to draft) | +33 [10, 56] | +0.52 [−0.03, 1.15] |
| Questions and empathy | +45 [16, 74] | +0.69 [0.04, 1.46] |
| All features | +41 [−27, +112] | +1.38 [0.00, 3.20] |

No single group of features accounts for the effect. Only action-oriented content reduced it while keeping a
usable interval: willingness to act fell from +43 to +33 points, and trust from +0.76 to +0.52. Caution explained
nothing, which contradicts the label "cautious". Adjusting for language or structure widened the intervals sharply,
because those features change together with the prompt and cannot be separated in this sample.

## Within-prompt associations (exploratory)

Within each prompt, we compared the third of situations with the most of a feature against the third with the least,
among participants without legal training. No feature showed a clear association with willingness to act. Tendencies
whose intervals include zero:

- more questions to the person: −16 points in willingness to act [−36, +8];
- stating whether the facts may be a crime: +15 points [−7, +39], and +0.37 in trust [−0.03, 0.78].

Offering to draft a document was associated with higher self-rated confidence (+0.41 on 1–5 [0.06, 0.75]). That is one
of 48 comparisons, so it may be chance.

The new and intermediate prompts were alike on most features, but the new prompt asked more questions, expressed
empathy more often and offered to draft documents. Its effect on willingness to act was smaller (+18 points vs the
formal prompt [−9, +45]). More questions and more offers did not increase willingness to act.

## Suggested text for the response to reviewers

> We agree that the three prompts differ in many features at once, and that the design cannot attribute the effect to
> plain language. We measured the answers with fixed rules (Table P1). The prompts did not differ in length (418–473
> words). The intermediate prompt was not more hedged than the formal one (0.42 vs 0.59 hedging expressions per 100
> words). It differed in sentence length, technical vocabulary, structure (headings and bullets), referral to a lawyer,
> concrete next steps, and stating whether the facts may be a crime. Offers to draft a complaint appeared almost only
> with the new prompt (30% vs 2%), so they cannot explain the intermediate prompt's effect. Adjusting for feature groups
> one at a time (Table P2), only action-oriented content (concrete steps and stating whether the facts may be a crime)
> reduced the effect on willingness to act (from +43 to +33 points) and on trust (from +0.76 to +0.52). Language and
> structure features vary together with the prompt and cannot be separated in this sample. We therefore relabel the
> condition as a "lay-oriented prompt" rather than "plain and cautious", report the effect as the effect of a prompt
> bundle, and propose a factorial follow-up that varies language register, structure and action content independently.

## Proposed changes to the manuscript

1. Rename the condition "plain and cautious" to "lay-oriented" everywhere; the data do not support "cautious".
2. Add Table P1 (what each prompt changed) next to the prompt results, and Table P2 in an appendix.
3. Describe the result as the effect of a bundle of features, not of plain language.
4. Add a limitation: the features vary together with the prompt; about 50 situations per prompt among participants
   without legal training; features measured with fixed rules, not human coding.
5. In Section 8, specify the round-3 experiment as factorial: register (legal vs everyday), structure (paragraphs vs
   headings and lists), and action content (with vs without next steps and a statement of whether it may be a crime).

## Note on numbers

Table P2 uses all of round 2. The manuscript currently reports trust +0.8 [0.2, 1.4] for the same comparison and
+0.79 [0.28, 1.41] for participants recruited from 29 October. Use one of them consistently.

## Source

| Table | Source |
|---|---|
| P1, P2, within-prompt associations | `06_evaluation/paper_2026-10-31/que_hace_cada_prompt.py` → `que_hace_cada_prompt.json` (fields `rasgos_por_prompt.todas`, `efecto_del_prompt_con_ajuste.sin`, `rasgo_vs_desenlace_dentro_del_prompt.sin`) |
