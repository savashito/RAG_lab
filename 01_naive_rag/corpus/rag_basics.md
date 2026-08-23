# A tiny knowledge base about RAG

Embeddings are lists of numbers that represent the meaning of a piece of text. Two texts with similar meaning are turned into vectors that point in nearly the same direction, so "closeness" in this vector space is a proxy for semantic similarity. Modern embedding models are neural networks trained so that paraphrases land near each other.

Chunking is the step where long documents are split into smaller passages before embedding. Chunk size matters a lot: chunks that are too large blur several ideas into one vector, while chunks that are too small lose the context needed to answer a question. Overlap between adjacent chunks helps avoid cutting an idea in half at a boundary.

Cosine distance measures how different the directions of two vectors are, ignoring their length. A cosine distance of zero means the two vectors point the same way, while a value near one means they are unrelated. In pgvector the cosine-distance operator is written as the special symbol between two vectors, and ordering rows by it gives you nearest-neighbour search.

Hybrid retrieval combines keyword search, such as BM25, with dense vector search. Keyword search excels at exact terms like product codes and rare names, while vector search excels at synonyms and paraphrases. Fusing the two ranked lists with Reciprocal Rank Fusion reliably beats either method used alone.

BM25 is a classic keyword ranking function. It scores a document by how often the query words appear in it, how rare those words are across the whole collection, and how long the document is. It has no notion of meaning, so it cannot match "car" to "automobile", but it is unbeatable when the exact token must match.

Reranking is a second pass that reorders an initial list of candidate passages using a more expensive but more accurate model, such as a cross-encoder. The retriever casts a wide net cheaply, and the reranker carefully picks the best few results from that net, adding several points of accuracy on hard queries.

pgvector is a Postgres extension that adds a vector column type and nearest-neighbour search directly inside the database. Because the vectors live next to the original text and its metadata, a single SQL query can filter by user or date and rank by similarity at the same time, which is awkward to do when vectors live in a separate store.

Energy efficiency is a real advantage of retrieval. Feeding a model only a few relevant chunks, instead of stuffing an entire corpus into a very long prompt, dramatically cuts the number of tokens processed. Since compute and energy scale with input length, retrieving the right small context is usually far cheaper than relying on a huge context window.
