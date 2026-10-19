# Related work — Tlacua Legis (FAccT 2027)

Living document. Two uses: (1) source for the paper's *Background and Related Work* section; (2) a list of ideas
to improve Tlacua, each tied to evidence.

**How each entry is written:** citation (with link) → what the work shows → **Paper:** why it matters for our
argument → **Tlacua:** what it suggests we build or measure.

**Verification:** every citation below was checked online on 2026-10-19 (title, authors, venue, year). Entries marked
⚠️ still need a detail confirmed before they go into the paper. Summaries are from abstracts and search results,
not from a full read: **read the paper before citing a specific number or claim.**

The current paper draft (`research_paper/facct2027_paper_draft.docx`) cites only Dahl et al. 2024, Raji et al. 2020
and Suresh & Guttag 2021.

---

## Our claim, in one paragraph (to position everything below)

In a federal legal system (Mexico: 32 state penal codes plus national and federal law), a RAG legal assistant can
cite a **real** article, quote it correctly, and still mislead, because the article belongs to **another state**. In
our user study (round 1), lay participants rarely noticed. The cause sits in **retrieval**: other states' articles
were in the context in 65 of 67 cases. A system prompt telling the model "don't cite a state you weren't told; ask
first" made it ask, but it still cited state codes in 7 of 12 no-place questions (benchmark set 14). Changing what
the model **sees** (a jurisdiction gate before retrieval) is the intervention we evaluate.

---

## 1. Legal hallucination and the reliability of legal AI

- **Dahl, Magesh, Suzgun & Ho (2024). "Large Legal Fictions: Profiling Legal Hallucinations in Large Language
  Models." *Journal of Legal Analysis* 16(1): 64–93.** [doi:10.1093/jla/laae003](https://doi.org/10.1093/jla/laae003)
  (already cited in the draft) — General-purpose LLMs hallucinate legal facts often and don't reliably recognize their
  own errors.
  **Paper:** baseline for "LLMs make legal errors". Our failure mode differs: the citation is *real* but
  *inapplicable*.

- **Magesh, Surani, Dahl, Suzgun, Manning & Ho (2025). "Hallucination-Free? Assessing the Reliability of Leading AI
  Legal Research Tools." *Journal of Empirical Legal Studies*.** [Stanford page](https://law.stanford.edu/publications/hallucination-free-assessing-the-reliability-of-leading-ai-legal-research-tools) ·
  [arXiv 2405.20362](https://arxiv.org/abs/2405.20362) — First preregistered evaluation of commercial legal research
  tools that use RAG. RAG reduces but does not eliminate hallucinations; they count as an error a response that is
  *misgrounded* (cites a real source that doesn't support the claim).
  **Paper:** closest prior work. "RAG ≠ hallucination-free" is our premise. Our wrong-state citations are a specific
  kind of misgrounding that their taxonomy covers, studied here with **lay users** in a **multi-jurisdiction civil-law**
  system. ⚠️ Read their taxonomy to use their exact terms.
  **Tlacua:** our citation classes (con respaldo / sin fundamento / ley mal atribuida / inventado) map onto their
  categories. Align the names before publishing.

- **Guha et al. (2023). "LegalBench: A Collaboratively Built Benchmark for Measuring Legal Reasoning in Large Language
  Models." *NeurIPS 2023* (Datasets & Benchmarks).** [proceedings](https://proceedings.neurips.cc/paper_files/paper/2023/hash/89e44582fd28ddfea1ea4dcb0ebbf4b0-Abstract.html) —
  162 tasks written by legal professionals, six types of legal reasoning. US law, English.
  **Paper:** shows legal evaluation must be built with lawyers, as Karen does for our sets.
  **Tlacua:** their task types ("rule-recall", "rule-application"…) could label our benchmark questions, to report
  *which kind* of legal reasoning fails.

- **Pipitone & Houir Alami (2024). "LegalBench-RAG: A Benchmark for Retrieval-Augmented Generation in the Legal
  Domain." arXiv:2408.10343.** [arXiv](https://arxiv.org/abs/2408.10343) — Evaluates only the **retrieval** step:
  6,858 expert-annotated query→snippet pairs; rewards small, precise snippets.
  **Tlacua:** our 🔎 metric (did the needed article reach the context?) is the same idea. Their precision-at-snippet
  view supports smaller chunks for long articles.

- **Zheng, Guha, Arifov, Zhang, Skreta, Manning, Henderson & Ho (2025). "A Reasoning-Focused Legal Retrieval
  Benchmark." *CS&Law 2025*.** [arXiv 2505.03970](https://arxiv.org/abs/2505.03970) — Bar Exam QA and **Housing Statute
  QA**; in the second, retrieval is done over **a separate candidate pool for each jurisdiction**. Legal RAG "remains a
  challenging application".
  **Paper:** an established benchmark that already treats jurisdiction as a hard retrieval boundary: the same design
  choice as our gate.
  **Tlacua:** per-jurisdiction pools is exactly what the gate implements. Cite as precedent.

- **Louis, van Dijck & Spanakis (2024). "Interpretable Long-Form Legal Question Answering with Retrieval-Augmented
  Large Language Models." *AAAI 2024*.** [AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/30232) — LLeQA: 1,868
  expert-annotated **statutory** questions (French, Belgian law), answers grounded in specific provisions,
  retrieve-then-read.
  **Paper:** the closest setting outside English common law: statutes, a civil-law system, a non-English language.

## 2. Jurisdiction-specific legal reasoning

- **Yang, Tan, Chen, Xiao, Tong & Zhou (2026). "CrossLex: A Source-Grounded Benchmark for Cross-Jurisdictional Legal
  Reasoning in Large Language Models." arXiv:2608.01292 (preprint, Aug 2026).** [arXiv](https://arxiv.org/abs/2608.01292) —
  6,149 instances, the same fact patterns across China, California and Germany. Models often answer correctly but
  **fail to cite the right jurisdiction's sources**.
  **Paper:** very recent and directly on point: "right answer, wrong jurisdiction's citation". It compares
  *countries*; we study *states inside one federal country* and **lay users' reactions**. ⚠️ Preprint: check whether it
  has been accepted somewhere before the deadline.

- **Tucker & Doyle (2025). "If You Give an LLM a Legal Practice Guide." *CS&Law 2025*.**
  [ACM](https://dl.acm.org/doi/10.1145/3709025.3712220) — LLMs struggle with questions that need detailed,
  **jurisdiction-specific** rules, and the paper tests giving them practice-guide material. ⚠️ Read for their exact
  findings and method (found through a search result; confirm the abstract).
  **Paper:** supports "jurisdiction-specific rules are a known weak spot".

- **Gap we have not found filled yet (search more):** a study of **lay users** facing **intra-country,
  cross-state** legal answers. If none exists, that's part of our contribution. ⚠️ Do a systematic search (ACM DL,
  ACL Anthology, ICAIL, JURIX, NLLP, CS&Law) before claiming "first".

## 3. Why prompts don't fix it: models follow (irrelevant or conflicting) retrieved context

- **Shi, Chen, Misra, Scales, Dohan, Chi, Schärli & Zhou (2023). "Large Language Models Can Be Easily Distracted by
  Irrelevant Context." *ICML 2023*.** [arXiv 2302.00093](https://arxiv.org/abs/2302.00093) — Irrelevant information in
  the prompt degrades answers; an instruction to ignore it helps **only partly**.
  **Paper:** mechanism for our set-14 result: the instruction "don't cite other states" helped (the model asks), but
  the irrelevant state articles still leaked into 7/12 answers.

- **Cuconasu et al. (2024). "The Power of Noise: Redefining Retrieval for RAG Systems." *SIGIR 2024*.**
  [arXiv 2401.14887](https://arxiv.org/abs/2401.14887) — Retrieved documents that are *related but not relevant* hurt
  RAG answers more than random ones.
  **Paper:** another state's article about the same crime is exactly a "related but not relevant" document: the
  worst kind of distractor according to this work.
  **Tlacua:** supports removing other states' articles (the gate) rather than only ranking them lower.

- **Xie, Zhang, Chen, Lou & Su (2024). "Adaptive Chameleon or Stubborn Sloth: Revealing the Behavior of Large Language
  Models in Knowledge Conflicts." *ICLR 2024*.** [arXiv 2305.13300](https://arxiv.org/abs/2305.13300) — LLMs readily
  adopt external evidence that is coherent and convincing, even against their own knowledge.
  **Paper:** a well-formatted article from another state's code *is* coherent, convincing evidence, so the model uses it.

- **Xu, Qi, Guo, Wang, Wang, Zhang & Xu (2024). "Knowledge Conflicts for LLMs: A Survey." *EMNLP 2024*.**
  [arXiv 2403.08319](https://arxiv.org/abs/2403.08319) — Taxonomy: context–memory, **inter-context**, intra-memory
  conflicts.
  **Paper:** articles from two states in the same context is an *inter-context conflict*; use their vocabulary.

- **Liu, Lin, Hewitt, Paranjape, Bevilacqua, Petroni & Liang (2024). "Lost in the Middle: How Language Models Use Long
  Contexts." *TACL* 12: 157–173.** [doi:10.1162/tacl_a_00638](https://doi.org/10.1162/tacl_a_00638) — Models use
  information at the start and end of the context best.
  **Tlacua:** order the context so the relevant state's articles come first, and test whether that changes citations.

## 4. Query understanding and metadata filtering (the gate)

- **Self-querying retrieval (practitioner technique, not an academic paper).** An LLM turns the question into
  structured metadata filters, and vector search runs only over matching documents. Shipped in common RAG frameworks
  (e.g. LangChain's `SelfQueryRetriever`; [NVIDIA RAG blueprint docs](https://docs.nvidia.com/rag/latest/custom-metadata.html)).
  **Paper:** our gate is this pattern with a legal twist: if no place is found, it doesn't fall back to "search
  everything", it restricts to national law and asks.

- **Dadopoulos, Ladas, Moschidis & Negkakis (2025). "Metadata-Driven Retrieval-Augmented Generation for Financial
  Question Answering." arXiv:2510.24402.** [arXiv](https://arxiv.org/abs/2510.24402) — Metadata filtering plus query
  rewriting improves RAG over baselines in a regulated domain (finance).
  **Paper:** an academic data point that metadata filtering helps in a high-stakes domain. ⚠️ Preprint.

- **Gao, Ma, Lin & Callan (2023). "Precise Zero-Shot Dense Retrieval without Relevance Labels." *ACL 2023*.**
  [arXiv 2212.10496](https://arxiv.org/abs/2212.10496) — **HyDE**: the LLM writes a hypothetical answer and that is
  embedded for search. **We use it** in the study configuration.
  **Paper:** method citation. **Note for Tlacua:** a hypothetical answer may itself mention a state; the gate reads
  the person's original question, not the HyDE text, on purpose.

## 5. Ambiguity, clarifying questions, abstention

- **Aliannejadi, Zamani, Crestani & Croft (2019). "Asking Clarifying Questions in Open-Domain Information-Seeking
  Conversations." *SIGIR 2019*.** [arXiv 1907.06554](https://arxiv.org/abs/1907.06554) — Defines the task; dataset
  Qulac.
- **Aliannejadi et al. (2020). "ConvAI3: Generating Clarifying Questions for Open-Domain Dialogue Systems (ClariQ)."
  arXiv:2009.11352.** [arXiv](https://arxiv.org/abs/2009.11352) — Shared task: **when** to ask, and **what** to ask.
  **Paper:** "should the system ask for the state?" is a clarification-need decision; our set 14 has questions
  where asking is wrong (comparisons, national law) and where it's required (no place).
- **Min, Michael, Hajishirzi & Zettlemoyer (2020). "AmbigQA: Answering Ambiguous Open-domain Questions." *EMNLP
  2020*.** [ACL Anthology](https://aclanthology.org/2020.emnlp-main.466) — Over half of open-domain questions are
  ambiguous; the task is to find every plausible reading.
  **Paper:** "what's the penalty for robbery?" in Mexico has 32+ readings (one per state).
  **Tlacua:** the alternative to asking is the AmbigQA strategy: briefly list how it varies. Our user study suggests
  lay users then take one state's answer as theirs, so asking is safer. Worth stating as a design argument.
- **Zhang et al. (2024). "CLAMBER: A Benchmark of Identifying and Clarifying Ambiguous Information Needs in Large
  Language Models." *ACL 2024*.** [arXiv 2405.12063](https://arxiv.org/abs/2405.12063) — Current LLMs are poor at
  noticing ambiguity and asking good clarifying questions; chain-of-thought and few-shot prompting help only a little.
  **Paper:** matches our set 14: prompting alone gave limited gains, which motivates a system-level gate. ⚠️ Confirm
  the full author list.
- **Wen, Yao, Feng, Xu, Tsvetkov, Howe & Wang (2025). "Know Your Limits: A Survey of Abstention in Large Language
  Models." *TACL* 13.** [ACL Anthology](https://aclanthology.org/2025.tacl-1.26) — Framework for when LLMs should
  decline to answer (query, model and human-values perspectives).
  **Tlacua:** "the code of Puebla is not in our documents" is a partial abstention; use their framing for the
  out-of-corpus category.

## 6. Citations and attribution

- **Gao, Yen, Yu & Chen (2023). "Enabling Large Language Models to Generate Text with Citations." *EMNLP 2023*.**
  [ACL Anthology](https://aclanthology.org/2023.emnlp-main.398) — ALCE benchmark; citation **recall** (claims backed by
  a citation) and **precision** (citations that actually back the claim).
- **Liu, Zhang & Liang (2023). "Evaluating Verifiability in Generative Search Engines." *Findings of EMNLP 2023*.**
  [arXiv 2304.09848](https://arxiv.org/abs/2304.09848) — Human audit of commercial generative search engines: many
  sentences unsupported, many citations not supporting their sentence.
  **Paper:** our citation check (regex + database) is a cheaper, domain-specific version of their citation precision.
  **Tlacua:** report our numbers in their terms (citation precision), and add "applicable jurisdiction" as an extra
  condition a citation must meet to count as supporting.

## 7. LLM-as-judge (our benchmark's grader)

- **Zheng et al. (2023). "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." *NeurIPS 2023* (Datasets &
  Benchmarks).** [proceedings](https://proceedings.neurips.cc/paper_files/paper/2023/hash/91f18a1287b398d378ef22505bf41832-Abstract.html) —
  Strong LLM judges agree with humans >80 %, but have position, verbosity and **self-enhancement** biases.
- **Panickssery, Bowman & Feng (2024). "LLM Evaluators Recognize and Favor Their Own Generations." *NeurIPS 2024*.**
  [arXiv 2404.13076](https://arxiv.org/abs/2404.13076) — LLM judges can recognize and favor their own outputs.
  **Paper — limitation we must state:** our judge is **the same model** that writes the answers (Gemma, served as
  `Gemma-4-4B-8b`, 25B parameters). Mitigations to report: the judge only marks presence/absence of expert-written
  components (not overall quality); score computed in code; regex↔judge agreement (77–83 % on set 14) and human
  review (✍️) as checks.
  **Tlacua:** run a second judge from a different model family on a sample, and report agreement.

## 8. Lay users, legal advice and (over)reliance

- **Schneiders, Seabrooke, Krook, Hyde, Leesakul, Clos & Fischer (2025). "Objection Overruled! Lay People can
  Distinguish Large Language Models from Lawyers, but still Favour Advice from an LLM." *CHI 2025*.**
  [arXiv 2409.07871](https://arxiv.org/abs/2409.07871) — Lay people tend to prefer LLM-generated legal advice, even when
  they can tell it apart from lawyers' advice.
  **Paper:** strong motivation: lay users *prefer* LLM legal advice, so wrong-jurisdiction answers reach people who
  are inclined to trust them. Consistent with our participants rarely detecting problems.

- **Tan, Westermann & Benyekhlef (2023). "ChatGPT as an Artificial Lawyer?" *AI4AJ workshop @ ICAIL 2023* (CEUR-WS
  Vol. 3435).** [PDF](https://ceur-ws.org/Vol-3435/short2.pdf) — Legal information for laypeople evaluated as a
  **process** (understanding the person's situation and needs, not just accuracy); compares ChatGPT with JusticeBot.
  **Paper:** supports evaluating "did it understand where the person is?" as part of quality.

- **Kim, Liao, Vorvoreanu, Ballard & Wortman Vaughan (2024). "'I'm Not Sure, But...': Examining the Impact of Large
  Language Models' Uncertainty Expression on User Reliance and Trust." *FAccT 2024*.** ⚠️ Add the DOI. — How LLMs
  phrase uncertainty changes how much users rely on them.
  **Tlacua:** test a phrasing like «esto depende del estado; no sé dónde ocurrió» against a confident answer, as a
  round-2+ manipulation.

- **Buçinca, Malaya & Gajos (2021). "To Trust or to Think: Cognitive Forcing Functions Can Reduce Overreliance on AI
  in AI-assisted Decision-making." *PACM HCI (CSCW)*.** [arXiv 2102.09692](https://arxiv.org/abs/2102.09692) —
  Making people think before seeing the AI's answer reduces overreliance.
- **Vasconcelos, Jörke, Grunde-McLaughlin, Gerstenberg, Bernstein & Krishna (2023). "Explanations Can Reduce
  Overreliance on AI Systems During Decision-Making." *PACM HCI 7 (CSCW1), Art. 129*.**
  [doi:10.1145/3579605](https://doi.org/10.1145/3579605) — Explanations reduce overreliance when they're simpler than
  the task itself.
  **Paper (both):** our "participants rarely noticed problems" is an overreliance finding; these frame it.
  **Tlacua:** asking for the state first works a bit like a cognitive forcing function: the person has to think about
  where it happened. A hypothesis worth testing.

## 9. Auditing and sociotechnical harm (FAccT framing)

- **Raji et al. (2020). "Closing the AI Accountability Gap: Defining an End-to-End Framework for Internal Algorithmic
  Auditing." *FAT\* 2020*: 33–44.** [doi:10.1145/3351095.3372873](https://doi.org/10.1145/3351095.3372873) (already
  cited in the draft).
- **Suresh & Guttag (2021). "A Framework for Understanding Sources of Harm throughout the Machine Learning Life
  Cycle." *EAAMO 2021*.** [doi:10.1145/3465416.3483305](https://doi.org/10.1145/3465416.3483305) (already cited in
  the draft).
- **Raji, Kumar, Horowitz & Selbst (2022). "The Fallacy of AI Functionality." *FAccT 2022*.**
  [doi:10.1145/3531146.3533158](https://doi.org/10.1145/3531146.3533158) — Deployed AI often simply doesn't work, and
  functionality is a first-order policy and harm question.
  **Paper:** frames our finding as a *functionality* failure (the assistant doesn't do what it implies: tell you
  *your* law), not just a fairness one. Good fit for FAccT.

## 10. Spanish-language and Mexican legal NLP resources

- **Martinez-Seis, Pichardo-Lagunas, Koff, Equihua, Perez-Maqueo & Hernández-Huerta (2022). "Unified, Labeled, and
  Semi-Structured Database of Pre-Processed Mexican Laws." *Data* 7(7): 91.** [MDPI](https://www.mdpi.com/2306-5729/7/7/91) —
  Mexican laws converted from PDF into a semi-structured JSON corpus, labeled with NLP.
  **Paper:** related resource; shows Mexican legal NLP is under-resourced.
  **Tlacua:** check whether it covers **state** penal codes and could speed up adding states (we only have CDMX, Edomex,
  Morelos, Querétaro).
- **Legal-ES (2020), *LT4Gov workshop*.** [PDF](https://aclanthology.org/2020.lt4gov-1.6.pdf) — Large Spanish legal
  corpus (>2,000 M words) including Mexican sources. ⚠️ Add authors.
- **MEL: Legal Spanish language model (2025). arXiv:2501.16011.** [arXiv](https://arxiv.org/abs/2501.16011) — ⚠️ Add
  authors; check whether it includes Mexican law (probably Spain-focused).

---

## Ideas for Tlacua that come from this literature

| # | Idea | Evidence | Status |
|---|---|---|---|
| 1 | Jurisdiction gate: retrieve only the detected state's code + national law; ask when no place | Zheng et al. 2025 (per-jurisdiction pools); Cuconasu 2024; Shi 2023 | Built (2f92902); benchmark #52/#53 running |
| 2 | Distinguish **place of the facts** from other places mentioned (residence, workplace) | Karen's set 12, Carlos case; Celaya example | To do |
| 3 | Order context: relevant-state articles first | Liu et al. 2024 (Lost in the Middle) | Idea |
| 4 | Report citation precision in ALCE terms, with "right jurisdiction" as a condition | Gao et al. 2023; Liu, Zhang & Liang 2023 | Partly (citations.py) |
| 5 | Second judge from another model family on a sample; report agreement | Panickssery et al. 2024; Zheng et al. 2023 | To do |
| 6 | Uncertainty phrasing as a study manipulation | Kim et al. 2024 | Idea (round 3?) |
| 7 | "Ask first" as a cognitive forcing function: measure whether it improves detection of problems | Buçinca et al. 2021 | Idea |
| 8 | Two-turn benchmark: the system asks, the person answers the state, then the system must use only that state | ClariQ; CLAMBER | To do |
| 9 | Label benchmark questions by reasoning type (rule recall vs application) | Guha et al. 2023 (LegalBench) | Idea |
| 10 | Add more state codes from existing structured corpora | Martinez-Seis et al. 2022 | Check coverage |

## To search next

- Lay users and federal/multi-jurisdiction legal information (US state law, Mexico, Brazil, Germany Länder…).
- Access to justice and AI in Latin America / Mexico specifically.
- Legal design / plain-language legal information (for the prompt-style findings).
- Human-subject studies of RAG citations (do people check citations at all?).
- Venues to sweep: FAccT, CHI, CSCW, CS&Law, ICAIL, JURIX, NLLP workshop, AI4AJ workshop, *Artificial Intelligence and
  Law* journal.
