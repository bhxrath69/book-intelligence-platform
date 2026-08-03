import logging
from typing import Any, Dict, List, Tuple

from django.db import transaction

from books.ai_service import call_ollama
from books.models import Book, BookChunk



logger = logging.getLogger(__name__)

def get_cache_key(question: str, book_id: int, version: str = "v2") -> str:
    import hashlib
    return hashlib.sha256(f"{version}:{book_id}:{question}".encode()).hexdigest()


def get_cached_answer(question: str, book_id: int):
    from django.core.cache import cache
    key = get_cache_key(question, book_id)
    return cache.get(key), key


def set_cached_answer(key: str, response: dict, ttl: int = 86400):
    from django.core.cache import cache
    cache.set(key, response, ttl)



try:
    import chromadb
    from chromadb import PersistentClient
except Exception:
    chromadb = None
    PersistentClient = None


chroma_client = None
collection = None
_embedder = None


def get_collection():
    global chroma_client, collection
    if chromadb is None or PersistentClient is None:
        return None
    if collection is not None:
        return collection
    try:
        chroma_client = PersistentClient(path="./chroma_db")
        collection = chroma_client.get_or_create_collection("books_collection")
        return collection
    except Exception as exc:
        logger.warning("Chroma initialization failed: %s", exc)
        return None


def get_embedder():
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception as exc:
            logger.warning("SentenceTransformer failed: %s - RAG disabled", exc)
            _embedder = None
    return _embedder


def chunk_text(text: str, chunk_size: int = 200, overlap: int = 80) -> List[str]:
    words = text.split()
    if len(words) < 10:
        return []
    chunks = []
    step = chunk_size - overlap
    for i in range(0, len(words) - chunk_size + 1, step):
        chunk = ' '.join(words[i:i + chunk_size])
        if len(chunk.split()) >= 10:
            chunks.append(chunk)
    return chunks


def strip_gutenberg(text: str) -> str:
    if "*** START OF" in text:
        text = text.split("*** START OF")[1]
        if "***" in text:
            text = text.split("***", 1)[1]
    if "*** END OF" in text:
        text = text.split("*** END OF")[0]
    return text.strip()

def mmr(query_embedding: List[float], chunk_embeddings: List[List[float]], 
        chunks: List[str], top_k: int = 5, lambda_: float = 0.5) -> List[str]:
    """
    Maximal Marginal Relevance — balances relevance vs diversity.
    Prevents returning near-duplicate chunks to Claude.
    """
    import numpy as np

    if not chunk_embeddings or not chunks:
        return chunks[:top_k]

    def cosine_sim(a, b):
        a, b = np.array(a), np.array(b)
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    selected = []
    candidates = list(range(len(chunks)))

    for _ in range(min(top_k, len(chunks))):
        mmr_scores = {}
        for idx in candidates:
            relevance = cosine_sim(query_embedding, chunk_embeddings[idx])
            if selected:
                redundancy = max(
                    cosine_sim(chunk_embeddings[idx], chunk_embeddings[s])
                    for s in selected
                )
            else:
                redundancy = 0.0
            mmr_scores[idx] = lambda_ * relevance - (1 - lambda_) * redundancy

        best = max(mmr_scores, key=mmr_scores.get)
        selected.append(best)
        candidates.remove(best)

    return [chunks[i] for i in selected]



def index_book(book: Book) -> bool:
    try:
        active_collection = get_collection()
        embedder = get_embedder()
        if active_collection is None or embedder is None:
            return False

        full_text = (book.full_text or '').strip()
        if len(full_text) < 50:
            full_text = f"{book.title} {book.description}".strip()
        if len(full_text) < 50:
            return False

        full_text = strip_gutenberg(full_text)

        chunks = chunk_text(full_text)
        if not chunks:
            return False

        ids = []
        embeddings = []
        metadatas = []
        documents = []

        with transaction.atomic():
            BookChunk.objects.filter(book=book).delete()
            for i, chunk in enumerate(chunks):
                chroma_id = f"book_{book.id}_chunk_{i}"
                embedding = embedder.encode(chunk).tolist()
                ids.append(chroma_id)
                embeddings.append(embedding)
                metadatas.append({
                    "book_id": book.id,
                    "title": book.title,
                    "author": book.author
                })
                documents.append(chunk)
                BookChunk.objects.create(
                    book=book,
                    chunk_text=chunk,
                    chunk_index=i,
                    chroma_id=chroma_id,
                )
            active_collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents,
            )
        return True
    except Exception as exc:
        logger.warning("Index error: %s", exc)
        return False


def delete_book_from_index(book_id: int) -> None:
    try:
        active_collection = get_collection()
        if active_collection is None:
            return
        results = active_collection.get(
            where={"book_id": book_id},
            include=["metadatas"],
        )
        if results['ids']:
            active_collection.delete(ids=results['ids'])
        BookChunk.objects.filter(book_id=book_id).delete()
    except Exception:
        pass


def rag_query(question: str) -> Dict[str, Any]:
    try:
        active_collection = get_collection()
        embedder = get_embedder()
        if active_collection is None or embedder is None:
            return {"answer": "Embeddings unavailable", "sources": []}

        question_embedding = embedder.encode(question).tolist()
        results = active_collection.query(
            query_embeddings=[question_embedding],
            n_results=5,
            include=["documents", "metadatas"],
        )

        if not results['documents'][0]:
            return {"answer": "No relevant books found.", "sources": []}

        context = "\n\n".join(results['documents'][0])
        sources = list(set([m['title'] for m in results['metadatas'][0]]))

        prompt = f"""You are a helpful book assistant. Using only the following book information as context, answer the user's question. If the answer cannot be found in the context, say so.

Context:
{context}

Question: {question}

Provide a clear helpful answer with specific book references."""

        answer = call_ollama(prompt, max_tokens=500)
        if not answer:
            answer = "Sorry, unable to answer at this time."

        return {
            "answer": answer,
            "sources": sources,
        }
    except Exception as exc:
        logger.warning("RAG error: %s", exc)
        return {"answer": "Sorry, unable to answer at this time.", "sources": []}


def rag_query_with_history(question: str, book_id: int, session_id: int = None) -> Dict[str, Any]:
    from books.models import ChatSession, Message, Book

    try:
        book = Book.objects.get(pk=book_id)
    except Book.DoesNotExist:
        return {"answer": "Book not found.", "sources": [], "session_id": None}

    # Get or create session
    if session_id:
        try:
            session = ChatSession.objects.get(pk=session_id, book=book)
        except ChatSession.DoesNotExist:
            session = ChatSession.objects.create(book=book)
    else:
        session = ChatSession.objects.create(book=book)

    # Save user message
    Message.objects.create(session=session, role='user', content=question)

    # Build conversation history — convert queryset to list first
    all_messages = list(session.messages.order_by('timestamp'))
    history = [
        {"role": m.role, "content": m.content}
        for m in all_messages[:-1]
    ]

    # Retrieve relevant chunks from ChromaDB filtered by book
    context = ""
    sources = []
    try:
        active_collection = get_collection()
        embedder = get_embedder()
        if active_collection is not None and embedder is not None:
            question_embedding = embedder.encode(question).tolist()
            results = active_collection.query(
                query_embeddings=[question_embedding],
                n_results=5,
                where={"book_id": book_id},
                include=["documents", "metadatas"],
            )
            if results['documents'][0]:
                context = "\n\n".join(results['documents'][0])
                sources = list(set([m['title'] for m in results['metadatas'][0]]))
    except Exception as exc:
        logger.warning("Retrieval error: %s", exc)

    # Build history string for prompt
    history_text = ""
    if history:
        history_text = "\n".join([
            f"{m['role'].capitalize()}: {m['content']}"
            for m in history
        ])
        history_text = f"\nPrevious conversation:\n{history_text}\n"

    prompt = f"""You are a helpful assistant for the book '{book.title}' by {book.author}.
Answer questions using only the provided context from this book.
If the answer is not in the context, say so clearly.
{history_text}
Context from the book:
{context}

Current question: {question}

Answer:"""

    answer = call_ollama(prompt, max_tokens=500)
    if not answer:
        answer = "Sorry, unable to answer at this time."

    # Save assistant response
    Message.objects.create(session=session, role='assistant', content=answer)

    return {
        "answer": answer,
        "sources": sources,
        "session_id": session.id,
    }
def generate_hypothetical_document(question: str, book_title: str, book_author: str = "", attempts: int = 3) -> str:
    """
    HyDE (Hypothetical Document Embeddings): generate a short hypothetical passage
    that would answer the question, written in the narrator's voice and in the
    book's exact style. This bridges the lexical/semantic gap between question and
    answer chunks (e.g. "Who is the narrator?" -> "Call me Ishmael.").
    Retries up to `attempts` times because llama3.2 may occasionally refuse or
    truncate. Falls back to the raw question if all attempts fail.

    Returns: the hypothetical passage (str) if generated, or the original
    question (str) as fallback. Callers should compare the return value to the
    original question to determine whether HyDE was actually used.
    """
    author_part = f" by {book_author}" if book_author else ""
    hyde_prompt = (
        f"Imitate the exact text of the book '{book_title}'{author_part}. "
        f"Write 2-4 sentences in the first person, as if you are the narrator of "
        f"the book introducing yourself at the very start of the book, in a way that "
        f"answers this question: {question}\n\n"
        f"Use the narrator's exact name and the exact style of the book's opening "
        f"chapter, so the passage matches the real text word-for-word. This will be "
        f"used to locate the corresponding passage in the full text. Do not include "
        f"any preamble or explanation; output only the passage.\n\n"
        f"Passage:"
    )
    best = ""
    for i in range(attempts):
        try:
            passage = call_ollama(hyde_prompt, max_tokens=150,
                                  temperature=0.1, seed=42)
            if passage and len(passage.split()) >= 2:
                if len(passage) > len(best):
                    best = passage
                # A reasonably long passage is almost always a real (or near-verbatim)
                # excerpt; stop early on success.
                if len(best.split()) >= 20:
                    break
        except Exception as exc:
            logger.warning("HyDE attempt %d failed: %s", i + 1, exc)
    if best:
        logger.info("HyDE passage accepted (best=%d words)", len(best.split()))
        return best.strip()
    logger.warning("HyDE generation failed after %d attempts; falling back to raw question", attempts)
    return question


def hybrid_rag_query(question: str, book_id: int, session_id: int = None) -> Dict[str, Any]:
    from rank_bm25 import BM25Okapi
    from books.models import ChatSession, Message, Book

    try:
        book = Book.objects.get(pk=book_id)
    except Book.DoesNotExist:
        return {"answer": "Book not found.", "sources": [], "session_id": None}

    if session_id:
        try:
            session = ChatSession.objects.get(pk=session_id, book=book)
        except ChatSession.DoesNotExist:
            session = ChatSession.objects.create(book=book)
    else:
        session = ChatSession.objects.create(book=book)

    # Check cache first
    cached, cache_key = get_cached_answer(question, book_id)
    if cached:
        cached['session_id'] = session.id
        cached['cache_hit'] = True
        return cached

    Message.objects.create(session=session, role='user', content=question)

    all_messages = list(session.messages.order_by('timestamp'))
    history = [
        {"role": m.role, "content": m.content}
        for m in all_messages[:-1]
    ]

    db_chunks = list(BookChunk.objects.filter(book_id=book_id).order_by('chunk_index'))
    context = ""
    sources = []
    active_collection = get_collection()
    embedder = get_embedder()
    hyde_used = False

    if db_chunks:
        corpus = [c.chunk_text for c in db_chunks]

        tokenized = [c.split() for c in corpus]
        bm25 = BM25Okapi(tokenized)
        bm25_scores = bm25.get_scores(question.split())

        # HyDE: generate a hypothetical answer passage to bridge the
        # query->answer lexical/semantic gap (e.g. "Who is the narrator?" -> "Call me Ishmael.")
        hyde_passage = generate_hypothetical_document(question, book.title, book.author)
        hyde_used = (hyde_passage != question)
        hyde_embedding = None
        if hyde_used and embedder is not None:
            try:
                hyde_embedding = embedder.encode(hyde_passage).tolist()
            except Exception as exc:
                logger.warning("HyDE embedding failed: %s", exc)
        logger.info("HyDE passage for '%s': %s", question, hyde_passage[:200])
        logger.info("HyDE status: %s for question: %s",
                    "used" if hyde_used else "FALLBACK",
                    question[:50])

        # Pool size for BM25 + vector (question) + vector (HyDE) before RRF
        pool_size = 50
        k = 60  # RRF constant

        rrf_scores = {}

        bm25_ranked = bm25_scores.argsort()[::-1][:pool_size]
        for rank, idx in enumerate(bm25_ranked):
            rrf_scores[int(idx)] = rrf_scores.get(int(idx), 0) + 1 / (k + rank)

        def add_vector_rankings(query_text: str, tag: str) -> List[int]:
            """Query ChromaDB with the given text embedding and add RRF scores.
            Returns the list of chunk indices retrieved."""
            if active_collection is None or embedder is None:
                return []
            try:
                q_emb = embedder.encode(query_text).tolist()
                vec_results = active_collection.query(
                    query_embeddings=[q_emb],
                    n_results=min(pool_size, len(corpus)),
                    where={"book_id": book_id},
                    include=["documents", "metadatas", "embeddings"],
                )
                indices = []
                for chroma_id in vec_results['ids'][0]:
                    try:
                        idx = int(chroma_id.split('_chunk_')[1])
                        indices.append(idx)
                    except (IndexError, ValueError):
                        continue
                for rank, idx in enumerate(indices):
                    if idx < len(corpus):
                        rrf_scores[idx] = rrf_scores.get(idx, 0) + 1 / (k + rank)
                return indices
            except Exception as exc:
                logger.warning("Vector retrieval error (%s): %s", tag, exc)
                return []

        question_vec_indices = add_vector_rankings(question, "question")
        hyde_vec_indices = add_vector_rankings(hyde_passage, "hyde")

        # All vector indices (question + hyde) for later embedding fetch
        vec_indices = list(dict.fromkeys(question_vec_indices + hyde_vec_indices))

        top_indices = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:pool_size]
        candidate_chunks = [corpus[i] for i in top_indices if i < len(corpus)]

        if active_collection is not None and embedder is not None and candidate_chunks:
            # Fetch stored embeddings from ChromaDB instead of recomputing with embedder.encode()
            candidate_chroma_ids = [
                f"book_{book_id}_chunk_{i}" for i in top_indices if i < len(db_chunks)
            ]
            stored_data = active_collection.get(
                ids=candidate_chroma_ids,
                include=["embeddings", "documents"]
            )
            stored_embeddings_map = {}
            if stored_data and stored_data.get('ids'):
                for j, cid in enumerate(stored_data['ids']):
                    try:
                        stored_idx = int(cid.split('_chunk_')[1])
                        if stored_data.get('embeddings') and j < len(stored_data['embeddings']):
                            stored_embeddings_map[stored_idx] = stored_data['embeddings'][j]
                    except (IndexError, ValueError, TypeError):
                        continue

            # Build candidate embeddings using stored ChromaDB embeddings, fallback to encode()
            candidate_embeddings = []
            for i in top_indices:
                if i >= len(corpus):
                    continue
                if i in stored_embeddings_map:
                    candidate_embeddings.append(stored_embeddings_map[i])
                else:
                    candidate_embeddings.append(embedder.encode(corpus[i]).tolist())

            mmr_query_embedding = hyde_embedding if hyde_embedding is not None else embedder.encode(question).tolist()
            top_chunks = mmr(
                query_embedding=mmr_query_embedding,
                chunk_embeddings=candidate_embeddings,
                chunks=candidate_chunks,
                top_k=5,
                lambda_=0.5
            )
        else:
            top_chunks = candidate_chunks[:5]

        sources = list(set([
            db_chunks[i].book.title
            for i in top_indices[:5]
            if i < len(db_chunks)
        ]))
        context = "\n\n".join(top_chunks)

    history_text = ""
    if history:
        history_text = "\n".join([
            f"{m['role'].capitalize()}: {m['content']}"
            for m in history
        ])
        history_text = f"\nPrevious conversation:\n{history_text}\n"

    prompt = f"""You are a helpful assistant for the book '{book.title}' by {book.author}.

STRICT RULES:
- Only use information explicitly stated in the Context section below.
- Do NOT mention any other books, authors, or titles that are not '{book.title}' by {book.author}.
- Do NOT bring in outside knowledge, even if you know it.
- If the context does not contain the answer, respond exactly with: "I don't have enough information in this book's content to answer that."
{history_text}
Context from '{book.title}':
{context}

Current question: {question}

Answer (grounded only in the context above):"""

    answer = call_ollama(prompt, max_tokens=500)
    if not answer:
        answer = "Sorry, unable to answer at this time."

    Message.objects.create(session=session, role='assistant', content=answer)

    retrieval_tag = "hybrid_bm25_vector_hyde_rrf_mmr" if hyde_used else "hybrid_bm25_vector_rrf_mmr"

    # Store in cache
    set_cached_answer(cache_key, {
        "answer": answer,
        "sources": sources,
        "retrieval": retrieval_tag,
    })

    return {
        "answer": answer,
        "sources": sources,
        "session_id": session.id,
        "retrieval": retrieval_tag,
    }
