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
