# Answers to the AUTHOR CHECK items, and corrections to the 3 November draft

*For the manuscript editor (ChatGPT). Applies to `facct_submission_coauthor_update_preview.pdf` (21 pages, 3 November
2026). Each item gives the location, the status, and the text to insert. Items marked **[authors]** need information
only the authors have. Aggregates only; no participant text.*

---

## Summary

| # | Location | AUTHOR CHECK | Status |
|---|---|---|---|
| 1 | §3.1, l. 132 | Model checkpoint, parameters, quantization, decoding | Answered; authors confirmed the same model in both rounds |
| 2 | §3.1, l. 176 | BM25, HyDE/rewrite, gate, index, seeds, failure handling | Answered; prompts go to supplementary material |
| 3 | §3.2, l. 203 | Archived conversation without an answer; eligibility; compensation | Answered; authors confirmed both rounds |
| 4 | §4.1, l. 304 | Retrieval-origin count after the exclusions | Answered: 117 of 118 |
| 5 | §4.2, l. 340 | Replay artifacts and answer key | Answered; raw outputs archived on 3 Nov |
| 6 | §6, l. 568 | Independent legal validation; human validation of automatic metrics | Gate coding done; answer-measure validation in progress (100 answers); answer keys: future work |
| 7 | Ethics, l. 598 | Ethics body, protocol, retention, access | Answered: anonymized for submission; retention text supplied |
| 8 | GenAI statement, l. 613 | Model versions; other tools | **[authors]** for versions; the statement must also be corrected (C1) |

Corrections not flagged in the draft: C1–C5 below.

---

## 1. Model (§3.1, line 132)

Replace the AUTHOR CHECK with:

> Generation used Gemma 4 26B-A4B instruction-tuned (a mixture-of-experts model with 25.2B total parameters, about 4B
> active per token), in its quantization-aware-trained GGUF release quantized to UD-Q4_K_XL (Unsloth), served with
> llama.cpp with a 32,768-token context. Answers were generated at temperature 0.1 with up to 4,096 output tokens and
> the model's thinking mode disabled; other sampling parameters were the server defaults (top-k 64, top-p 0.95,
> min-p 0.05), with no fixed seed.

These settings were read from the inference server on 3 November 2026; the authors confirmed that the same model was
served throughout rounds 1 and 2.

## 2. Retrieval, gate and failure handling (§3.1, line 176)

Replace the AUTHOR CHECK with:

> BM25 was an in-house Okapi implementation (k1 = 1.5, b = 0.75; lowercase alphanumeric tokens). Dense retrieval used
> Qwen3-Embedding-0.6B (float16, last-token pooling, unit-normalized vectors) served with Text Embeddings Inference
> 1.9.3, stored in PostgreSQL with pgvector and an HNSW index on cosine distance. The two rankings were combined with
> reciprocal-rank fusion (k = 60). HyDE, query decomposition, conversational query rewriting and the jurisdiction gate
> used the same Gemma model as generation: the gate and decomposition at temperature 0 (at most 300 and 400 output
> tokens), HyDE and query rewriting at temperature 0.1 (512 and 128 tokens). The reranker was Qwen3-Reranker-0.6B
> served with vLLM. If the gate's output could not be parsed or the call failed, the system fell back to rule-based
> detection of federal-entity names and treated the matter as place-dependent, so the assistant asked where the facts
> occurred. Generation failures were logged per message: 3 messages in round 1 and 6 of 375 in round 2. The gate,
> HyDE, decomposition and rewriting prompts are provided in the supplementary material.

**[authors]** Decide whether to publish the four auxiliary prompts as supplementary material; they are in
`apps/rewrite_lab/jurisdiction_gate.py` (`EXTRAER_SYSTEM`) and `apps/rewrite_lab/main.py` / `shared/llm_client.py`.

## 3. Missing answer, eligibility and compensation (§3.2, line 203)

Replace the AUTHOR CHECK with:

> One archived conversation lacked an original first answer because the connection closed before the answer finished;
> the participant did not complete that situation. Participants had to be at least 18 years old. Participation was
> voluntary and uncompensated.

Source: round-2 consent text (section 7, "Compensation": none; eligibility: at least 18 years old). The authors
confirmed that round-1 participants were also adults and were not compensated.

## 4. Retrieval-origin count (§4.1, line 304)

Replace the AUTHOR CHECK and the surrounding sentence with:

> A trace audit of the archived round found that 117 of the 118 other-entity penal codes named in round-1 answers (in
> 74 answers) belonged to passages supplied to the generator, showing that the dominant mechanism was retrieval rather
> than invention.

With the 2 excluded test participants, the same count reproduces the earlier 120 of 121 (in 76 answers).

## 5. Replay artifacts and answer key (§4.2, line 340; Appendix D)

**Answer key.** The replay ran on 24 October and scored answers with the study definition in force that day (version
9), which already lists Querétaro art. 167 Quinquies as an expected reference. Its expected-law statistic therefore
follows the inclusive rule and can be restored. Replace "We omit the earlier replay's expected-law statistic because
the supplied package does not establish which version of the photographs answer key that analysis used" with:

> The replay scored answers with the study definition as of 24 October, which already listed Querétaro Art. 167
> Quinquies as an expected reference, so its expected-law statistic follows the inclusive rule: averaged over the two
> repetitions, 72.7% of first answers named an accepted law under round-1 retrieval and 72.2% under the jurisdiction
> gate.

In Appendix D, delete "We do not report the earlier replay's expected-law statistic because the frozen package does
not identify the key used for that separate analysis".

**Artifacts.** The replay scripts are in the repository (`06_evaluation/replay_ronda1_2026-10-24/repetir_ronda1.py`,
`resumir_replay.py`). The raw outputs (10 files, about 5 MB) contain participant messages and are stored on the study
server outside the repository. Replace the AUTHOR CHECK with:

> The replay scripts and aggregate outputs are archived with the study code; raw replay outputs contain participant
> messages and are retained on the study server under the same access conditions as the study data.

The raw outputs were copied to permanent storage on the study server on 3 November 2026 (checksums verified). The
gate-plus-reranker replay is stored in the study database.

## 6. Legal and human validation (§6, line 568)

**Done: gate coding.** The place of the facts in the 98 deployed messages flagged by the regular expression was coded
by the team's legal expert, blind to the gate's output (see C2).

**In progress: human validation of the automatic answer measures.** The team's legal expert is coding a stratified
random sample of 100 first answers, blind to the rule-based labels, round and prompt: round 1, 30 of the 56 answers the
rule flagged as wrong-state and 30 of the 49 it did not; round 2, all 8 flagged and 32 of the 188 not flagged. For each
answer she records whether it names another entity's penal code (and whether only to rule it out), whether it names an
accepted law, whether it cites an accepted article, and whether it asks where the facts occurred. **The agreement
figures will be added when the coding is returned; do not insert numbers before then.** Placeholder text for §3.4 or
§6:

> A legal expert on the team, blind to the rule-based labels, round and prompt, coded a stratified random sample of
> 100 first answers. The wrong-state rule agreed with her coding in [X] of 100 answers ([details by stratum]); the
> accepted-law, accepted-article and asks-for-place rules agreed in [X], [X] and [X].

**Not done: independent legal validation of the answer keys.** The keys were prepared by the team's legal expert; an
independent review needs a second lawyer. Replace the AUTHOR CHECK with:

> Independent legal validation of the answer keys by a second legal expert remains future work. The rule-based
> response-feature indicators in Table 8 were not human-validated and are reported descriptively.

## 7. Ethics (line 598)

The committee is the Comité de Ética en Investigación y Docencia de la Facultad de Ingeniería (CEID-FI), Universidad
Nacional Autónoma de México. Replace the AUTHOR CHECK with:

> The study protocol was reviewed and approved by the Research and Teaching Ethics Committee of the Faculty of
> Engineering, Universidad Nacional Autónoma de México (Comité de Ética en Investigación y Docencia de la Facultad de
> Ingeniería, CEID-FI) [protocol number, approval date].

For the anonymous submission, write "[anonymized institution] ethics committee" and add the committee's name, protocol
number and approval date in the camera-ready version (authors' decision, 3 November 2026).

For retention and access, the consent text supports:

> Study data are stored in a database on a contracted server accessible only to the research team. Participants can
> withdraw during the session, which deletes everything they wrote, and can later request deletion by sending their
> anonymous participant code to the researchers; without that code their responses cannot be identified.

## 8. Generative AI usage statement (line 613)

**[authors]** Insert the ChatGPT and Codex model versions. Then apply C1.

---

## Corrections not flagged in the draft

### C1. Generative AI usage statement: the current text is inaccurate

The draft says the tools "were not used to collect study data or compute the reported statistical results". An AI
coding assistant wrote and ran the analysis scripts that computed the reported statistics and reconstructed the gate's
decisions. Replace the statement with:

> The authors used OpenAI ChatGPT and Codex [versions] to convert drafts to LaTeX, reorganize sections, suggest
> revisions, and check formatting and bibliographic metadata. The authors also used Anthropic's Claude (Claude Opus 5.5,
> via Claude Code) to write and run the analysis scripts that computed the reported statistics from the study database,
> and to reconstruct the jurisdiction gate's decisions in deployed messages. The place of the facts in deployed
> messages was coded by a human author. These tools were not used to collect study data or to interact with
> participants. The authors reviewed the code, outputs and text, and remain responsible for every claim, number,
> citation and interpretation.

### C2. Gate in deployed messages: new coding (§4.2, Table 3, Table 10, Appendix E, §6)

The 98 flagged messages were recoded by the team's legal expert, blind to the gate's output. Details and sources:
`evaluacion_filtro_estado.md`, Table G4.

**§4.2, replace** from "The production system did not log gate labels directly…" to "…gives 368/375." with:

> The production system did not log gate labels directly. We therefore reconstructed the deployed decision from the
> subnational codes present among the 50 post-filter candidates for each of 375 round-2 user messages. A regular
> expression compared the federal entities each participant had named so far with the codes the gate admitted; the 277
> messages where the two agreed were accepted automatically. The team's legal expert, blind to the gate's output, coded
> the place of the facts in the other 98. No message admitted the code of an entity other than the one the participant
> identified as the place of the facts. In seven messages the participant had stated Querétaro but the gate admitted no
> subnational code: two follow-ups did not inherit the place stated earlier, and in five messages about the
> photographs the gate did not treat "I am in" or "I live in Querétaro" as the place of the facts. The gate admitted
> the expected code in 368 of 375 messages. These results test retrieval restriction, not whether the gate correctly
> decided legal competence.

**Table 3**, row "Deployed round-2 messages": Result "368/375 admitted the expected code; 7 admitted no subnational
code"; Other entity selected "0/375".

**Table 10**, replace with:

| Place described | Expected only | Other entity | No subnational code |
|---|---|---|---|
| Querétaro (178) | 171 | 0 | 7 |
| Mexico City (45) | 45 | 0 | 0 |
| State of Mexico (10) | 10 | 0 | 0 |
| Comparison of two covered entities (1) | 1 | 0 | 0 |
| No place of facts supplied (141) | — | 0 | 141 |

Caption addition: "Messages that named one entity and admitted only that entity's code were accepted automatically and
are counted under that entity, whether the participant described it as the place of the facts or as their residence."

**Appendix E**, replace "Two Querétaro follow-ups failed to inherit the earlier place, producing no subnational code
rather than another entity's code." with:

> Seven messages in which the participant had placed the facts in Querétaro admitted no subnational code: two
> follow-ups that did not inherit the earlier place, and five photographs messages in which the gate did not treat the
> participant's location as the place of the facts. None admitted another entity's code.

**§6 Limitations**, replace "one author coded the 98 deployed messages requiring review" with "one legal expert coded
the 98 flagged deployed messages, blind to the gate's output, without a second coder; the 277 automatically accepted
messages were not read".

### C3. Appendix E: "in all 74 messages that mentioned both"

Replace "The gate distinguished the facts in Querétaro from a person's Mexico City residence in all 74 messages that
mentioned both." with:

> In 76 summons messages whose conversation mentioned both Querétaro and Mexico City, the gate admitted only
> Querétaro's code in 74. In one, the participant placed the fight in Mexico City, and the gate admitted only Mexico
> City's code; the other is one of the follow-ups that did not inherit the place.

### C4. Title

Restore the title submitted with the abstract (authors' decision, 3 November 2026):

> The Right Law from the Wrong State: Auditing and Repairing Jurisdiction Errors in a Legal RAG Assistant

### C5. Numbers verified against the data package

Tables 1, 4, 5, 7 and 8, Sections 4.3–4.6, and Appendices B and C match the JSON files in this folder. No change needed.

## Sources

| Item | Source |
|---|---|
| 1, 2 | Inference, embedding and reranker servers (read 3 Nov 2026); `shared/lexical.py`, `shared/llm_client.py`, `apps/rewrite_lab/main.py`, `apps/rewrite_lab/jurisdiction_gate.py`; pgvector index on the legal table |
| 3 | Study database (round-1 turn log); `06_evaluation/estudio_ronda2_2026-10-23/consentimiento_ronda2.md` |
| 4 | Study database: other-entity codes named in each round-1 answer vs the context saved with that answer |
| 5 | `06_evaluation/replay_ronda1_2026-10-24/resumir_replay.py`, rerun on 3 Nov 2026 over the raw replay outputs (first message, mean of two repetitions) |
| C2, C3 | `evaluacion_filtro_estado.md` (Table G4); legal expert's coding kept outside the repository |
