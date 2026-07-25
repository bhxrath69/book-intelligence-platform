import logging
from typing import Any, Dict, List

from django.db import transaction

from books.ai_service import call_ollama
from books.models import Book, BookChunk



logger = logging.getLogger(__name__)

def get_cache_key(question: str, book_id: int) -> str:
    import hashlib
    return hashlib.sha256(f"{book_id}:{question}".encode()).hexdigest()


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


def chunk_text(text: str, chunk_size: int = 200, overlap: int = 40) -> List[str]:
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

    if db_chunks:
        corpus = [c.chunk_text for c in db_chunks]

        tokenized = [c.split() for c in corpus]
        bm25 = BM25Okapi(tokenized)
        bm25_scores = bm25.get_scores(question.split())

        vec_indices = []
        if active_collection is not None and embedder is not None:
            try:
                question_embedding = embedder.encode(question).tolist()
                vec_results = active_collection.query(
                    query_embeddings=[question_embedding],
                    n_results=min(10, len(corpus)),
                    where={"book_id": book_id},
                    include=["documents", "metadatas"],
                )
                for chroma_id in vec_results['ids'][0]:
                    try:
                        idx = int(chroma_id.split('_chunk_')[1])
                        vec_indices.append(idx)
                    except (IndexError, ValueError):
                        continue
            except Exception as exc:
                logger.warning("Vector retrieval error: %s", exc)

        k = 60
        rrf_scores = {}

        bm25_ranked = bm25_scores.argsort()[::-1][:10]
        for rank, idx in enumerate(bm25_ranked):
            rrf_scores[int(idx)] = rrf_scores.get(int(idx), 0) + 1 / (k + rank)

        for rank, idx in enumerate(vec_indices):
            if idx < len(corpus):
                rrf_scores[idx] = rrf_scores.get(idx, 0) + 1 / (k + rank)

        top_indices = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:10]
        candidate_chunks = [corpus[i] for i in top_indices if i < len(corpus)]

        if active_collection is not None and embedder is not None and candidate_chunks:
            candidate_embeddings = [
                embedder.encode(c).tolist() for c in candidate_chunks
            ]
            question_embedding_for_mmr = embedder.encode(question).tolist()
            top_chunks = mmr(
                query_embedding=question_embedding_for_mmr,
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

    Message.objects.create(session=session, role='assistant', content=answer)

    # Store in cache
    set_cached_answer(cache_key, {
        "answer": answer,
        "sources": sources,
        "retrieval": "hybrid_bm25_vector_rrf_mmr",
    })

    return {
        "answer": answer,
        "sources": sources,
        "session_id": session.id,
        "retrieval": "hybrid_bm25_vector_rrf_mmr",
    }