import logging
from typing import Any, Dict, List

from django.db import transaction

from books.ai_service import get_anthropic_client
from books.models import Book, BookChunk

logger = logging.getLogger(__name__)

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


def index_book(book: Book) -> bool:
    try:
        active_collection = get_collection()
        embedder = get_embedder()
        if active_collection is None or embedder is None:
            return False

        full_text = f"{book.title} {book.description}".strip()
        if len(full_text) < 20:
            return False

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
                metadatas.append({"book_id": book.id, "title": book.title, "author": book.author})
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

        client = get_anthropic_client()
        if client is None:
            return {"answer": "Answer generation unavailable", "sources": sources}

        prompt = f"""You are a helpful book assistant. Using only the following book information as context, answer the user's question. If the answer cannot be found in the context, say so.

Context:
{context}

Question: {question}

Provide a clear, helpful answer with specific book references."""

        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        return {
            "answer": response.content[0].text.strip(),
            "sources": sources,
        }
    except Exception as exc:
        logger.warning("RAG error: %s", exc)
        return {"answer": "Sorry, unable to answer at this time.", "sources": []}
