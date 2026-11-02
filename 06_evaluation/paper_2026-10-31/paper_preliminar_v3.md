# Where You Are and Who You Are: Applicability Errors and Misplaced Trust in a Legal RAG Assistant, Audited with Its Users

*Preliminary draft v3 (2 November 2026). Anonymous submission to ACM FAccT 2027. Round-2 data frozen on 2 November
2026, 09:27 UTC (last participant activity 05:30 UTC); collection continues. Changes from v2: data updated (68 → 79
participants); new Section 5.4 compares rounds 1 and 2 with the same prompt; new Section 5.7 on how participants with
and without legal training phrase their questions and whether the assistant guides them; new Section 5.8 on what
drives comprehension; the comprehension questionnaire is described in full (Table 0); round-1 answer metrics now use
the answer key participants saw (Appendix C). Every number has a source in Appendix A. Items marked ⚠ must be checked
before submission.*

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
when replayed on all 108 real conversations. Deployed in round 2 (79 participants so far), 8 of 187 first answers (4%)
named another state's code. With the same formal prompt in both rounds, wrong-state first answers to participants
without legal training fell from 74% to 4%, yet their comprehension did not change detectably (61% vs 63%). Two
findings explain why. First, people learned from the answer when it contained the right article: they answered "which
law applies?" correctly in 64% of situations in which the assistant had cited the expected article and in 32% of those
in which it had not. Second, people communicate differently: participants with legal training named the state in 63% of
first messages, those without it in 40%, and retrieval found the expected article for 56% of first messages that named
the state against 14% of those that did not. When the assistant asked for the state, lay participants supplied it in 41%
of cases, and retrieval then rose to 57%; legally trained participants almost never answered the question. Round 2 also
assigned each participant at random one of three system prompts. Among lay participants, a plain-and-cautious prompt
raised the share who would act on the answer from 39% to 81% (+42 points, 95% CI 21 to 62) and trust by 0.8 points on a
five-point scale (CI 0.2 to 1.4), with no detectable change in comprehension; the answers cited the correct law equally
often with all three prompts. Fixing
*where* also exposed *who*: after the gate, answers in a gender-neutral extortion scenario cited a law that protects only
women in 33% of replayed answers. We argue that legal RAG must be evaluated with the people it serves, that accuracy,
comprehension and trust must be measured separately, and that an assistant for lay users must ask for the facts on which
applicability depends.

**Keywords:** legal information access, retrieval-augmented generation, jurisdiction, user study, clarifying questions,
evaluation practices, overreliance, sycophancy, access to justice, Mexico

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
who most need free legal orientation are the least able to check which state's law a citation belongs to, and, as we
show, the least likely to say where the facts occurred. Lay people already prefer LLM-generated legal advice and say
they would act on it even when they can tell it apart from a lawyer's [Schneiders et al. 2025].

We report a two-round audit of an open-weight RAG assistant for Mexican criminal law, run with its intended users
rather than with expert-written questions. In each round, participants consulted the assistant in their own words about
three fictional situations whose correct answers depend on where the facts occurred. Between rounds we repaired the
failure that round 1 exposed and replayed every real round-1 conversation through the repaired system. In round 2 we
deployed the repair and assigned each participant at random one of three system prompts that differ in register and
tone. One prompt was used in both rounds, which lets us compare the rounds with the prompt held fixed.

We ask five research questions:

- **RQ1.** How often does the assistant cite law from a state other than the one where the facts occurred, and where in
  the pipeline does that law come from?
- **RQ2.** Do users notice these errors, and does legal training change that?
- **RQ3.** Does a system-level jurisdiction gate remove the error, does removing it improve users' comprehension, and
  what does it expose?
- **RQ4.** Does a plain-language, warmer prompt improve comprehension, or does it raise trust and willingness to act
  without improving comprehension?
- **RQ5.** Do people with and without legal training describe their problem differently, and can the assistant guide
  those who leave out the facts on which applicability depends?

Our contributions are: (1) evidence, from real conversations, that wrong-jurisdiction citations in legal RAG are mostly
a retrieval failure, invisible to most users; (2) a jurisdiction gate evaluated by replaying every real conversation,
then deployed, and the finding that removing the error did not by itself raise comprehension; (3) a randomized
comparison of three prompts showing that plain language raised trust and stated willingness to act among lay users
without raising their comprehension or the accuracy of the answers; (4) evidence that lay users omit the place where the
facts occurred far more often than legally trained users, that this omission, not legal vocabulary, drives the retrieval
gap between them, and that an assistant that asks for the place closes most of that gap; (5) the observation that
applicability has at least two conditions, where the person is and who the person is, and that the second surfaces only
after the first is fixed; and (6) a methodological lesson: our own metrics and answer keys misled us several times, and
we document how.

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

### 2.3 Asking for missing facts

Conversational search has long treated underspecified queries as a reason to ask a clarifying question rather than to
answer [Aliannejadi et al. 2019 ⚠ verify]. In legal help, the missing fact is often the one that decides applicability:
where the facts occurred, or who the parties are. Our design asks only when the place is missing, and only after a
first answer restricted to national law; Section 5.7 measures who answers that question and what it buys.

### 2.4 Lay users, trust and overreliance

Lay people tend to prefer LLM legal advice and report greater willingness to act on it than on a lawyer's advice
[Schneiders et al. 2025]. People overestimate the accuracy of LLM answers, more so for longer explanations [Steyvers et
al. 2025]. Fluent LLM explanations raise confidence and reliance without reliably raising accuracy, and subjective trust
and perceived clarity predict human–AI team performance poorly [Cohen et al. 2026 ⚠ preprint]. Hedged, first-person
expressions of uncertainty reduce, but do not eliminate, overreliance [Kim et al. 2024]. Explanations reduce
overreliance only when they are easier to verify than the task itself [Vasconcelos et al. 2023], and cognitive forcing
functions reduce it at a cost in user satisfaction [Buçinca et al. 2021].

### 2.5 Warmth, tone and sycophancy

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

### 2.6 Auditing across the pipeline

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
history before searching. The system prompt is used only to write the answer; it does not enter retrieval or the gate,
so for a participant's first message, what retrieval finds depends only on what the participant wrote.

**Round 1 configuration.** When a user named a state, the router added a search restricted to that state's code and
interleaved it with the general search. It did not remove other states' passages.

**Round 2 configuration (changes made between rounds).**

1. **Jurisdiction gate.** Before retrieval, an LLM step reads the user's own words (not the HyDE text, which can invent
   a place) and decides where the facts occurred. If it finds a state, retrieval is restricted to that state's code plus
   federal and general law. If it finds none, retrieval is restricted to federal and general law, so a state's penal
   code cannot be retrieved until the user names the state. A second rule decides whether the current question names a
   place so that a later message does not inherit a state from an unrelated earlier one.
2. **Reranker.** A cross-encoder reranker (Qwen3-Reranker-0.6B) reorders the fused candidates. On round-1 first
   messages, it raised recall@10 of the expected article from 25.3% to 35.0% (Table 7).
3. **Nine sources switched off for search** on 25 October, the day round 2 opened, by the research team through an
   administration page: among them the General Law on Women's Access to a Life Free of Violence and a technical note
   on "Ley Olimpia" (Section 5.9). Round 2 searches 42 sources and 6,766 passages. Round 1 and all replays used all 51.
4. **System prompts** (Section 4.3).

Answers took 12.2 seconds on average in round 2 (90% within 14.7 s).

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

Every situation text names the state where the facts occurred; participants decide whether to include it in their
messages.

### 4.2 Procedure and measures

Consent, a profile questionnaire, a practice question, then three situations. In each situation participants could send
the assistant up to six messages in their own words, then answered two multiple-choice comprehension questions (Table
0), rated their confidence in their own answers (1–5), said whether they had noticed a problem in the answers, and
whether they would act on them. From 26 October, round 2 added two five-point scales after each situation, written by
the legal expert: trust in the assistant's answer and perceived correctness of the legal information. The study ends
with the System Usability Scale (SUS) and two open questions.

**Table 0. Comprehension questions.** Every question also offers "I don't know"; the two "which law" questions also offer
"none of the options". Both rounds used the same six questions and the same answer key (Appendix C).

| Situation | Question | Correct answer |
|---|---|---|
| Workplace messages | Which offense and which law apply? | Querétaro Penal Code art. 167 Ter (Mexico City Penal Code art. 179 in that variant) |
| | Does it matter that this person supervises Alex's work? | Yes, it is more serious |
| The photos | Can it be an offense even though Cris sent the photos voluntarily? | Yes |
| | Which offense and which law apply? | General Law on Extortion art. 15 |
| The summons | Which penal code applies? | Querétaro's, where the fight happened |
| | Can Ariel ask for the case to be handled in Mexico City because he lives there? | No |

- **Comprehension:** share of the two questions answered correctly (aciertos), per situation. "I don't know" counts as
  incorrect. The application scores each situation when the participant submits it. Two caveats shape how we read
  this measure. Only the two "which law" questions depend on what the assistant said; the other four can often be
  answered from general knowledge (Section 5.8). And in "the photos", 22 of 60 round-2 participants chose Querétaro art.
  167 Quinquies, which the answer key itself calls relevant but scores as incorrect (Section 5.8).
- **Would act / noticed a problem:** share of situations with "yes".
- **Wrong-state code:** an answer names the penal code of a state other than the one where the facts occurred (regular
  expressions over code names; Appendix B explains why this strict version replaced two earlier ones).
- **Correct law / correct article:** the answer cites the law (and article) in the answer key.
- **Asks for the state:** the answer contains a question or direct request about where the facts occurred.
- **Names the state:** the participant's message names a Mexican state or Mexico City (regular expression).
- **Recall@10:** share of expected articles among the 10 passages the retriever returned for the participant's message.

We report differences with 95% confidence intervals from a bootstrap that resamples **participants** (4,000
replicates), because each person contributes up to three situations. We decided to report participants with and
without legal training separately after seeing the round-2 data; those subgroup analyses are exploratory.

### 4.3 Conditions

**Round 1** compared two prompts with participants assigned at random: the **formal legal** prompt (the original, written
for law students and professionals) and a plain-language prompt; a non-randomized pilot used the formal prompt.

**Round 2** assigns each participant at random one of three system prompts, all with the repaired retrieval:

| Condition (id in the data) | Name in this paper | What the prompt asks the model to do |
|---|---|---|
| `original` | **Formal legal** | Answer only from the context, in "clear, precise and professional legal Spanish" for law students and professionals; argumentative paragraphs; sections Answer / Legal basis / Conclusion / Doctrinal sources. Same prompt as round 1 (identical text in all 108 answers compared in Section 5.4). |
| `nuevo` | **Warm and comprehensive** | Everyday, empathetic language plus a full legal interview: elements of the offense, penalties, every procedural stage; always a "Legal basis" section; at most two questions; offers to draft complaints and filings once the state is known. The longest prompt. |
| `intermedio` | **Plain and cautious** | Everyday language, short paragraphs; insists on not overstating certainty, separating facts from hypotheses, and checking that a law applies to the people involved (age, relationship); drafts filings only if asked; sections Orientation / Legal basis / Options. Added on 28 October. |

The application assigns each new participant the condition with the fewest participants so far (ties broken at
random), and stores it before the first situation; participants do not see it. Because the third prompt was added on 28
October with 6 participants in each of the first two, the next six participants all received it; its first participant
consented on 29 October at 00:21 UTC. From 1 November the application assigns the condition with the fewest participants
*within the person's legal-training stratum* (classified from the profile, with the same rule as the analysis),
breaking ties by the overall count and then at random. Earlier assignments were not changed.

### 4.4 Participants

**Round 1** (9–21 October 2026): 45 participants, 33 completed; 26 without legal training and 19 with it (studies or
studied law, or works in a legal job). Recruited at a public university through in-person kiosks and a public link,
mostly students.

**Round 2** (25 October onward; frozen 2 November): 79 consented, 59 completed the whole study (183 situations, 361
messages to the assistant). Recruitment was through three public links shared in messaging groups (66 participants) and
in-person kiosks (13), and reached an older population than round 1 (Table 1b). 59 had no legal training and 20 had it
(same rule as round 1).

**Table 1. Round 2 participants by condition.**

| | Formal legal | Warm and comprehensive | Plain and cautious | Total |
|---|---|---|---|---|
| Consented | 27 | 26 | 26 | 79 |
| Completed the study | 21 | 19 | 19 | 59 |
| Without legal training | 21 | 19 | 19 | 59 |
| With legal training | 6 | 7 | 7 | 20 |

**Table 1b. Round 2 profile (all 79).** Highest education: completed bachelor's 37, master's 17, bachelor's in progress
10, high school 9, doctorate 5, middle school 1. Age: 18–24: 12; 25–34: 18; 35–44: 26; 45–59: 16; 60+: 7. AI assistant
use: daily 30, weekly 8, a few times a month 33, never 8.

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
| Answers citing the correct law ⚠ (see Appendix C) | 72.7% | 72.2% | — |
| Correct article, follow-up messages, change vs A | — | — | +13.0 points [1.9, 25.0] |
| Answers in "photos" citing the women's-violence law | 13% (15/112) | 33% (37/112) | 34% (38/112) |

The gate cut wrong-state answers by 57.9 points (95% CI −66.2 to −49.5) without losing correct-law citations. The
reranker added correct-article citations in follow-up messages (+10.5 points over B, CI −0.6 to 21.5; +13.0 over A).

**Deployed in round 2,** the gate held: 8 of 187 first answers (4.3%) named another state's code: 6 of 66 with the
formal legal prompt, 1 of 61 with the warm one and 1 of 60 with the plain one (warm − formal −7.5 points, CI −14.5 to
−0.6). Four of the six formal-prompt cases came from the 18 situations of its six legally trained participants. The share
of first answers citing the correct law did not differ by prompt (70%, 69%, 70%).

### 5.4 Same prompt, two rounds: fewer errors, the same comprehension

The formal legal prompt was used, with identical text, in both rounds. Comparing it across rounds holds the prompt fixed
and changes the system (gate, reranker, nine sources off) and the population (Section 4.4). The comparison is therefore
supporting evidence; the replay in Table 2, which keeps the conversations fixed, is the clean test of the system change.

**Table 3. Formal legal prompt, round 1 vs round 2** (n = people; differences in points, 95% CI, participant bootstrap).

| | Without legal training | | | With legal training | | |
|---|---|---|---|---|---|---|
| | Round 1 (7) | Round 2 (21) | Difference | Round 1 (9) | Round 2 (6) | Difference |
| First answer names another state's code | 74% | 4% | **−70 [−88, −51]** | 43% | 22% | −21 [−46, +1] |
| Assistant asks for the state | 0% | 53% | **+52 [39, 66]** | 0% | 33% | **+33 [11, 56]** |
| First answer cites the correct law | 63% | 65% | +1 [−19, +24] | 57% | 83% | **+27 [1, 53]** |
| First answer cites the correct article | 42% | 52% | +10 [−14, +37] | 43% | 78% | **+34 [6, 61]** |
| Comprehension (aciertos) | 61% | 63% | +2 [−18, +22] | 80% | 69% | −10 [−32, +10] |
| Would act on the answer | 56% | 39% | −16 [−57, +24] | 50% | 72% | +22 [−20, +62] |
| Noticed a problem | 0% | 13% | **+13 [4, 24]** | 14% | 6% | −8 [−24, +7] |

Among lay participants the system change removed almost all wrong-state first answers and made the same prompt ask for
the state in half of its answers, but comprehension did not change detectably. Noticing a problem rose from 0% to 13%,
plausibly because the assistant now said it lacked the state. With all three prompts and both legal-training groups
pooled, the same pattern holds in each situation: wrong-state first answers fell by 44 to 56 points (workplace 51% → 5%,
photos 60% → 3%, summons 48% → 5%), while comprehension changed by −5 to +8 points, none distinguishable from zero
(Appendix A, Table A3). Sections 5.7 and 5.8 explain why removing the error did not raise comprehension.

### 5.5 RQ4: plain language raised trust and willingness to act, not comprehension

**Table 4. Round 2, all participants, by prompt.** Values are means per situation; n = situations. Trust and
perceived-correctness scales exist only from 26 October.

| Measure | Formal legal | Warm and comprehensive | Plain and cautious |
|---|---|---|---|
| Comprehension (aciertos) | 65% (64) | 72% (60) | 70% (59) |
| Trust in the answer (1–5) | 3.56 (52) | 3.67 (51) | 4.02 (59) |
| Perceived correctness (1–5) | 3.77 (52) | 3.84 (51) | 4.03 (59) |
| Confidence in own answers (1–5) | 4.16 (64) | 4.10 (60) | 4.14 (59) |
| Would act on the answer | 48% (64) | 65% (60) | 75% (59) |
| Noticed a problem | 11% (64) | 13% (60) | 12% (59) |
| SUS (0–100), completers | 73.5 (21) | 75.4 (19) | 78.9 (19) |
| Answers that ask for the state | 47% | 35% | 31% |
| Words per answer | 448 | 491 | 433 |
| First answer cites the correct law | 70% (66) | 69% (61) | 70% (60) |
| First answer cites the correct article | 59% (66) | 56% (61) | 60% (60) |
| First answer names another state's code | 9% (66) | 2% (61) | 2% (60) |
| Recall@10, first message | 28% (66) | 37% (62) | 35% (60) |
| Median minutes per situation | 6.9 | 7.5 | 5.8 |

**Table 5. Round 2, participants without legal training only.** n = situations; participants in the header.

| Measure | Formal legal (21) | Warm and comprehensive (17) | Plain and cautious (19) |
|---|---|---|---|
| Comprehension (aciertos) | 63% (46) | 65% (44) | 70% (47) |
| Trust in the answer (1–5) | 3.38 (37) | 3.61 (38) | 4.17 (47) |
| Perceived correctness (1–5) | 3.60 (37) | 3.82 (38) | 4.13 (47) |
| Would act on the answer | 39% (46) | 61% (44) | 81% (47) |
| Noticed a problem | 13% (46) | 11% (44) | 9% (47) |
| First answer cites the correct law | 65% (48) | 67% (45) | 71% (48) |
| First answer cites the correct article | 52% (48) | 51% (45) | 60% (48) |

**Table 6. Differences between prompts (percentage points or scale points), 95% CI from a participant bootstrap.**

| Measure | Warm − Formal | Plain − Formal | Plain − Warm |
|---|---|---|---|
| *Without legal training* | | | |
| Would act | +22 [−4, +49] | **+42 [21, 62]** | +20 [−5, +44] |
| Trust in the answer (1–5) | +0.23 [−0.36, 0.86] | **+0.79 [0.24, 1.40]** | **+0.57 [0.05, 1.09]** |
| Comprehension | +2 [−17, +20] | +7 [−11, +25] | +5 [−11, +22] |
| Noticed a problem | −2 [−16, +13] | −5 [−18, +9] | −3 [−17, +11] |
| *All participants* | | | |
| Would act | +17 [−8, +40] | **+26 [5, 47]** | +10 [−12, +32] |
| Trust in the answer (1–5) | +0.11 [−0.37, 0.65] | +0.46 [−0.09, 1.02] | +0.35 [−0.13, 0.83] |
| Perceived correctness (1–5) | +0.07 [−0.43, 0.63] | +0.27 [−0.33, 0.88] | +0.19 [−0.33, 0.70] |
| Comprehension | +7 [−9, +22] | +5 [−10, +19] | −2 [−16, +12] |
| Noticed a problem | +2 [−10, +16] | +1 [−11, +14] | −2 [−15, +12] |
| First answer cites the correct law | −1 [−17, +16] | 0 [−14, +15] | +1 [−13, +16] |
| First answer cites the correct article | −3 [−23, +15] | +1 [−16, +18] | +4 [−13, +23] |
| Answers that ask for the state | −12 [−29, +5] | **−16 [−30, −1]** | −4 [−18, +10] |

Among lay participants, the plain-and-cautious prompt, which explicitly tells the model not to overstate certainty,
produced the highest trust (4.17 of 5) and the highest willingness to act (81%); both differences with the formal prompt
exclude zero, and trust also exceeds the warm prompt's. It did not produce answers that were more often correct (Table 6,
all participants) or participants who understood more (+7 points, CI −11 to +25), and it asked for the state less often
than the formal prompt. Detection of problems stayed between 9% and 13% with all three prompts.

**Is the effect an artifact of recruitment dates?** The plain prompt's participants all arrived from 29 October, while
seven participants of the other two prompts arrived earlier. Restricting the comparison to participants who consented
from 29 October 00:21 UTC (13, 13 and 17 lay participants), the plain − formal differences remain: trust +0.79 [0.28,
1.41], would act +35 [13, 57], comprehension +11 [−8, +30].

Trust tracked comprehension weakly and inconsistently. With the formal prompt, comprehension was 73% in situations where
participants rated trust 4 or 5 (32 situations) and 50% where they rated it 1–3 (20); with the plain-and-cautious prompt,
67% (44) and 77% (15). With the formal prompt, trust followed understanding; with the plain prompt it did not. These are
descriptive, without intervals.

By situation (Appendix A, Table A2), the difference in willingness to act is largest in the summons (41% formal vs 67%
warm and 75% plain), where acting on a wrong answer has a clear consequence (ignoring a summons from another state).

### 5.6 Legal training and the prompts

**Table 6b. Round 2 by legal training.** Comprehension in aciertos; n = situations. Differences: with − without legal
training, 95% CI from a participant bootstrap.

| Measure | Without legal training (57 participants) | With legal training (18) | Difference [95% CI] |
|---|---|---|---|
| Comprehension, prompts pooled | 66% (137) | 76% (46) | +10 [−4, +23] |
| Comprehension, formal legal | 63% (46) | 69% (18; 6 people) | +6 [−17, +29] |
| Comprehension, warm and comprehensive | 65% (44) | 91% (16; 6 people) | +26 [13, 42] |
| Comprehension, plain and cautious | 70% (47) | 67% (12; 6 people) | −4 [−29, +18] |
| Trust in the answer (1–5), pooled | — | — | +0.02 [−0.49, 0.49] |
| Would act, pooled | — | — | +7 [−16, +28] |
| Noticed a problem, pooled | — | — | +4 [−8, +18] |

**Table 6c. Round 2, participants with legal training, by prompt** (descriptive; six people per prompt; n = situations).

| Measure | Formal legal | Warm and comprehensive | Plain and cautious |
|---|---|---|---|
| Comprehension | 69% (18) | 91% (16) | 67% (12) |
| Trust in the answer (1–5) | 4.00 (15) | 3.85 (13) | 3.42 (12) |
| Would act | 72% | 75% | 50% |
| Noticed a problem | 6% | 19% | 25% |
| Recall@10, first message | 36% | 63% | 29% |
| First message names the state | 56% | 81% | 50% |

The plain-and-cautious prompt, which most persuaded lay participants, went the other way with legally trained ones:
lower trust, lower willingness to act, more problems noticed. With four to six people per cell this is a hypothesis for
the next round, not a finding.

The high comprehension of legally trained participants with the warm prompt should not be attributed to the prompt.
Because the prompt does not enter retrieval, recall for a first message depends only on what the participant wrote.
These six participants named the state in 81% of their first messages, and five of six did so already in their first
situation, before seeing any answer; their recall was correspondingly high (Section 5.7). Random assignment gave this
cell participants who wrote more complete questions, and better retrieval raises comprehension (Section 5.8).

### 5.7 RQ5: how people ask, and whether the assistant guides them

**Table 7a. First message of each situation, round 2, by legal training** (52 participants without legal training, 142
situations; 16 with it, 46 situations).

| First message | Without legal training | With legal training | Difference [95% CI] |
|---|---|---|---|
| Names the state | 40% | 63% | **+23 [5, 41]** |
| Names the offense (harassment, extortion…) | 27% | 39% | +12 [−3, +30] |
| Names a law, code or article | 4% | 9% | +5 [−4, +16] |
| Words | 32 | 38 | +6 [−5, +17] |
| Recall@10 | 30% | 44% | +14 [−1, +28] |

Legally trained participants did not write in a more technical register: few participants in either group named a law
or an article. They included the decisive fact, the place, more often. Round 1 points the same way (60% vs 43% named
the state; +17 [−3, +36]).

Naming the state is what matters for retrieval. Across all round-2 first messages, recall@10 was 56% when the message
named the state (86 situations) and 14% when it did not (102). With the gate, a message without a place retrieves only
federal and general law, so a state code such as Querétaro's cannot be found. People did not learn to name the state
over the study: 49% of first messages named it in participants' first situation and 44% in their later ones.

**Table 7b. Situations whose first message did not name the state, round 2.**

| | Without legal training | With legal training |
|---|---|---|
| The assistant asked for the state (first answer) | 81% (85) | 65% (17) |
| When asked, the participant then gave the state | **41%** (69) | **9%** (1 of 11) |
| Recall@10, first message | 15% (85) | 9% (17) |
| Recall@10, message in which the state was given | **57%** (31) | — (2) |

The guidance works for lay participants: when the assistant asked, four in ten supplied the state, and in that message
retrieval found the expected article almost four times as often. Legally trained participants who left out the state
almost never answered the question; they also sent fewer messages per situation (1.5 vs 2.0). We do not yet know why;
the open answers at the end of the study may tell.

**Table 7c. Best recall@10 reached in the conversation.**

| | Without legal training | With legal training | Difference [95% CI] |
|---|---|---|---|
| Round 1 | 32% | 21% | −11 [−26, +4] |
| Round 2, first message | 30% | 44% | +14 [−1, +28] |
| Round 2, best in the conversation | 44% | 50% | +6 [−11, +23] |

Over the conversation, the retrieval gap between the two groups shrank from 14 to 6 points. In round 1, when the
assistant asked for the state in 20% of situations lacking it, the best recall reached by lay participants was 32%; in
round 2 it was 44%. The weak point is the first answer: it is written before the assistant asks, from a retrieval that
could not reach state law, and six in ten lay participants did not answer the question.

### 5.8 What drives comprehension

**The questionnaire.** In both rounds, lay participants answered the two "which law" questions correctly in under half
of situations (42% in round 1, 49% in round 2; +7 [−7, +21]) and the other four in about three quarters (77% and 76%;
−2 [−14, +10]). The four general questions can be answered without the assistant and leave little room to improve;
this dilutes any effect of the system on the comprehension score.

**The answer.** Comprehension depends on what the assistant said. In situations where the assistant cited the expected
article in some answer, participants answered "which law applies?" correctly far more often:

**Table 8. Participants answering "which law applies?" correctly, by whether the assistant cited the expected article
in the situation** (workplace messages and photos; both rounds pooled; n = situations).

| | Assistant cited it | Did not | Difference [95% CI] |
|---|---|---|---|
| All participants | 64% (106) | 32% (82) | **+32 [20, 45]** |
| Without legal training | 59% (76) | 30% (57) | **+29 [13, 44]** |
| With legal training | 77% (30) | 36% (25) | **+41 [18, 63]** |
| Workplace messages only | 79% (58) | 42% (36) | **+38 [18, 57]** |
| Round 1 only | 61% (33) | 31% (35) | +29 [7, 51] |
| Round 2 only | 66% (73) | 32% (47) | +34 [16, 49] |

This is an association, not an experiment: participants who ask better questions may both obtain the article and answer
better on their own. That the association holds among lay participants and within each round makes that explanation
less likely but does not exclude it. Read with Section 5.7, it explains Table 3: the gate stopped the assistant from
citing *another* state, but in the workplace situation the first answer cited the expected article in only 33% of lay
participants' situations in round 2, and most lay first messages did not name the state (Section 5.7). People cannot learn an
article the assistant did not give them.

**The answer key.** In "the photos", the key accepts only the General Law on Extortion. Yet participants chose the
Querétaro article on threatening to publish intimate images (art. 167 Quinquies), which the key's own reference text
calls applicable, almost as often: 10 vs 9 of 34 in round 1 and 22 vs 24 of 60 in round 2. Counting both as correct
would raise this question from 26% to 56% (round 1) and from 40% to 77% (round 2). The issue affects both rounds equally
and does not bias the comparisons, but it lowers comprehension in "the photos" for a defensible answer. ⚠ The legal
expert must decide whether the paper scores art. 167 Quinquies as correct.

### 5.9 Fixing *where* exposed *who*

Once the gate kept the right state's law in the context, a different applicability error became visible. "The photos"
is gender-neutral, yet in the replay with the gate, 33% of answers (37 of 112) cited the General Law on Women's Access to
a Life Free of Violence, against 13% without it (Table 2): with other states' codes removed, this general law, which
applies nationwide but protects only women, rose in the ranking. The citation is correct about *where* and wrong about
*who*. On 25 October, before round 2 opened, the team switched that law and eight other sources off for search; no
round-2 "photos" answer cited it (0 of 61). This is a stopgap that removes the law for the people it does protect. The
principled fix is a second applicability condition, the person's characteristics (sex, age, relationship to the other
party), that the system must ask about or infer before citing a law that depends on them. We have built the first step,
an editor page where legal experts tag whole documents with the person categories they apply to; the filter itself is
future work.

### 5.10 Retrieval is still the ceiling

**Table 9. Recall@10 of the expected articles, round-1 first messages replayed through each configuration.**

| Configuration | All situations | Photos |
|---|---|---|
| HyDE only (round 1) | 18.9% | — |
| Round 2 without reranker | 25.3% | 12.3% |
| Round 2 with reranker | 35.0% | 24.6% |
| Round 2 with reranker, 9 sources off | 37.3% | 27.2% |

Even with the reranker, the retriever brings the expected article into the top 10 for about a third of first messages,
and for one in seven when the message does not name the state (Section 5.7). The model cites the correct law far more
often (69–70%) than the retriever finds the exact article, because neighboring articles of the right law often suffice;
but the correct *article* is cited in only 56–60% of first answers.

## 6. Discussion

### 6.1 The failure is applicability, not hallucination

Wrong-state citations were real articles from real codes, retrieved and faithfully reproduced. A metric that checks
whether a citation exists, or even whether it supports the sentence, would score many of them as correct. Legal RAG needs
an applicability check: does this law govern *these* facts, *here*, for *this* person? Prompting does not supply that
check (round 1's plain prompt asked for the state and still cited other states); changing what the model sees does
(Table 2).

### 6.2 Accuracy, comprehension and trust are three different outcomes

Our two interventions each moved one outcome and left the others. Repairing retrieval removed almost all wrong-state
citations (Tables 2 and 3) but did not detectably raise comprehension. Changing the prompt raised trust and willingness
to act among lay participants (Table 6) but did not change the accuracy of the answers or comprehension. An evaluation
that measured only one of the three would have reached the wrong conclusion about the other two: a system benchmark
would have declared the gate a success for users, and a satisfaction survey would have declared the plain prompt one.
The link between them runs through the specific content of the answer: participants understood when the assistant gave
them the right article (Table 8), and the assistant gave it when they had told it where they were (Section 5.7).

### 6.3 Tone is a safety variable

Round 2 replicates, with random assignment and three prompts, the pattern round 1 only suggested: plain language raised
stated willingness to act (by 42 points among lay participants with the plain-and-cautious prompt) and trust (0.8 scale
points) more clearly than it raised comprehension (+7 points, not distinguishable from zero). This is consistent with
work showing that fluency raises reliance more than accuracy [Cohen et al. 2026; Steyvers et al. 2025] and that warmth
trades off against reliability [Ibrahim et al. 2025]. Two details sharpen it. First, our manipulation did not change
the model, the retrieval or the cited law: the share of first answers citing the correct law was 69–70% in all three
conditions. What changed was how persuasive the same evidence sounded. Second, telling the model to be cautious did not
make users cautious: the plain-and-cautious prompt produced the *highest* trust, and with it, trust no longer tracked
understanding. Plain language is still the right goal for access to justice [Hagan 2024]; the formal prompt's low
willingness to act is not a virtue, since participants also did not understand it better. The implication is that
plain-language legal assistants need mechanisms that make limits visible in ways users act on, and that the trust a
prompt produces is not evidence that users understood. The opposite reaction of legally trained participants to the
plain prompt (Table 6c), if confirmed, would mean that the right tone depends on who is asking.

### 6.4 Lay users omit the fact that decides applicability; the assistant must ask

The difference between lay and legally trained participants was not vocabulary but knowing which fact matters. Six in
ten lay first messages omitted the state, and without it retrieval could not reach state law. A legal assistant for the
general public therefore cannot assume that the question contains what the answer depends on. Asking works: when our
assistant asked, lay participants who supplied the place quadrupled retrieval of the expected article, and the gap with
legally trained participants shrank from 14 to 6 points. Two design consequences follow. First, the assistant should ask
*before* answering when a decisive fact is missing, rather than answering from national law and asking at the end, since
the first answer is the one most people act on and six in ten did not answer the question. Second, the same logic
extends to *who* (Section 5.9): the person's characteristics are another fact lay users will not volunteer.

### 6.5 Applicability has more than one condition

The gate solved *where* and exposed *who*. Switching off the women's-violence law fixed the gender-neutral scenario at the
price of hiding the law from the women it protects. A legal assistant must reason about the person, not only the place,
and must ask when the answer depends on facts the user has not given. Each repair moves the error to the next condition
the system does not model, which is an argument for evaluating with real users, whose stories contain the conditions
benchmark authors did not anticipate.

### 6.6 Our metrics and answer keys misled us

Our first wrong-state metric counted any mention of a place: the correct summons answer "Querétaro, not Mexico City,
governs" scored as citing Mexico City. Our second, the version in the study dashboard, treated as allowed only the codes
of the laws in the answer key; in "the photos" the key is a general law, so citing Querétaro's own penal code, which is
the right state, counted as an error, inflating round-2 wrong-state rates from 4% to about 14%. We report the strict
version, defined by the place where the facts occurred (Appendix B). The comprehension key for "the photos" scores as
wrong an answer its own reference calls applicable (Section 5.8). And an edit to the round-1 study definition made after
the round closed silently changed the answer key our analysis read, inflating round-1 "correct law" rates by 6 to 13
points until we pinned the version participants saw (Appendix C). Applicability metrics need the same scrutiny as the
systems they score, and analyses must pin the definition that participants actually saw.

## 7. Limitations

- **Small samples.** 21–27 participants per prompt; differences in comprehension below about 20 points cannot be
  detected yet (Section 8). The comprehension result is an absence of evidence, not evidence of absence.
- **Exploratory subgroups.** We decided to separate participants by legal training after seeing the data. Legally
  trained cells have 4 to 6 people per prompt. Assignment has been stratified by legal training since 1 November.
- **Different populations between rounds.** Round 1 recruited mostly students at university kiosks; round 2 mostly
  older adults through messaging groups. The comparison across rounds (Table 3) mixes the system change with the
  population change; the replay (Table 2) does not.
- **Association, not causation,** in Table 8 and Section 5.7.
- **The comprehension questionnaire** has six multiple-choice questions, four answerable without the assistant, no
  pre-test, and one key that scores a defensible answer as wrong (Section 5.8).
- **Recruitment dates for the third prompt.** Its participants arrived from 29 October; restricting to that period does
  not change the result (Section 5.5), but its first six participants were assigned consecutively.
- **Self-reported willingness to act**, not behavior. Trust scales exist only from 26 October.
- **Prompts differ in more than tone** (length, structure, whether they ask for the state, whether they offer to draft
  filings), so we cannot isolate tone.
- **Metrics are automatic** (regular expressions over answers and messages). Human grading by legal experts is pending
  (0 answers graded so far).
- **Same model as judge** in our earlier expert benchmark [Panickssery et al. 2024]; not used for any number in this
  draft.
- **Nine sources switched off** between rounds, so round 1 and round 2 corpora differ.

## 8. How much more data

Using the spread observed between participants in round 2 (standard deviation of each person's mean: 0.26 for
comprehension, 0.82 for trust), two-sided α = 0.05 and 80% power:

| Claim we want to make | Participants needed per prompt |
|---|---|
| Detect a 15-point difference in comprehension | 46 |
| Detect a 10-point difference in comprehension | 103 |
| Show comprehension differs by less than ±10 points (equivalence) | 112 |
| Detect a 0.5-point difference in trust (1–5) | 43 |
| Detect a 10-point difference in noticing a problem | 68 |

Read the other way, the smallest difference detectable with 80% power:

| Participants per prompt | Comprehension | Trust (1–5) |
|---|---|---|
| 22 | 22 points | 0.70 |
| 30 | 18 points | 0.60 |
| 45 | 15 points | 0.49 |

The willingness-to-act and trust differences between the formal and plain-and-cautious prompts are already detected.
The submission will report about 25 participants per prompt, with comprehension framed as an open question;
collection continues toward 30–45 per prompt, with assignment within strata of legal training, for the camera-ready
version or a preregistered follow-up. A follow-up should measure comprehension with questions that depend on the answer,
and should test asking for the place before the first answer.

## 9. Ethical considerations

Fictional situations, anonymous codes, informed consent approved by ⚠ [institution / protocol id], withdrawal with
immediate deletion, and deletion on request by code. No names, emails or IP addresses are stored with responses. The
assistant was evaluated as a research system; it states that it does not replace a lawyer. The situations include
sexual harassment and threats to publish intimate images; participants could stop at any time. Switching off the
women's-violence law is a research stopgap with a cost we name in Section 6.5.

## 10. Conclusion

A legal assistant can cite real law, sound clear and kind, and still mislead, because the law it cites belongs to
another state or protects another kind of person. Most such errors came from retrieval, most users did not see them, and
a system-level gate removed almost all of the wrong-state citations, without making people understand more. People
understood when the assistant gave them the right article, and the assistant gave it when they had said where they
were, which lay users did far less often than legally trained ones. Asking for the place closed most of that gap.
Making the assistant speak plainly, which is the right goal for access to justice, raised trust and willingness to act
without raising comprehension or accuracy. Evaluations of legal AI should be run with the people it is meant to serve,
should measure accuracy, comprehension and trust separately, should check applicability (where and who), and should
treat both tone and the questions the assistant asks as part of the safety case.

---

## References (⚠ = verify before submission)

- Aliannejadi, M., Zamani, H., Crestani, F., and Croft, W. B. 2019. Asking Clarifying Questions in Open-Domain
  Information-Seeking Conversations. *SIGIR 2019*. ⚠ verify details.
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

All scripts are in `06_evaluation/paper_2026-10-31/` and were run on the production database on 2 November 2026,
09:27–10:30 UTC. Outputs contain aggregates only.

| Claim | Source |
|---|---|
| Round 2, Tables 1, 4, 5, 6, 6b, 6c, A2; Section 8 | `analisis_ronda2.py` → `resultados_ronda2.json` |
| Round 1 wrong-state first answers, 53% (57/107), by prompt and situation | same script, `ronda1_1a_otro_estado_corregida` |
| Table 3 (same prompt, two rounds) | `puente_ronda1_ronda2.py` → `puente.json` |
| Section 5.4 by situation; Section 5.8 questionnaire; Table A3 | `por_pregunta_y_escenario.py` → `por_pregunta.json` |
| Table 8; Section 5.5 recruitment-date check | `pruebas_aprendizaje_y_fecha.py` → `pruebas.json` |
| Tables 7a–7c | `como_preguntan.py` → `como_preguntan.json` |
| Recall by naming the state; Table 6c last two rows | `recall_primer_mensaje.py`, `estado_por_orden_de_situacion.py` |
| 120 of 121 codes came from retrieval | all round-1 answers, 24 Oct (`replay_ronda1_2026-10-24`) |
| Noticed / would act by legal training, round 1 | final round-1 data by profile, 25 Oct |
| Table 2 (replay) | "Ronda 1 real" runs #1–#2 (A), #4–#5 (B), #12–#13 (B + reranker), #6–#7 (C) |
| Table 9 (recall@10) | `recall_sin_rerank.py`, `recall_apagar_fuentes.py` (24–25 Oct) |

**Table A2. Round 2 by situation and prompt** (n = situations).

| Situation | Measure | Formal legal | Warm and comprehensive | Plain and cautious |
|---|---|---|---|---|
| Workplace messages | Comprehension | 67% (21) | 75% (20) | 71% (19) |
| | Trust (1–5) | 3.47 (17) | 3.71 (17) | 4.26 (19) |
| | Would act | 57% | 60% | 74% |
| | Noticed a problem | 14% | 10% | 16% |
| | Recall@10, first message | 18% | 38% | 32% |
| | First answer names another state's code | 14% | 0% | 0% |
| The photos | Comprehension | 64% (21) | 58% (19) | 60% (20) |
| | Trust (1–5) | 3.59 (17) | 3.63 (16) | 4.05 (20) |
| | Would act | 48% | 68% | 75% |
| | Noticed a problem | 14% | 32% | 10% |
| | Recall@10, first message | 24% | 23% | 35% |
| | First answer names another state's code | 10% | 0% | 0% |
| The summons | Comprehension | 64% (22) | 81% (21) | 78% (20) |
| | Trust (1–5) | 3.61 (18) | 3.67 (18) | 3.75 (20) |
| | Would act | 41% | 67% | 75% |
| | Noticed a problem | 5% | 0% | 10% |
| | Recall@10, first message | 41% | 50% | 38% |
| | First answer names another state's code | 4% | 5% | 5% |

**Table A3. Rounds 1 and 2 by situation, participants without legal training, all prompts pooled** (n = situations in
round 1 / round 2; differences with 95% CI).

| Situation | Measure | Round 1 | Round 2 | Difference |
|---|---|---|---|---|
| Workplace messages (23 / 46) | First answer names another state's code | 65% | 4% | −61 [−80, −39] |
| | First answer cites the correct article | 43% | 33% | −11 [−35, +13] |
| | Comprehension | 71% | 69% | −2 [−20, +16] |
| The photos (24 / 46) | First answer names another state's code | 75% | 0% | −75 [−92, −58] |
| | First answer cites the correct article | 29% | 46% | +17 [−8, +40] |
| | Comprehension | 50% | 58% | +8 [−8, +23] |
| The summons (21 / 49) | First answer names another state's code | 62% | 4% | −58 [−78, −35] |
| | First answer cites the correct article | 71% | 84% | +12 [−9, +35] |
| | Comprehension | 74% | 71% | −2 [−22, +17] |

## Appendix B. Three versions of the wrong-state metric

1. **Round 1 (mentions):** any mention of a place counts. Fails on "Querétaro, not Mexico City, governs".
2. **Dashboard (answer-key laws):** allowed codes = those of the laws in the answer key. Fails on "the photos", whose key
   is a general law, so Querétaro's own code counts as another state (inflates round 2 from 4% to about 14% of first
   answers).
3. **Strict (this paper):** the answer names the penal code of a state other than the one where the facts occurred
   (Querétaro, or Mexico City in that variant of the workplace scenario). Same regular expressions as
   `metrica_estricta.py` (24 Oct). For round 1, versions 2 and 3 give the same 53%.

## Appendix C. The round-1 answer key

Round-1 participants saw version 7 of the study definition, in which the correct answer to "which law applies?" in "the
photos" is the General Law on Extortion, art. 15, and the expected articles are arts. 15 and 17 of that law. On 21
October at 19:19 UTC, after the round had closed (one later situation, in another scenario, was submitted at 19:33), the
legal expert edited the definition in the application (version 9): she added an option "both should be examined"
(extortion and Querétaro art. 167 Quinquies) as the correct answer, and added art. 167 Quinquies to the expected
articles. No participant saw or chose the new option, and the comprehension scores stored at submission used version 7.
Our analysis scripts, however, read the expected articles from the current definition, which counted citing Querétaro's
code in "the photos" as citing the correct law. This inflated round-1 "first answer cites the correct law" by 6 to 13
points depending on the group (for example, formal prompt, all participants: 71% → 60%). All round-1 numbers in this
draft use the archived version 7 (`06_evaluation/estudio_ronda1_2026-10-13/piloto_penal_v7_final.yaml`). The wrong-state
metric and comprehension are unaffected. ⚠ The replay in Table 2 was run after the edit; its "correct law" row must be
checked against version 7 before submission (the wrong-state rows are unaffected).
