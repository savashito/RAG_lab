"""
06_evaluation/eval_set.py — a hand-labelled evaluation set over the RAM papers.

Each item is (question, gold_source) where gold_source is the paper (filename
stem) that actually answers it. Paper-level relevance is easy to label reliably
(one paper is clearly the right source) and gives us REAL metrics — recall@k,
MRR — instead of the proxy signals we used in the ad-hoc ram_experiment.

Labels were written by reading each paper's abstract; every question targets a
feature distinctive to one paper (species, treatment, mechanism).
"""

# gold_source = the .md stem in ingestion/out/Root Apical Meristem/
EVAL: list[tuple[str, str]] = [
    ("Which hormones cross-talk to regulate the root apical meristem?",
     "10.1007@s11103-008-9393-6"),
    ("How does abscisic acid interact with auxin and cytokinin at the root meristem?",
     "10.1007@s11103-008-9393-6"),
    ("How does CLAVATA3/CLE peptide signaling regulate the shoot and root meristem?",
     "miwa2008"),
    ("What allelopathic effect do volatile monoterpenoids from Salvia leucophylla have on the root meristem?",
     "nishida2005"),
    ("Which monoterpenoid compounds inhibit DNA synthesis and cell proliferation in Brassica seedlings?",
     "nishida2005"),
    ("How does methyl jasmonate change terpene chemistry in Douglas-fir roots?",
     "huber2005"),
    ("How does methyl jasmonate affect sesquiterpenoid and diterpenoid concentrations in conifer roots?",
     "huber2005"),
    ("What tissue-specific DNA and histone modifications occur in the barley root apical meristem?",
     "braszewska-zalewska2013"),
    ("How does H4K5 histone acetylation vary between tissues of the root meristem?",
     "braszewska-zalewska2013"),
    ("How does redox and reactive oxygen species regulate root apical meristem organization?",
     "detullio2010"),
    ("How do reactive oxygen species connect root development to environmental conditions?",
     "detullio2010"),
    ("What is the role of the quiescent center in root apical meristem development?",
     "jiang2005"),
    ("How do cytokinin and auxin treatments affect terpenoid biosynthesis in Artemisia alba?",
     "danova2017"),
    ("How is the balance between cell division and differentiation controlled in the Arabidopsis root meristem?",
     "perilli2012"),
    ("How is epigenetic regulation involved in shoot apical meristem stem cells and transposon control?",
     "nguyen2022"),
]
