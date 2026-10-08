# Project brief: a legal RAG assistant for Mexican law (context for brainstorming a FAccT 2027 paper)

> Purpose of this file: give another AI assistant full context on what we built, measured and learned, so it can help
> with ideas for a paper. It includes the main results **and** side details that may or may not be useful.
> Numbers marked "measured" come from real runs. Anything about the user study is a **plan**, not a result.

---

## 1. One-paragraph summary

We built and deployed a retrieval-augmented generation (RAG) assistant that answers questions about Mexican law, citing
the exact article of the right code. It runs on an **open-weight LLM hosted on our own GPU** (Gemma 4, 26B-A4B MoE,
4-bit, llama.cpp; no commercial API), with Postgres + pgvector and a hand-built hybrid search. A criminal-law expert
(our collaborator, "the expert") wrote 163+ benchmark questions with rubric criteria. We measured BM25, dense, hybrid
and several query-expansion strategies, found and fixed several evaluation failures, and added a second tool: a guided
**form-filling assistant** (e.g. a no-fault divorce filing in Mexico City) for the general public where the LLM only
collects facts and a lawyer-reviewed template produces the legal text. Target venue: **ACM FAccT 2027** (abstract
due 2026-10-27, paper 2026-11-03, 14 pages, anonymized). Planned next step: a user study with law students and lay users.

---

## 2. Why this domain is interesting (sociotechnical context)

- **Fragmented law.** Mexico has a Federal Penal Code, a National Code of Criminal Procedure (CNPP, national), and a
  separate penal code for each of the 32 states. The same offence (e.g. sexual harassment, kidnapping) has different
  article numbers, definitions and penalties per state. A correct-sounding answer citing the wrong state's code is
  invalid, and a non-lawyer cannot tell.
- **Historical names.** Mexico City was the "Distrito Federal" until 2016; many codes still carry that name
  ("Código Civil para el Distrito Federal"). Both names appear in questions and documents.
- **Procedural reform in progress.** The new National Code of Civil and Family Procedure (CNPCF) applies to family
  matters in Mexico City from 2026-06-01, replacing the local procedure code. Older practice manuals (2008-era) are
  outdated. A RAG system can mix old and new law.
- **Access to justice.** Legal aid is scarce; many people search online or ask chatbots. Family and criminal matters
  are high-stakes (detention, custody, domestic violence). Technical legal defence is mandatory in family trials
  (CNPCF art. 666), so a tool must not pretend to replace a lawyer.
- **Scanned sources.** Many legal books and form manuals exist only as scanned PDFs, so OCR quality affects what the
  system can know.

---

## 3. System (as built)

### 3.1 Corpus and ingestion
- Topic "derecho_penal_mexicano": **46 documents, 8,641 chunks (3,755 are statute articles), ~3.4 M words.**
  - 7 codes: Federal Penal Code (CPF), CNPP, penal codes of Mexico City (CDMX), State of Mexico (Edomex), Morelos, Querétaro (plus Morelos-related codes).
  - General laws: kidnapping (LGPSDMS), extortion, organized crime (LFCDO), victims (LGV).
  - ~30 doctrinal books (criminal law theory, procedure).
- Topic "derecho_familiar" (being cleaned by the expert, excluded from current tests): Mexico City Civil Code and Civil
  Procedure Code, CNPCF, family-law books, a scanned 2008 forms manual.
- PDF → Markdown: digital PDFs with pymupdf4llm on the server; **scanned pages are detected per page and sent to a
  separate OCR machine** (Mac mini, Docling + Apple Vision). On real scans Docling beat Tesseract (Tesseract interleaved
  two-page spreads and read bleed-through). Docling sometimes drops or reorders a paragraph.
- Ingest UI with **diagnostics per document** (e.g. "article numbers skip from 35 to 37", "articles glued together",
  "page headers inside text") and a **human sign-off ("visto bueno")** per warning and per document, with the
  reviewer's name and date; a sign-off becomes stale if the document changes.

### 3.2 Chunking
- Statutes: **one article per chunk**, with the law's full name and its hierarchy (Book › Title › Chapter › Article)
  prepended to the text that is embedded and indexed: `Fuente: <LAW NAME> (<file>)`.
- Books: sentence-based chunking (pysbd).
- Article-label edge cases that broke citations and were fixed: "Bis", "Ter", "Quáter", "737 A / 737 B" (single-letter
  suffix), `ARTÍCULO *35`, bold or orphan chapter headings, page headers glued into articles. Example: ~2/3 of the
  Morelos penal code's articles were glued to the previous article before the fix.

### 3.3 Retrieval
- **BM25** (in-memory, hand-written), **dense** (Qwen3-Embedding-0.6B served by HF TEI, pgvector), **hybrid** =
  Reciprocal Rank Fusion (RRF) of both.
- **HyDE**: the LLM drafts a hypothetical statute passage; it is embedded together with the question.
- **Decomposition**: the LLM splits comparative questions ("compare CDMX vs Querétaro on X") into one sub-query per
  jurisdiction; results are interleaved.
- **Code routing (ours, no LLM)**: a curated table of codes with names, aliases and acronyms (e.g. "Distrito Federal" →
  CDMX). Detection is accent-insensitive and typo-tolerant (edit distance ≤ 1 for words of 6+ letters in phrases,
  8+ alone). For each code named in the question, an extra search restricted to that code is interleaved with the
  normal search.
- **Neighbours**: adjacent articles added to the context after ranking.
- UI shows every stage (sub-queries, routes, retrieved chunks and scores) for transparency/debugging.

### 3.4 Generation and judging
- Gemma 4 (26B-A4B MoE, Q4, llama.cpp, 4 parallel slots) on our own GPU server.
- The same model is the **LLM judge** for the benchmark (a known limitation).

### 3.5 Form-filling assistant ("trámites")
- Separate page for the general public. **State machine**: START → TRIAGE (is this the right procedure? e.g. if both
  spouses agree, suggest mutual divorce instead) → INTERVIEW (one question at a time) → REVIEW → DOCUMENT.
- **The LLM never writes legal text.** It only: chooses the form from the person's description, extracts facts from
  free-text answers, checks whether an address is complete, and answers side questions via the RAG.
- The document is produced by **code** from a template written/reviewed by a lawyer (conditional blocks, loops over
  children, automatic numbering). Missing data shows as `[FALTA: field]`, never invented.
- **Privacy by design**: the person's answers and draft live only in their browser (localStorage) and travel with each
  request; the server stores and logs nothing personal (logs only state, duration and number of LLM calls).
- Completeness checks without the LLM where possible: phone, e-mail, full date, full name (asks for surnames),
  amounts, percentages; address parts checked by an LLM call. Person can say "leave it as is".
- Special flows built from expert input: **spouse's address unknown** → the filing requests official searches
  (IMSS, ISSSTE, SAT, INE, CFE) and, failing that, service by public notice (edictos) per CNPCF arts. 203/209-II.
  Pronoun resolution ("I live with the children" → applicant's name); "at my house" disambiguated against known addresses.
- Forms are stored in the DB with versions and states (draft → reviewed → published); only published forms are
  offered to the public. Source scans and published snapshots in object storage (MinIO). The first form (no-fault
  divorce, Mexico City) is still a **draft awaiting the expert's legal review** (8 open points: competence article,
  evidence, missing clause for adult children who need support, wording of the mandatory-lawyer warning, etc.).
- Measured issue fixed: turns took >1 minute with two concurrent users because LLM calls blocked the server event
  loop; moved to a thread pool and added per-turn timing and LLM-call counts in the UI.

---

## 4. Benchmarks

Written by the criminal-law expert. Each question has rubric criteria:
- **must** (required content, usually "cites article X of code Y"), **should** (nice to have), **error** (a specific
  mistake that fails the answer; formerly called "must_not").
- Optional per-set **judge notes** (extra instructions for the judge), snapshotted per run.

| Set | Questions | Gold articles | Content |
|---|---|---|---|
| S1 (set 3) | 50 | 80 | General: sexual offences, general part, criminal procedure |
| S2 (set 9) | 56 | 56 | Single-law: kidnapping and extortion general laws, penal codes |
| S3 (set 11) | 57 | 118 | Comparative: Mexico City vs Querétaro (two jurisdictions per question) |
| Others | — | — | Family law (set 8, paused), sets 6 and 10 |

Gold articles are parsed automatically from the *must* criteria (law name + article number) and resolved to chunk ids,
which gives a **judge-free retrieval metric** (is the gold article in the top-k?).

---

## 5. Results (measured)

### 5.1 Retrieval-only ablation (2026-10-08), Recall@10 (Recall@20) and MRR@50

| Configuration | S1 general | S2 single-law | S3 comparative | Pooled R@10 (254 gold) | s/query |
|---|---|---|---|---|---|
| BM25 | .55 (.73) | .95 (.95) | .54 (.64) | .63 | 0.1 |
| Dense | .70 (.81) | .96 (.98) | .72 (.86) | .77 | 0.3 |
| Hybrid (RRF) | .79 (.90) | .96 (.98) | .77 (.90) | .82 | 0.4 |
| Hybrid + HyDE | .83 (.90) | .96 (.98) | .81 (.91) | .85 | 1.1 |
| Hybrid + Decomposition | .81 (.90) | .98 (1.00) | .81 (.98) | .85 | 1.1–1.7 |
| Hybrid + Code routing | .78 (.91) | .96 (.98) | .82 (.95) | .84 | 0.7–1.1 |
| Hybrid + HyDE + Decomposition | .86 (.93) | .96 (.98) | .86 (.95) | .88 | 2.3–4.0 |
| Hybrid + HyDE + Code routing | .85 (.95) | .96 (.98) | .86 (.96) | .88 | 1.4–1.8 |

MRR@50 best: Hybrid+HyDE+Routing on S1 (.52) and S3 (.50); Hybrid+Decomp on S2 (.87).

### 5.2 End-to-end (LLM-judged)

| Set | Config | Fully correct | Mean score | Gold article in context |
|---|---|---|---|---|
| S3 | Hybrid+HyDE+Decomp (run 31) | 43/57 (75%) | .886 | 110/118 |
| S3 | same config, repeated (run 34) | 40/57 | — | — |
| S3 | Hybrid+HyDE+Routing (run 35) | 43/57 (75%) | .879 | 112/118 (8.9 vs 11.1 s/question) |
| S1 | Hybrid+HyDE+Decomp (run 23) | 37/50 (74%) | .894 | 72/80 |
| S2 | Dense+HyDE (run 25) | 51/56 (91%) | .944 | — |

Run-to-run noise: about ±3 questions out of 57 for an identical config.

### 5.3 Other measured effects
- **Law name in every chunk**: for codes whose name only appeared in (removed) page headers, median dense rank of gold
  articles went from 21 to 4.
- Chunker fix for "acoso sexual" (CDMX art. 179): hybrid rank from outside top-10 to 2 (the chunk previously did not
  contain the word "acoso" because the heading was lost).
- Re-chunking the other penal codes with the new chunker did **not** improve retrieval (hybrid 65→64 of 80), so we left them.
- Some articles remain hard for BM25 (e.g. CPF art. 266 "violación equiparada", BM25 rank 88), needing stemming or HyDE.
- Judge notes per set: measured on one run, minimal effect.
- Earlier tutorial-scale experiments (other domain, plant biology papers): removing bibliographies cut chunks 653→392
  and "reference noise" in answers from 15% to 0%; data cleaning beat model swapping.

---

## 6. Evaluation failures we found (candidate FAccT material)

1. **Double negation in rubrics flipped the judge.** Error criteria written as "Do not omit article X" were read by the
   judge in the wrong direction. Pass rate on S3 was **7–12%; after rewriting criteria positively ("Omits article X"),
   75%** with the same answers' quality. We renamed must_not → "error", and the server now **rejects new negatively
   phrased error criteria** (old ones grandfathered).
2. **Gold mislabeling via historical names.** Criteria said "Distrito Federal"; our gold parser did not map it to
   Mexico City, so gold articles were assigned to the wrong code (e.g. a Querétaro "148 Bis" vs a CDMX article),
   making correct retrieval look like failure.
3. **Corpus changes silently change benchmark results.** The expert deleted two Morelos family codes on purpose while
   cleaning; a family-law run collapsed (6/38 retrieved) — not a model bug. Benchmarks need corpus versioning.
4. **OCR and chunking errors become "model errors".** Glued articles, lost headings, "737 A" collapsed onto "737".
5. **Noise > effect size.** Several configuration differences in end-to-end runs are within ±3/57 judge+generation
   noise; the judge-free retrieval metric is more stable.
6. **Same model as generator and judge** (self-preference risk; not yet measured).

---

## 7. Accountability / design choices worth discussing

- Open-weight model on our own hardware: no user questions sent to a commercial API (data sovereignty, cost, but lower capability).
- Citations to exact articles; retrieval stages visible in the UI.
- Expert sign-off on each ingested document; staleness when the document changes.
- Forms: separation of concerns (LLM gathers facts; reviewed template drafts); draft/reviewed/published workflow;
  warnings about mandatory legal defence and referral to public defenders/helplines; triage toward the right procedure.
- Personal data only in the user's browser; server logs contain no personal data.
- Benchmark tooling enforces rubric hygiene (no negated error criteria), snapshots judge instructions per run, and
  warns when compared runs used different judge notes.

---

## 8. Limitations (honest)

- One expert wrote all questions and gold labels; no inter-annotator agreement yet.
- **All questions are expert-phrased** — no lay-user queries yet. The system is meant for the public.
- Generator = judge; no human grading yet.
- One embedding model; one LLM; mostly two jurisdictions in the comparative set (CDMX, Querétaro).
- Code routing depends on a hand-curated list of code names/aliases.
- The forms assistant has not been evaluated with users; first form not yet legally reviewed.
- Gold articles are derived from criteria text automatically.

---

## 9. Planned user study (NOT done yet)

Participants: the expert (scenarios, adjudication), **10–20 law students** (second graders + intermediate user group),
**20–30 lay users** (no legal training).

- The expert writes 8–10 **fictional scenarios** (some involve two jurisdictions or common misconceptions) with
  comprehension questions and correct answers. No real cases (ethics, safety).
- Each participant consults the assistant **in their own words** for 2–3 scenarios, then answers comprehension
  questions, rates confidence (1–5) and says whether they would act on the answer. Then completes the divorce form with
  a fictional persona card. SUS questionnaire.
- Measures:
  - retrieval recall for lay vs expert phrasing on the same topics;
  - answer correctness graded blind by two students, adjudicated by the expert; Cohen's κ; agreement with the LLM judge, split by lay vs expert phrasing;
  - **harm labels** for wrong answers (harmless / misleading / dangerous) and the share caused by wrong-jurisdiction citations;
  - **over-reliance**: confidence vs correctness; whether users notice wrong-state citations (lay vs students);
  - forms: completion rate, turns, time, errors in the filing as judged by the expert.
- Ethics: informed consent, pseudonymous codes, voluntary for students (not tied to grades; recruited by someone other
  than their teacher), small compensation for lay users, ethics committee approval or exemption to be checked.
- Timeline: build study pages Oct 9–13, pilot Oct 14–15, sessions Oct 16–22, analysis Oct 21–27, writing to Nov 3.
  Fallback: pilot + student grading for the first submission; full lay study in the revision round (Jan 28, 2027).

### Draft target abstract (brackets = hypothesis, not data)
Title: "Confident and Wrong in the Wrong State: A Multi-Stakeholder Audit of Retrieval-Augmented Legal Assistance in Mexico".
Claims to test: expert benchmarks overstate quality for the public (lay recall [0.6x] vs expert 0.88); jurisdiction
errors are [x%] of harmful answers; LLM judge agreement with humans [κ] and more lenient on lay questions; lay users
equally confident in wrong answers and rarely notice wrong-state citations; template-based forms produce court-ready
filings for [x/y] participants.

FAccT focus areas: Evaluations and evaluation practices (primary), System development and deployment, Law and policy.
FAccT says work without deep engagement with social components is out of scope, so a pure retrieval ablation is not enough.

---

## 10. Smaller details that might spark ideas

- Code routing is cheap (no LLM call) and matches LLM decomposition on comparative questions at ~2× lower latency; on top
  of decomposition it adds nothing. Possible angle: transparent, auditable rules vs opaque LLM steps.
- BM25 is near-perfect when the question names the law and article (S2) and weak otherwise — a proxy for expert vs lay phrasing.
- Comparative questions lose the second jurisdiction: articles about the same offence in another state, or neighbouring
  articles of the same code, crowd it out.
- Concurrency: a single local GPU with 4 slots serves everything; a slow form turn blocked other users until fixed.
  Cost/latency matter for public-interest deployments.
- One scanned 2008 forms manual was hand-corrected after OCR (reconstructed text marked in [brackets], lost text as
  [illegible]) — provenance of corrected legal text is itself an accountability question.
- The expert is actively curating the corpus (deleting/re-uploading codes); the system has per-document diagnostics
  and sign-offs, but no formal corpus versioning tied to benchmark runs yet.
- The app is used by a small team now; opening the forms assistant to the public without login is an open decision.
- Ideas not yet done: streaming answers, .docx export, Spanish stemming for BM25, reranker, more embedding models,
  more jurisdictions, an "uncertain jurisdiction" warning when the question does not say which state.

## 11. Questions we would like help with

1. Strongest framing for FAccT given what we have (evaluation-practice paper vs system/accountability paper vs both).
2. Which user-study measures give the most convincing evidence in ~2 weeks of sessions.
3. How to define and validate a harm scale for legal answers.
4. Related work: legal RAG evaluation (e.g. hallucination audits of commercial legal AI tools), LLM-as-judge
   reliability, access-to-justice technology, over-reliance on AI advice, Global South / non-English legal NLP.
5. Threats to validity reviewers will raise and how to pre-empt them.
