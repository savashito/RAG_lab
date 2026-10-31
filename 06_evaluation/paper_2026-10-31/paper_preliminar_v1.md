# Where You Are and Who You Are: Applicability Errors and Misplaced Trust in a Legal RAG Assistant, Audited with Its Users

*Preliminary draft v1 (31 October 2026). Anonymous submission to ACM FAccT 2027. Round-2 data frozen on 31 October
2026, 07:57 UTC; collection continues. Every number has a source in Appendix A. Items marked ⚠ must be checked before
submission.*

---

## Abstract

Retrieval-augmented generation (RAG) is promoted to widen access to legal information, yet legal RAG is usually
evaluated with questions written by experts. In Mexico, criminal law is split across a federal code, a national
procedural code and 32 state penal codes, so whether a law applies depends on where the facts occurred. We audit an
open-weight, locally hosted RAG assistant over Mexican criminal law in two rounds with its intended users, who consulted
it in their own words about three fictional situations. In round 1 (45 participants), 53% of first answers (57 of 107)
named the penal code of a state other than the one where the facts occurred, and in 120 of 121 cases that code had been
supplied by retrieval, not invented by the model. Participants without legal training noticed a problem in 8% of
situations, yet said they would act on the answer in 64%. A jurisdiction gate, an LLM step that identifies where the
facts occurred and restricts retrieval to that state's code plus national law, cut wrong-state answers from 60% to 2%
when replayed on all 108 real conversations, with no loss in citing the correct law. Deployed in round 2 (52
participants so far), only 2 of 117 first answers named another state's code. Round 2 also assigned each participant at
random one of three system prompts: a formal legal prompt, a warm and comprehensive one, and a plain and cautious one.
Among participants without legal training, both plain-language prompts raised the share who would act on the answer
from 35% to 86–88% (+50 and +52 points; 95% CIs from 24 to 77) and raised trust in the answer by up to one point on a five-point
scale, while comprehension did not change (63%, 63% and 70%). Problem detection stayed between 4% and 12%. Fixing
*where* exposed a second applicability condition, *who*: after the gate, answers in a gender-neutral extortion scenario
cited a law that protects only women in 33% of replayed answers. We argue that legal RAG must be evaluated with the
people it serves, that its metrics must check whether a cited law applies to where they are and who they are, and that
tone is a safety variable, not only a usability one.

**Keywords:** legal information access, retrieval-augmented generation, jurisdiction, user study, evaluation practices,
overreliance, sycophancy, access to justice, Mexico

---

## 1. Introduction

People meet legal problems before they can afford or reach a lawyer. A conversational assistant appears to lower that
barrier: a person describes what happened in ordinary words and receives an explanation of possible offenses, rights and
next steps, with citations to the law. Retrieval-augmented generation (RAG) is the standard way to ground such answers in
real legal text, and legal-technology vendors advertise it as a cure for hallucination. Audits of commercial legal RAG
tools show that it is not [Magesh et al. 2025], and benchmark work shows that models that answer legal questions
correctly often cite the wrong jurisdiction's sources [Yang et al. 2026].

Two features of the setting we study make this problem acute. First, Mexico is a federal system: each of the 32 states
has its own penal code, while some offenses are governed by general laws that apply nationwide and procedure is governed
by a single national code. Two state codes can describe the same conduct with different elements and penalties. A
citation can therefore be real, quoted correctly, and still inapplicable to the person who reads it. Second, the people
who most need free legal orientation are the least able to check which state's law a citation belongs to. Lay people
already prefer LLM-generated legal advice and say they would act on it even when they can tell it apart from a lawyer's
[Schneiders et al. 2025].

We report a two-round audit of an open-weight RAG assistant for Mexican criminal law, run with its intended users
rather than with expert-written questions. In each round, participants consulted the assistant in their own words about
three fictional situations whose correct answers depend on where the facts occurred. Between rounds we repaired the
failure that round 1 exposed and replayed every real round-1 conversation through the repaired system. In round 2 we
deployed the repair and assigned each participant at random one of three system prompts that differ in register and
tone.

We ask four research questions:

- **RQ1.** How often does the assistant cite law from a state other than the one where the facts occurred, and where in
  the pipeline does that law come from?
- **RQ2.** Do users notice these errors, and does legal training change that?
- **RQ3.** Does a system-level jurisdiction gate remove the error, and what does it expose?
- **RQ4.** Does a plain-language, warmer prompt improve comprehension, or does it raise trust and willingness to act
  without improving comprehension?

Our contributions are: (1) evidence, from real conversations, that wrong-jurisdiction citations in legal RAG are mostly
a retrieval failure, invisible to most users; (2) a jurisdiction gate evaluated by replaying every real conversation,
then deployed; (3) a randomized comparison of three prompts showing that plain, warm language raised trust and stated
willingness to act among lay users without raising their comprehension; (4) the observation that applicability has at
least two conditions, where the person is and who the person is, and that the second surfaces only after the first is
fixed; and (5) a methodological lesson: our own place-name metrics misled us twice, and we document how.

## 2. Background and related work

### 2.1 Legal hallucination and misgrounded citations

General-purpose LLMs hallucinate legal facts and do not reliably recognize their own errors [Dahl et al. 2024]. RAG
reduces but does not eliminate this: in a preregistered evaluation, commercial legal research tools built on RAG
hallucinated in more than 17% of queries, and the authors count as an error an answer that is *misgrounded*, citing a
real source that does not support the claim [Magesh et al. 2025]. Our wrong-state citations are a specific kind of
misgrounding: the source exists and may even support the sentence, but it does not govern the facts. Benchmarks are
beginning to target this. CrossLex pairs the same fact patterns across China, California and Germany and finds that
models often answer correctly but fail to cite the right jurisdiction's authorities [Yang et al. 2026]; Housing Statute
QA already treats jurisdiction as a hard retrieval boundary with separate candidate pools per jurisdiction [Zheng et al.
2025]. These benchmarks compare countries or US states with expert-written questions. We study states inside one
federal country, with questions written by users.

Spanish-language legal NLP is under-resourced. A 2026 systematic review found no dedicated legal question-answering
benchmark for Spanish-speaking jurisdictions in Latin America, and in a new bar-exam benchmark from Bolivia, Colombia and
Puerto Rico, criminal law was among the weakest areas for frontier models (66% accuracy) [Mind the Gap 2026 ⚠ authors].
We are not aware of a user study of a legal assistant for Mexican law. ⚠ Systematic search of ACM DL, ACL Anthology,
ICAIL, JURIX, NLLP and CS&Law still pending before claiming "first".

### 2.2 Why retrieved context drives the error

Models follow retrieved context, even when it is irrelevant or conflicting. Irrelevant information degrades answers and
an instruction to ignore it helps only partly [Shi et al. 2023]; documents that are related but not relevant hurt RAG
more than random ones [Cuconasu et al. 2024]; and models readily adopt coherent external evidence even against their own
knowledge [Xie et al. 2024]. Another state's article on the same offense is exactly a related-but-not-relevant,
coherent document, and two states' articles in one context are an inter-context knowledge conflict [Xu et al. 2024].
This predicts what we found: prompting the model not to cite other states helps little while their articles remain in
the context. The fix we evaluate, restricting retrieval by metadata before search, is a common practitioner pattern
(self-querying retrieval) and has helped in another regulated domain [Dadopoulos et al. 2025]; we add a legal fallback:
when no place is found, retrieve only national law and ask.

### 2.3 Lay users, trust and overreliance

Lay people tend to prefer LLM legal advice and report greater willingness to act on it than on a lawyer's advice
[Schneiders et al. 2025]. People overestimate the accuracy of LLM answers, more so for longer explanations [Steyvers et
al. 2025]. Fluent LLM explanations raise confidence and reliance without reliably raising accuracy, and subjective trust
and perceived clarity predict human–AI team performance poorly [Cohen et al. 2026 ⚠ preprint]. Hedged, first-person
expressions of uncertainty reduce, but do not eliminate, overreliance [Kim et al. 2024]. Explanations reduce
overreliance only when they are easier to verify than the task itself [Vasconcelos et al. 2023], and cognitive forcing
functions reduce it at a cost in user satisfaction [Buçinca et al. 2021].

### 2.4 Warmth, tone and sycophancy

Tone is not neutral. Fine-tuning models to be warmer and more empathetic raised their error rates on safety-critical
tasks by 10 to 30 percentage points and made them more likely to validate users' incorrect beliefs, especially when
users expressed sadness or confusion; training the same models to be colder did not [Ibrahim et al. 2025 ⚠ preprint].
Models preserve users' face far more than humans do in advice settings (social sycophancy) [Cheng et al. 2026], and
human preference data reward answers that agree with the user [Sharma et al. 2024]. On the user side, warmth and
empathy in a chatbot's presentation shape perceived trust and usefulness even when the underlying model is unchanged
[⚠ arXiv 2604.15316, authors to confirm], and anthropomorphic cues raise perceived accuracy [Cohn et al. 2024]. At
FAccT, writing in the user's own sociolect did not raise reliance [Basoah et al. 2025]. Legal-design work treats plain
language as a quality criterion of good legal help [Hagan 2024]. Our round-2 manipulation sits between these
literatures: we did not fine-tune the model, we only changed the system prompt, and we measured comprehension
separately from trust and willingness to act.

### 2.5 Auditing across the pipeline

Lifecycle audits trace harms to upstream design choices rather than to "model error" [Raji et al. 2020; Suresh and
Guttag 2021], and deployed AI often fails at the basic function it implies [Raji et al. 2022]. An assistant that cites
another state's code fails at the function a legal assistant implies: telling you *your* law.

## 3. System

The assistant is a self-hosted RAG system. Generation uses an open-weight Gemma model served with llama.cpp on a single
GPU (⚠ confirm exact model and quantization: served alias `Gemma-4-4B-8b`; earlier draft says Gemma 4 26B-A4B). The
corpus for criminal law had 51 sources and 8,557 passages in round 1: the Federal Penal Code, the National Code of
Criminal Procedure, the penal codes of Mexico City, the State of Mexico, Morelos and Querétaro, several general laws
(including the General Law on Extortion and the General Law on Women's Access to a Life Free of Violence), doctrine,
and materials on digital violence. Statutes are split roughly one article per passage, with the law name and hierarchy
in the passage text.

Retrieval combines BM25 with dense embeddings (Qwen3-Embedding-0.6B) by reciprocal-rank fusion, plus hypothetical
document embeddings (HyDE) [Gao et al. 2023], query decomposition for comparative questions, and neighboring articles.
The top 10 passages go to the model. In multi-turn conversations, the system rewrites the current question using the
history before searching.

**Round 1 configuration.** When a user named a state, the router added a search restricted to that state's code and
interleaved it with the general search. It did not remove other states' passages.

**Round 2 configuration (changes made between rounds).**

1. **Jurisdiction gate.** Before retrieval, an LLM step reads the user's own words (not the HyDE text, which can invent
   a place) and decides where the facts occurred. If it finds a state, retrieval is restricted to that state's code plus
   federal and general law. If it finds none, retrieval is restricted to federal and general law. A second rule decides
   whether the current question names a place (`filtro_ve_pregunta`) so that a later message does not inherit a state
   from an unrelated earlier one.
2. **Reranker.** A cross-encoder reranker (Qwen3-Reranker-0.6B) reorders the fused candidates. On round-1 first
   messages, it raised recall@10 of the expected article from 25.3% to 35.0% (Table 6).
3. **Nine sources switched off for search** on 25 October, the day round 2 opened, by the research team through an
   administration page: among them the General Law on Women's Access to a Life Free of Violence and a technical note
   on "Ley Olimpia" (Section 6.3). Round 2 searches 42 sources and 6,766 passages. Round 1 and all replays used all 51.
4. **System prompts** (Section 4.3).

Answers took 12.1 seconds on average in round 2 (90% within 14.8 s).

## 4. Study design

### 4.1 Situations

Participants saw three fictional situations in random order. Each has an answer key written by a legal expert on our
team.

- **Workplace messages.** A supervisor sends sexual messages and offers a promotion for a date; no physical contact.
  Half the participants (assigned at random) saw the facts in Querétaro, half in Mexico City. Correct law: Querétaro
  Penal Code art. 167 Ter (sexual harassment by a superior), or Mexico City Penal Code art. 179.
- **The photos.** Cris, 24, lives in Querétaro, sent intimate photos to someone met on an app, and is now asked for
  5,000 pesos under threat of publication. Correct law: extortion under the General Law on Extortion, arts. 15 and 17;
  Querétaro art. 167 Quinquies is also relevant. The scenario is gender-neutral on purpose.
- **The summons.** Ariel lives in Mexico City, hit someone in a bar in Querétaro and received a summons from Querétaro's
  prosecutor, and believes Mexico City law applies. Correct law: Querétaro Penal Code art. 1 and National Code of
  Criminal Procedure art. 20.

### 4.2 Procedure and measures

Consent, a profile questionnaire, a practice question, then three situations. In each situation participants could send
the assistant up to six messages in their own words, then answered two multiple-choice comprehension questions,
rated their confidence (1–5), said whether they had noticed a problem in the answers, and whether they would act on
them. From 26 October, round 2 added two five-point scales after each situation, written by the legal expert: trust in
the assistant's answer and perceived correctness of the legal information. The study ends with the System Usability
Scale (SUS) and two open questions.

- **Comprehension:** share of the two questions answered correctly (aciertos), per situation.
- **Would act / noticed a problem:** share of situations with "yes".
- **Wrong-state code:** an answer names the penal code of a state other than the one where the facts occurred (regular
  expressions over code names; Appendix B explains why this strict version replaced two earlier ones).
- **Correct law / correct article:** the answer cites the law (and article) in the answer key.
- **Asks for the state:** the answer contains a question or direct request about where the facts occurred.
- **Recall@10:** share of expected articles among the 10 passages the retriever returned for the participant's message.

We report differences between prompts with 95% confidence intervals from a bootstrap that resamples **participants**
(4,000 replicates), because each person contributes up to three situations.

### 4.3 Conditions

**Round 1** compared two prompts with participants assigned at random: the **formal legal** prompt (the original, written
for law students and professionals) and a plain-language prompt; a non-randomized pilot used the formal prompt.

**Round 2** assigns each participant at random one of three system prompts, all with the repaired retrieval:

| Condition (id in the data) | Name in this paper | What the prompt asks the model to do |
|---|---|---|
| `original` | **Formal legal** | Answer only from the context, in "clear, precise and professional legal Spanish" for law students and professionals; argumentative paragraphs; sections Answer / Legal basis / Conclusion / Doctrinal sources. Same prompt as round 1 (bridge). |
| `nuevo` | **Warm and comprehensive** | Everyday, empathetic language plus a full legal interview: elements of the offense, penalties, every procedural stage; always a "Legal basis" section; at most two questions; offers to draft complaints and filings once the state is known. The longest prompt. |
| `intermedio` | **Plain and cautious** | Everyday language, short paragraphs; insists on not overstating certainty, separating facts from hypotheses, and checking that a law applies to the people involved (age, relationship); drafts filings only if asked; sections Orientation / Legal basis / Options. Added on 28 October. |

The application assigns each new participant the condition with the fewest participants so far (ties broken at
random), and stores it before the first situation; participants do not see it. Because the third prompt was added on 28
October with 6 participants in each of the first two, the next six participants all received it. Its first participants
therefore arrived on later dates than the average participant of the other two conditions (Section 7).

### 4.4 Participants

**Round 1** (9–21 October 2026): 45 participants, 33 completed; 26 without legal training and 19 with it (studies or
studied law, or works in a legal job). Recruited at a public university through in-person kiosks and a public link.

**Round 2** (25 October onward; frozen 31 October): 52 consented, 37 completed the whole study, 50 completed at least
one situation (114 situations, 232 messages to the assistant). Recruitment was through three public links shared
in messaging groups (46 participants) and in-person kiosks (6). 40 had no legal training and 12 had it. Legal training is
unevenly distributed across conditions (Table 1), which is why we report lay participants separately.

**Table 1. Round 2 participants by condition.**

| | Formal legal | Warm and comprehensive | Plain and cautious | Total |
|---|---|---|---|---|
| Consented | 17 | 18 | 17 | 52 |
| Completed the study | 12 | 13 | 12 | 37 |
| Without legal training | 16 | 12 | 12 | 40 |
| With legal training | 1 | 6 | 5 | 12 |

Profile (all 52): highest education: completed bachelor's 27, master's 10, high school 7, bachelor's in progress 6,
doctorate 2. Age: 18–24: 6; 25–34: 12; 35–44: 19; 45–59: 12; 60+: 3. AI assistant use: daily 19, weekly 6, a few times a
month 22, never 5.

## 5. Results

### 5.1 RQ1: wrong-state citations come from retrieval

In round 1, 53% of first answers (57 of 107) named the penal code of a state other than the one where the facts
occurred: 57% (24 of 42) with the formal legal prompt, 38% (15 of 39) with the plain-language prompt, and 69% (18 of 26)
in the pilot. By situation: workplace messages 51%, photos 59%, summons 48%. The code was not invented: across all
round-1 answers, 120 of the 121 wrong-state codes named (in 76 answers) had been retrieved into the context. The
plain-language prompt of round 1 asked for the state more often, which lowered but did not remove the error; prompting
alone does not change what the model sees.

### 5.2 RQ2: users rarely notice

Participants without legal training noticed a problem in 8% of round-1 situations (64 situations) and said they would act
on the answer in 64%. Participants with legal training noticed a problem more often (19% of 37 situations) and were more
cautious (would act in 46%). Legal training made people more skeptical in general, but it did not make the specific
error visible: legally trained participants also chose the wrong state's article in the workplace scenario, and their
comments expressed general caution ("verify against the law") rather than pointing at the other state's code.

### 5.3 RQ3: the jurisdiction gate, replayed and deployed

We replayed every real round-1 conversation (108 conversations, twice each) through the round-1 configuration (A) and
the gate (B), with the same prompt.

**Table 2. Replay of the 108 real round-1 conversations (two repetitions each).**

| | A: round-1 retrieval | B: gate | B + reranker |
|---|---|---|---|
| Answers naming another state's code (first message) | 59.7% | 1.9% | 2.8% |
| Answers citing the correct law | 72.7% | 72.2% | — |
| Correct article, follow-up messages, change vs A | — | — | +13.0 points [1.9, 25.0] |
| Answers in "photos" citing the women's-violence law | 13% (15/112) | 33% (37/112) | 34% (38/112) |

The gate cut wrong-state answers by 57.9 points (95% CI −66.2 to −49.5) without losing correct-law citations. The
reranker added correct-article citations in follow-up messages (+10.5 points over B, CI −0.6 to 21.5; +13.0 over A).

**Deployed in round 2,** the gate held: only 2 of 117 first answers (1.7%) named another state's code, both with the
formal legal prompt (2 of 38, 5.3%); none of the 79 first answers with the two plain-language prompts did. Counting
every answer in a situation, 5% (formal), 0% (warm) and 8% (plain and cautious) of situations had at least one
wrong-state answer. The share of first answers citing the correct law did not differ by prompt (66%, 68%, 66%).

### 5.4 RQ4: plain language raised trust and willingness to act, not comprehension

**Table 3. Round 2, all participants, by prompt.** Values are means per situation; n = situations (n of participants with
at least one situation: 17, 16, 17). Trust and perceived-correctness scales exist only from 26 October.

| Measure | Formal legal | Warm and comprehensive | Plain and cautious |
|---|---|---|---|
| Comprehension (aciertos) | 61% (37) | 74% (40) | 68% (37) |
| Trust in the answer (1–5) | 3.28 (25) | 3.94 (31) | 4.19 (37) |
| Perceived correctness (1–5) | 3.52 (25) | 4.13 (31) | 4.24 (37) |
| Confidence in own answers (1–5) | 3.89 (37) | 4.23 (40) | 4.14 (37) |
| Would act on the answer | 35% (37) | 83% (40) | 78% (37) |
| Noticed a problem | 11% (37) | 10% (40) | 16% (37) |
| SUS (0–100), completers | 65.4 (12) | 77.9 (13) | 79.0 (12) |
| Answers that ask for the state | 56% | 36% | 30% |
| Words per answer | 447 | 486 | 433 |
| First answer cites the correct law | 66% (38) | 68% (41) | 66% (38) |
| First answer cites the correct article | 50% (38) | 56% (41) | 55% (38) |
| First answer names another state's code | 5% (38) | 0% (41) | 0% (38) |
| Recall@10, first message | 24% (38) | 39% (42) | 29% (38) |
| Median minutes per situation | 6.9 | 5.1 | 5.8 |

Retrieval is identical across prompts, so differences in recall@10 come from how participants in each group wrote
their first message. The warm-and-comprehensive group had more legally trained participants (6 of 18), and their
first messages retrieved better (recall@10 of 63% for those six, against 25% for the group's lay participants). That imbalance also explains most of that group's higher
comprehension. Among participants without legal training, the pattern is clearer:

**Table 4. Round 2, participants without legal training only.**

| Measure | Formal legal (16) | Warm and comprehensive (10) | Plain and cautious (12) |
|---|---|---|---|
| Comprehension (aciertos) | 63% (34) | 63% (24) | 70% (28) |
| Trust in the answer (1–5) | 3.28 (25) | 4.00 (18) | 4.25 (28) |
| Perceived correctness (1–5) | 3.52 (25) | 4.28 (18) | 4.21 (28) |
| Would act on the answer | 35% (34) | 88% (24) | 86% (28) |
| Noticed a problem | 12% (34) | 4% (24) | 11% (28) |

**Table 5. Differences between prompts (percentage points or scale points), 95% CI from a participant bootstrap.**

| Measure | Warm − Formal | Plain − Formal | Plain − Warm |
|---|---|---|---|
| *All participants* | | | |
| Would act | +47.4 [23.0, 70.9] | +43.2 [16.4, 68.6] | −4.1 [−26.2, 16.9] |
| Trust in the answer (1–5) | +0.66 [−0.05, 1.52] | +0.91 [0.22, 1.73] | +0.25 [−0.22, 0.71] |
| Perceived correctness (1–5) | +0.61 [−0.12, 1.47] | +0.72 [−0.03, 1.61] | +0.11 [−0.34, 0.54] |
| Comprehension | +12.9 [−8.7, 34.2] | +6.8 [−12.9, 27.1] | −6.2 [−23.2, 10.4] |
| Noticed a problem | −0.8 [−16.4, 15.2] | +5.4 [−12.2, 23.5] | +6.2 [−11.0, 23.6] |
| Answers that ask for the state | −19.4 [−38.7, 1.3] | −25.5 [−43.3, −6.7] | −6.1 [−21.7, 7.5] |
| *Without legal training* | | | |
| Would act | +52.2 [25.8, 77.3] | +50.4 [23.8, 75.8] | −1.8 [−23.1, 21.4] |
| Trust in the answer (1–5) | +0.72 [−0.08, 1.67] | +0.97 [0.22, 1.85] | +0.25 [−0.40, 0.94] |
| Comprehension | −0.7 [−25.3, 25.2] | +6.4 [−14.6, 26.9] | +7.1 [−14.3, 28.3] |
| Noticed a problem | −7.6 [−22.6, 6.3] | −1.1 [−19.4, 17.8] | +6.5 [−8.2, 23.9] |

Three results stand out. First, the formal legal prompt is an outlier on willingness to act: about a third of
participants would act on its answers, against more than four in five with either plain-language prompt, and the
interval excludes zero in every comparison with it. Second, the plain-and-cautious prompt, which explicitly tells the
model not to overstate certainty, produced the highest trust (4.19 of 5); the difference with the formal prompt excludes
zero. Third, comprehension among lay participants did not move with either: 63%, 63% and 70%, with intervals that
include zero and are wide (about ±25 points). Detection of problems stayed low with all three prompts.

Trust also tracked comprehension only weakly. With the plain-and-cautious prompt, comprehension was 68% in situations
where participants rated trust 4 or 5 (30 situations) and 64% where they rated it 1–3 (7 situations); with the formal
prompt, 64% (14) and 50% (11).

By situation (Appendix A, Table A2), the difference in willingness to act is largest in the summons (23% formal vs 86%
warm and 75% plain) and the photos (33% vs 85% and 77%), the two situations where acting on a wrong answer has the
clearest consequence (ignoring a summons; paying or not reporting extortion).

### 5.5 Fixing *where* exposed *who*

Once the gate kept the right state's law in the context, a different applicability error became visible. "The photos"
is gender-neutral, yet in the replay with the gate, 33% of answers (37 of 112) cited the General Law on Women's Access to
a Life Free of Violence, against 13% without it (Table 2): with other states' codes removed, this general law, which
applies nationwide but protects only women, rose in the ranking. The citation is correct about *where* and wrong about
*who*. On 25 October, before round 2 opened, the team switched that law and eight other sources off for search; no
round-2 "photos" answer cited it. This is a stopgap that removes the law for the people it does protect. The principled
fix is a second applicability condition, the person's characteristics (sex, age, relationship to the other party), that
the system must ask about or infer before citing a law that depends on them. We have built the first step, an editor
page where legal experts tag whole documents with the person categories they apply to; the filter itself is future
work.

### 5.6 Retrieval is still the ceiling

**Table 6. Recall@10 of the expected articles, round-1 first messages replayed through each configuration.**

| Configuration | All situations | Photos |
|---|---|---|
| HyDE only (round 1) | 18.9% | — |
| Round 2 without reranker | 25.3% | 12.3% |
| Round 2 with reranker | 35.0% | 24.6% |
| Round 2 with reranker, 9 sources off | 37.3% | 27.2% |

Even with the reranker, the retriever brings the expected article into the top 10 for about a third of first messages.
The model cites the correct law far more often (66%) than the retriever finds the exact article, because neighboring
articles of the right law often suffice; but the correct *article* is cited in only 50–56% of first answers.

## 6. Discussion

### 6.1 The failure is applicability, not hallucination

Wrong-state citations were real articles from real codes, retrieved and faithfully reproduced. A metric that checks
whether a citation exists, or even whether it supports the sentence, would score many of them as correct. Legal RAG needs
an applicability check: does this law govern *these* facts, *here*, for *this* person? Prompting does not supply that
check (round 1's plain prompt asked for the state and still cited other states); changing what the model sees does
(Table 2).

### 6.2 Tone is a safety variable

Round 2 replicates, with random assignment and three prompts, the pattern round 1 only suggested: plain, warm language
raised stated willingness to act (by about 50 points among lay participants) and trust (up to one scale point) without
raising comprehension. This is consistent with work showing that fluency raises reliance more than accuracy [Cohen et al.
2026; Steyvers et al. 2025] and that warmth trades off against reliability [Ibrahim et al. 2025]. Two details sharpen it.
First, our manipulation did not change the model, the retrieval or the cited law: the share of first answers citing the
correct law was 66–68% in all three conditions. What changed was how persuasive the same evidence sounded. Second,
telling the model to be cautious did not make users cautious: the plain-and-cautious prompt produced the *highest*
trust. Plain language is still the right goal for access to justice [Hagan 2024]; the formal prompt's low willingness
to act is not a virtue, since participants also did not understand it better. The implication is that plain-language
legal assistants need mechanisms that make limits visible in ways users act on, for example asking for the state before
answering (the formal prompt asked most often, 56% of answers) or first-person uncertainty [Kim et al. 2024], and that
evaluations must measure comprehension and reliance separately, as the trust a prompt produces is not evidence that
users understood.

### 6.3 Applicability has more than one condition

The gate solved *where* and exposed *who*. Switching off the women's-violence law fixed the gender-neutral scenario at the
price of hiding the law from the women it protects. A legal assistant must reason about the person, not only the place,
and must ask when the answer depends on facts the user has not given. Each repair moves the error to the next condition
the system does not model, which is an argument for evaluating with real users, whose stories contain the conditions
benchmark authors did not anticipate.

### 6.4 Our metrics misled us

Our first wrong-state metric counted any mention of a place: the correct summons answer "Querétaro, not Mexico City,
governs" scored as citing Mexico City. Our second, the version in the study dashboard, treated as allowed only the codes
of the laws in the answer key; in "the photos" the key is a general law, so citing Querétaro's own penal code, which is
the right state, counted as an error, inflating round-2 wrong-state rates from 2% to about 8%. We report the strict
version, defined by the place where the facts occurred (Appendix B). Applicability metrics need the same scrutiny as the
systems they score.

## 7. Limitations

- **Small samples.** 16–18 participants per prompt; differences in comprehension of 10–15 points cannot be detected yet
  (Section 8). The comprehension result is an absence of evidence, not evidence of absence.
- **Uneven legal training across prompts** (1, 6 and 5 legally trained participants). We report lay participants
  separately; stratified assignment would have prevented this.
- **Time confound for the third prompt.** Its first six participants arrived consecutively after 28 October.
- **Self-reported willingness to act**, not behavior. Trust scales exist only from 26 October.
- **Recruitment** through public links in messaging groups; participants may share networks.
- **Prompts differ in more than tone** (length, structure, whether they ask for the state, whether they offer to draft
  filings), so we cannot isolate tone.
- **Metrics are automatic** (regular expressions over answers). Human grading by legal experts is pending (0 answers
  graded so far).
- **Same model as judge** in our earlier expert benchmark [Panickssery et al. 2024]; not used for any number in this
  draft.
- **Nine sources switched off** between rounds, so round 1 and round 2 corpora differ.

## 8. How much more data

Using the spread observed between participants in round 2 (standard deviation of each person's mean), two-sided
α = 0.05 and 80% power:

| Claim we want to make | Participants needed per prompt |
|---|---|
| Detect a 15-point difference in comprehension | 48 |
| Detect a 10-point difference in comprehension | 107 |
| Show comprehension differs by less than ±10 points (equivalence) | 117 |
| Detect a 0.5-point difference in trust (1–5) | 43 |
| Detect a 10-point difference in noticing a problem | 77 |

The willingness-to-act difference is already detected. The trust difference between the formal and plain-and-cautious
prompts is detected; trust differences between the two plain prompts need about 43 per prompt. Our plan is to reach
about 45 participants per prompt (about 135 in total, about 85 more), assigning within strata of legal training, and to
treat comprehension equivalence as a question for a larger, preregistered follow-up.

## 9. Ethical considerations

Fictional situations, anonymous codes, informed consent approved by ⚠ [institution / protocol id], withdrawal with
immediate deletion, and deletion on request by code. No names, emails or IP addresses are stored with responses. The
assistant was evaluated as a research system; it states that it does not replace a lawyer. The situations include
sexual harassment and threats to publish intimate images; participants could stop at any time. Switching off the
women's-violence law is a research stopgap with a cost we name in Section 6.3.

## 10. Conclusion

A legal assistant can cite real law, sound clear and kind, and still mislead, because the law it cites belongs to
another state or protects another kind of person. Most such errors came from retrieval, most users did not see them, and
a system-level gate removed almost all of the wrong-state citations. Making the assistant speak plainly, which is the
right goal for access to justice, raised trust and willingness to act without raising comprehension. Evaluations of
legal AI should be run with the people it is meant to serve, should check applicability (where and who), and should
treat tone as part of the safety case.

---

## References (⚠ = verify before submission)

- Basoah, J., Chechelnitsky, D., Long, T., Reinecke, K., Zerva, C., Zhou, K., Díaz, M., and Sap, M. 2025. Not Like Us,
  Hunty: Measuring Perceptions and Behavioral Effects of Minoritized Anthropomorphic Cues in LLMs. *FAccT 2025*.
  arXiv:2505.05660.
- Buçinca, Z., Malaya, M. B., and Gajos, K. Z. 2021. To Trust or to Think: Cognitive Forcing Functions Can Reduce
  Overreliance on AI in AI-assisted Decision-making. *PACM HCI 5 (CSCW1)*. arXiv:2102.09692.
- Cheng, M., Yu, S., Lee, C., Khadpe, P., Ibrahim, L., and Jurafsky, D. 2026. ELEPHANT: Measuring and Understanding Social
  Sycophancy in LLMs. *ICLR 2026*. arXiv:2505.13995.
- Cohen, R., Feng, L., Bloch, A., and Kraus, S. 2026. The Persuasion Paradox: When LLM Explanations Fail to Improve
  Human-AI Team Performance. arXiv:2604.03237. ⚠ preprint.
- Cohn, M., et al. 2024. Believing Anthropomorphism: Examining the Role of Anthropomorphic Cues on User Trust in Large
  Language Models. *CHI 2024 (Extended Abstracts)*. arXiv:2405.06079. ⚠ full author list and track.
- Cuconasu, F., et al. 2024. The Power of Noise: Redefining Retrieval for RAG Systems. *SIGIR 2024*. arXiv:2401.14887.
- Dadopoulos, M., Ladas, A., Moschidis, S., and Negkakis, I. 2025. Metadata-Driven Retrieval-Augmented Generation for
  Financial Question Answering. arXiv:2510.24402. ⚠ preprint.
- Dahl, M., Magesh, V., Suzgun, M., and Ho, D. E. 2024. Large Legal Fictions: Profiling Legal Hallucinations in Large
  Language Models. *Journal of Legal Analysis* 16(1): 64–93. doi:10.1093/jla/laae003.
- Gao, L., Ma, X., Lin, J., and Callan, J. 2023. Precise Zero-Shot Dense Retrieval without Relevance Labels. *ACL 2023*.
  arXiv:2212.10496.
- Hagan, M. 2024. Measuring What Matters: Developing Human-Centered Legal Q-and-A Quality Standards through
  Multi-Stakeholder Research. *JURIX 2024*. ⚠ pages/DOI.
- Ibrahim, L., Hafner, F. S., and Rocher, L. 2025. Training Language Models to Be Warm and Empathetic Makes Them Less
  Reliable and More Sycophantic. arXiv:2507.21919. ⚠ preprint; check venue.
- Kim, S. S. Y., Liao, Q. V., Vorvoreanu, M., Ballard, S., and Wortman Vaughan, J. 2024. "I'm Not Sure, But...":
  Examining the Impact of Large Language Models' Uncertainty Expression on User Reliance and Trust. *FAccT 2024*.
  doi:10.1145/3630106.3658941.
- Magesh, V., Surani, F., Dahl, M., Suzgun, M., Manning, C. D., and Ho, D. E. 2025. Hallucination-Free? Assessing the
  Reliability of Leading AI Legal Research Tools. *Journal of Empirical Legal Studies* 22: 216–242.
  doi:10.1111/jels.12413.
- Mind the Gap: A Systematic Review and Benchmark of Spanish-Language Legal Question Answering in Latin America. 2026.
  *ICML 2026*. ⚠ authors.
- Panickssery, A., Bowman, S. R., and Feng, S. 2024. LLM Evaluators Recognize and Favor Their Own Generations. *NeurIPS
  2024*. arXiv:2404.13076.
- Raji, I. D., Smart, A., White, R. N., Mitchell, M., Gebru, T., Hutchinson, B., Smith-Loud, J., Theron, D., and Barnes,
  P. 2020. Closing the AI Accountability Gap. *FAT\* 2020*: 33–44. doi:10.1145/3351095.3372873.
- Raji, I. D., Kumar, I. E., Horowitz, A., and Selbst, A. 2022. The Fallacy of AI Functionality. *FAccT 2022*.
  doi:10.1145/3531146.3533158.
- Schneiders, E., Seabrooke, T., Krook, J., Hyde, R., Leesakul, N., Clos, J., and Fischer, J. E. 2025. Objection
  Overruled! Lay People Can Distinguish Large Language Models from Lawyers, but Still Favour Advice from an LLM. *CHI
  2025*. arXiv:2409.07871.
- Sharma, M., Tong, M., Korbak, T., Duvenaud, D., Askell, A., Bowman, S. R., et al. 2024. Towards Understanding
  Sycophancy in Language Models. *ICLR 2024*. arXiv:2310.13548.
- Shi, F., Chen, X., Misra, K., Scales, N., Dohan, D., Chi, E., Schärli, N., and Zhou, D. 2023. Large Language Models Can
  Be Easily Distracted by Irrelevant Context. *ICML 2023*. arXiv:2302.00093.
- Steyvers, M., Tejeda, H., Kumar, A., Belem, C., Karny, S., Hu, X., Mayer, L., and Smyth, P. 2025. What Large Language
  Models Know and What People Think They Know. *Nature Machine Intelligence* 7: 221–231.
- Suresh, H., and Guttag, J. 2021. A Framework for Understanding Sources of Harm throughout the Machine Learning Life
  Cycle. *EAAMO 2021*. doi:10.1145/3465416.3483305.
- Vasconcelos, H., Jörke, M., Grunde-McLaughlin, M., Gerstenberg, T., Bernstein, M., and Krishna, R. 2023. Explanations
  Can Reduce Overreliance on AI Systems During Decision-Making. *PACM HCI 7 (CSCW1)*, Art. 129. doi:10.1145/3579605.
- Xie, J., Zhang, K., Chen, J., Lou, R., and Su, Y. 2024. Adaptive Chameleon or Stubborn Sloth. *ICLR 2024*.
  arXiv:2305.13300.
- Xu, R., Qi, Z., Guo, Z., Wang, C., Wang, H., Zhang, Y., and Xu, W. 2024. Knowledge Conflicts for LLMs: A Survey.
  *EMNLP 2024*. arXiv:2403.08319.
- Yang, X., et al. 2026. CrossLex: A Source-Grounded Benchmark for Cross-Jurisdictional Legal Reasoning in Large Language
  Models. arXiv:2608.01292. ⚠ preprint; full author list.
- Zheng, L., Guha, N., Arifov, J., Zhang, S., Skreta, M., Manning, C. D., Henderson, P., and Ho, D. E. 2025. A
  Reasoning-Focused Legal Retrieval Benchmark. *CS&Law 2025*. arXiv:2505.03970.
- ⚠ Warmth/competence/empathy and trust in LLM chatbots (N = 115). arXiv:2604.15316. Authors to confirm.

## Generative AI usage statement

⚠ To be written by the authors: which tools were used for drafting, analysis code and literature search, and that the
authors verified every number, quotation and citation.

---

## Appendix A. Where each number comes from

| Claim | Source |
|---|---|
| Round 2, all tables in 5.3–5.4 | `06_evaluation/paper_2026-10-31/analisis_ronda2.py` run on the production database, 31 Oct 2026 07:57 UTC; output `resultados_ronda2.json` (aggregates only) |
| Round 1 wrong-state first answers, 53% (57/107), by prompt and situation | same script, `ronda1_1a_otro_estado_corregida` (strict metric, place where the facts occurred) |
| 120 of 121 codes came from retrieval | all round-1 answers, 24 Oct (`replay_ronda1_2026-10-24`) |
| Noticed / would act by legal training, round 1 | final round-1 data by profile, 25 Oct |
| Table 2 (replay) | "Ronda 1 real" runs #1–#2 (A), #4–#5 (B), #12–#13 (B + reranker), #6–#7 (C) |
| Table 6 (recall@10) | `recall_sin_rerank.py`, `recall_apagar_fuentes.py` (24–25 Oct) |
| Power calculations | `analisis_ronda2.py`, `tamano_de_muestra` |

**Table A2. Round 2 by situation and prompt** (n = situations).

| Situation | Measure | Formal legal | Warm and comprehensive | Plain and cautious |
|---|---|---|---|---|
| Workplace messages | Comprehension | 63% (12) | 73% (13) | 71% (12) |
| | Trust (1–5) | 3.25 (8) | 4.10 (10) | 4.42 (12) |
| | Would act | 50% | 77% | 83% |
| | Noticed a problem | 17% | 8% | 17% |
| | Recall@10, first message | 8% | 36% | 25% |
| The photos | Comprehension | 63% (12) | 62% (13) | 58% (13) |
| | Trust (1–5) | 3.38 (8) | 3.90 (10) | 4.23 (13) |
| | Would act | 33% | 85% | 77% |
| | Noticed a problem | 17% | 23% | 15% |
| | Recall@10, first message | 21% | 25% | 35% |
| The summons | Comprehension | 58% (13) | 86% (14) | 75% (12) |
| | Trust (1–5) | 3.22 (9) | 3.82 (11) | 3.92 (12) |
| | Would act | 23% | 86% | 75% |
| | Noticed a problem | 0% | 0% | 17% |
| | Recall@10, first message | 42% | 57% | 27% |

## Appendix B. Three versions of the wrong-state metric

1. **Round 1 (mentions):** any mention of a place counts. Fails on "Querétaro, not Mexico City, governs".
2. **Dashboard (answer-key laws):** allowed codes = those of the laws in the answer key. Fails on "the photos", whose key
   is a general law, so Querétaro's own code counts as another state (inflates round 2 from 2% to about 8% of first
   answers).
3. **Strict (this paper):** the answer names the penal code of a state other than the one where the facts occurred
   (Querétaro, or Mexico City in that variant of the workplace scenario). Same regular expressions as
   `metrica_estricta.py` (24 Oct). For round 1, versions 2 and 3 give the same 53%.
