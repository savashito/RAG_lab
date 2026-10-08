# FAccT 2027 — abstract draft

Focus areas: **Evaluations and evaluation practices** (primary), System development and deployment, Law and policy.
Deadlines: abstract 2026-10-27, paper 2026-11-03 (AoE). Anonymized; max 14 pages + 1 endmatter page.

## Title (options)

1. Grounded or Just Plausible? Auditing Retrieval-Augmented Legal Assistance Across Mexico's Fragmented Criminal Jurisdictions
2. The Right Article from the Wrong State: Jurisdiction-Aware Evaluation of Legal RAG for Access to Justice in Mexico

## Abstract (~260 words)

Retrieval-augmented generation (RAG) is increasingly proposed as a way to widen access to legal information where legal aid is scarce. In Mexico, criminal law is split across a federal penal code, a national procedural code and 32 state penal codes, so a correct answer depends on retrieving the article of the right jurisdiction — an error that is invisible to a lay user, yet determines whether the information is valid. We build and audit an open-weight, locally hosted RAG assistant over 46 Mexican criminal-law sources (8,641 chunks) and evaluate it on 163 questions written by a criminal-law practitioner, including 57 comparative questions spanning two jurisdictions. We report three findings. First, retrieval quality is uneven in ways that matter: lexical search retrieves the gold article for 95% of questions that name the law, but for only 54–55% of those that do not, and comparative questions systematically lose the second jurisdiction. Hybrid retrieval, hypothetical-passage expansion and a lightweight, LLM-free code router raise pooled Recall@10 from 0.63 to 0.88. Second, the evaluation apparatus itself is fragile: negatively phrased rubric criteria inverted an LLM judge's verdicts and dropped the measured pass rate from 75% to 7–12%; historical place names ("Distrito Federal") silently mislabeled gold articles; and run-to-run variation exceeded several reported improvements. Third, we describe accountability mechanisms for a public-facing deployment: expert sign-off on every ingested document, citation-grounded answers, and a form-filling assistant in which the LLM only gathers facts while lawyer-reviewed templates produce the legal text and personal data never leave the user's browser. We argue for judge-free, jurisdiction-aware evaluation before such tools reach the public.

## Before submitting — numbers to verify / add

- [ ] "95% vs 54–55%" = BM25 Recall@10 on S2 vs S1/S3 (results.txt). Confirm S2 questions actually name the law.
- [ ] Generator/judge model name (gemma-4-26B-A4B per /props).
- [ ] Remove deployment URL, collaborator names and project names (anonymity policy).

---

## Target abstract (with the user study) — HYPOTHETICAL

Everything in [brackets] is a placeholder for a result we have NOT measured yet. Replace with real numbers
or rewrite the sentence if the result goes the other way. Do not submit with brackets.

**Title:** Confident and Wrong in the Wrong State: A Multi-Stakeholder Audit of Retrieval-Augmented Legal Assistance in Mexico

Retrieval-augmented generation (RAG) is promoted as a way to widen access to legal information where legal aid is scarce, yet such systems are almost always evaluated with questions written by legal experts. We audit an open-weight, locally hosted RAG assistant over Mexican criminal law — a federal penal code, a national procedural code and multiple state codes (46 sources, 8,641 chunks) — where a correct answer requires the article of the right jurisdiction. We combine a 163-question expert benchmark with a study of [N≈25] lay participants and [N≈15] law students, who consulted the assistant in their own words about [10] fictional scenarios; every answer was graded blind by two law students and adjudicated by a criminal-law practitioner. Three findings emerge. First, expert benchmarks overstate quality for the public: Recall@10 of the gold article falls from [0.88] for expert questions to [0.6x] for lay questions on the same topics, and jurisdiction errors — the right offence from the wrong state — account for [x%] of harmful answers. Second, the evaluation apparatus is itself fragile: an LLM judge agreed with human graders only moderately ([κ = 0.xx]) and was more lenient on lay-phrased questions, and negatively phrased rubric criteria inverted its verdicts, dropping the measured pass rate from 75% to 7–12%. Third, lay participants were [as confident] in incorrect answers as in correct ones and rarely noticed wrong-jurisdiction citations ([x%]), while students did so [y%] of the time. In a form-filling task, separating fact-gathering (LLM) from legal drafting (lawyer-reviewed templates), with personal data kept in the browser, produced [court-ready] filings for [x/y] participants. We argue that legal RAG should be evaluated with the people it is meant to serve, with jurisdiction-aware and harm-weighted metrics.
