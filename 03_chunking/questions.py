"""
03_chunking/questions.py — a small labelled evaluation set.

Each item is (question, gold) where `gold` is a distinctive phrase that appears
verbatim in exactly one place in the corpus. A chunking strategy 'wins' a
question if the retrieved top-k chunks contain that phrase. If a strategy's cut
lands in the middle of the gold phrase, no single chunk contains it — which is
exactly the failure we want to catch.

This is a tiny, hand-built stand-in for a real eval set. Lab 06 replaces it with
a proper evaluation harness (faithfulness, context recall, LLM-as-judge).
"""

QUESTIONS: list[tuple[str, str]] = [
    ("What pigment absorbs sunlight during photosynthesis?", "chlorophyll"),
    ("How do plants take in carbon dioxide?", "tiny pores called stomata"),
    ("What sugar does photosynthesis produce?", "glucose"),
    ("Where did the Eagle land on the Moon?", "Sea of Tranquility"),
    ("How many people walked on the Moon in total?", "twelve astronauts"),
    ("When did Apollo 11 launch?", "July 16, 1969"),
    ("Which coffee species has more caffeine?", "Robusta beans contain more caffeine"),
    ("How does caffeine reduce drowsiness?", "blocking adenosine receptors"),
    ("What are the two main coffee species?", "Arabica and Robusta"),
    ("What force moved water through Roman aqueducts?", "gravity"),
    ("How many aqueducts served the city of Rome?", "eleven aqueducts"),
    ("Why did Romans build stone arches?", "keep the water channel at the right height"),
    # These target the tricky-abbreviation doc. The naive splitter breaks after
    # "Dr." and "approx.", stranding the answer across a chunk boundary; a proper
    # segmenter (sentence-pysbd) keeps the sentence whole.
    ("What voltage does the pressure sensor operate at?", "3.5 volts"),
    ("Who approved the pressure sensor design?", "Dr. Ingrid Halvorsen"),
    ("How often should the sensor be calibrated?", "approx. every 6 months"),
]
