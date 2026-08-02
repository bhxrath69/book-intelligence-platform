# Task Progress

## Step 1 — Verify huggingface-hub fix
- [x] huggingface_hub=0.36.2 (within <1.0 constraint)
- [x] SentenceTransformer('all-MiniLM-L6-v2') → Embedder OK

## Step 2 — Debug Streamlit chat
- [x] 2a: Ollama responsive (hi → "How can I assist you today?")
- [x] 2b: Django started fresh, port 8000 listening
- [x] 2c: Chat endpoint OK — book 199 "Who is Heathcliff?" → real answer, hybrid_bm25_vector_rrf_mmr
- [x] 2d: Streamlit running at localhost:8501, HTTP 200; all backing endpoints verified (books list 19, stats, history, chat)

## Step 3 — Expand to ~25 books via Gutendex
- [x] Added 8 books (IDs 199-207): Wuthering Heights, Anna Karenina, Dorian Gray, Heart of Darkness, The Odyssey, Little Women, Robinson Crusoe, Gulliver's Travels, Scarlet Letter
- [x] Final book list: 27 books total

## Step 4 — Spot-check 3 newly added books
- [x] Dorian Gray (201) — grounded, no hallucination
- [x] Heart of Darkness (202) — grounded, no hallucination
- [x] The Scarlet Letter (207) — grounded, no hallucination

## Step 5 — RAGAS evaluation with Ollama as judge
- [x] Built 16-question test set across 16 books
- [x] Custom eval script (ragas_evaluate.py) since ragas pkg has broken langchain_community dep
- [x] Ran all 4 metrics via llama3.2 judge + MiniLM embeddings
- [x] Saved ragas_results.json
- [x] Reported averages: context_precision=0.731, context_recall=0.469, faithfulness=0.056, answer_relevancy=0.433


- [x] 6a Diagnose: Dracula full_text is WRONG (Gutendex ID 144 = The Voyage Out by Virginia Woolf, not Dracula). 0 chunks contain Harker/Dracula/Transylvania
- [x] 6a Diagnose: Dorian Gray portrait chunks exist but rank below 5 in vector search (rank 8, dist 0.9958)
- [x] 6a Diagnose: Moby Dick "Call me Ishmael" exists in chunk 26-27; vector rank ~3 but MMR + top-5 narrows it out
- [ ] 6b Fix Dracula: re-download Dracula text (Gutenberg ID 345) & re-index
- [ ] 6b Fix Dorian Gray/Moby Dick: increase candidate pool n_results 10->15
- [ ] 6b Fix Moby Dick: increase chunk overlap 40->80 for context continuity
- [ ] 6b Re-index 3 fixed books
- [ ] 6c Re-test 3 questions via /chat/ endpoint
- [ ] 6d Re-run RAGAS subset & compare context_recall



