# Tlacua: project summary for funding searches

*November 2026. Written so that an assistant (for example, ChatGPT) can search for grants, compute credits, and
fellowships that fit this project. Items in [brackets] must be filled in by the team before applying.*

## One-paragraph description

Tlacua is an open-weight, self-hosted AI legal assistant for people in Mexico who need initial orientation on criminal
law but cannot reach a lawyer. It answers questions in plain Spanish and cites the Mexican laws it relies on, using
retrieval-augmented generation (RAG) over federal, national, and state legal codes. Our research audits it with its
intended users and repairs the failures we find. Our central finding is that a legal assistant can cite a real law,
quoted correctly, that does not apply to the person's case — for example, the penal code of the wrong Mexican state —
and that people without legal training do not notice. We study how to prevent these *applicability errors* and how
they affect user understanding, trust, and reliance.

## Problem

- Mexico has 32 state penal codes plus federal and national laws; which one applies depends on where the facts
  occurred and on who the people involved are (age, sex, relationship, public-servant status).
- Most people who need legal help cannot afford a lawyer and do not know which facts matter legally.
- AI legal assistants are usually evaluated by whether their citations exist or support a sentence, not by whether the
  cited law applies to the person. That gap harms exactly the users least able to detect it.

## Findings so far (two user-study rounds, October–November 2026)

- **Round 1 (43 participants):** 53% of the assistant's first answers (56 of 105) named the penal code of a Mexican
  state other than the one where the facts occurred; in 117 of 118 cases that code came from the retrieval step, not
  from the model inventing it.
- **Users did not detect it:** participants without legal training were as willing to act on these answers as on
  correct ones (63% vs 67%) and rarely reported a problem (9% vs 6%). Legally trained participants hesitated (would act
  in 23% vs 61%) but did not identify the cause.
- **Repair:** a retrieval-scoping step that identifies where the facts occurred cut these errors from 59.7% to 1.9% on
  the same 108 real conversations, and to 4.1% (8 of 196 first answers) in round 2 (81 participants).
- **Remaining failures are broader:** a lawyer on the team judged 24 of 180 round-2 answers legally incorrect, almost
  all for applying a law without verifying its factual conditions (age, relationship, whether money was demanded).
  Participants said they would act on 15 of those 24.
- **Trust without understanding:** a plain-language prompt raised users' trust (+0.76 on a 1–5 scale) and willingness
  to act (39% to 82%) without a comparable gain in understanding or citation accuracy — a trust-calibration risk.
- **Missing facts:** when users' first message named the state, the system retrieved the right article 61% of the
  time; when it did not, 16%.

A paper reporting these results has been submitted to ACM FAccT 2027 (under anonymous review).

## What we have built

- A self-hosted RAG assistant for Mexican criminal law (open-weight Gemma 4 model on a single NVIDIA RTX 5090 GPU;
  Qwen3 embedding and reranking models; PostgreSQL with pgvector). Corpus: federal and national law and the penal codes
  of Mexico City, the State of Mexico, Morelos, and Querétaro (51 sources, about 8,500 passages).
- A jurisdiction-scoping component that restricts retrieval to the law of the place where the facts occurred.
- A user-study platform (consent, random assignment, questionnaires, logging of every answer and retrieval).
- A guided assistant that helps people prepare legal filings from templates reviewed by a lawyer (first form: unilateral
  divorce in Mexico City).

## Planned work (next 12–18 months)

1. **Round 3 study:** a version of the assistant that first collects the legally decisive facts (place, ages,
   relationship, type of case) and only then gives guidance, compared with the current system in a randomized study.
   Outcomes: legal correctness judged blind by independent lawyers, user drop-out, retrieval accuracy, understanding,
   and whether trust tracks correctness.
2. **Independent validation:** blind review of answers and answer keys by lawyers outside the team; human validation of
   our automatic metrics.
3. **Person-based applicability:** tagging laws by whom they protect (for example, women, minors, older adults) so the
   assistant does not cite a law that does not apply to the person — and does not hide it from those it protects.
4. **Nationwide coverage:** extending the corpus from 4 to all 32 Mexican states and testing whether the error and the
   repair behave the same.
5. **Open release:** publishing the evaluation method, test sets, and code for other legal-aid and public-interest
   organizations.

## What funding would pay for

- Compute: GPU time for model serving, retrieval experiments, and replays of real conversations.
- Legal experts' time: answer keys, case catalogs, document templates, and blind review.
- Participant compensation (participants have so far been unpaid volunteers).
- Engineering: round-3 implementation, nationwide corpus ingestion, and maintenance.
- [Budget figures to be added by the team.]

## Team and organizations

- [Principal investigator name and role] — Boston College ([faculty / staff / student — affects eligibility]).
- [Mexican nonprofit name] — [registered as *donataria autorizada*? yes/no; U.S. equivalency determination? yes/no].
- A licensed Mexican lawyer on the team (answer keys, legal review).
- Collaborators at EAAMO (Equity and Access in Algorithms, Mechanisms, and Optimization) — [confirm EAAMO's U.S.
  nonprofit status and willingness to apply].

## Keywords for the search

access to justice; legal aid technology; AI for social good; responsible / trustworthy AI; AI auditing and evaluation;
human–AI interaction; algorithmic fairness; Latin America; Mexico; Spanish-language AI; open-weight / open-source
models; legal empowerment; public-interest technology; digital rights.

## What to search for

- Grants open to (a) a U.S. university (Boston College), (b) a Mexican nonprofit, or (c) a U.S. nonprofit research
  community (EAAMO).
- Cash grants, compute or cloud credits (GPU hours, API credits), and research fellowships.
- Funders already active in this space include, for example, the Patrick J. McGovern Foundation, the Tinker Foundation,
  Google.org, NVIDIA's Academic Grant Program, the NSF Law & Science program, and Mexico's SECIHTI. Find others,
  current deadlines, award sizes, and eligibility for each of the three applicant types.
