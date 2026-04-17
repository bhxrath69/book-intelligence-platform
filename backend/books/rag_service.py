import os
import chromadb
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer
from books.models import Book, BookChunk
from django.db import transaction
from typing import List, Dict, Any
from books.ai_service import Anthropic

chroma_client = PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection("books_collection")
embedder = None
try:
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
except:
    print("SentenceTransformer init failed - RAG disabled")

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
                    chroma_id=chroma_id
                )
            
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )
        
        return True
    except Exception as e:
        print(f"Index error: {e}")
        return False

def delete_book_from_index(book_id: int) -> None:
    try:
        results = collection.get(
            where={"book_id": book_id},
            include=["metadatas"]
        )
        if results['ids']:
            collection.delete(
                ids=results['ids']
            )
        BookChunk.objects.filter(book_id=book_id).delete()
    except:
        pass

def rag_query(question: str) -> Dict[str, Any]:
    try:
        question_embedding = embedder.encode(question).tolist()
        results = collection.query(
            query_embeddings=[question_embedding],
            n_results=5,
            include=["documents", "metadatas"]
        )
        
        if not results['documents'][0]:
            return {"answer": "No relevant books found.", "sources": []}
        
        context = "\n\n".join(results['documents'][0])
        sources = list(set([m['title'] for m in results['metadatas'][0]]))
        
        prompt = f"""You are a helpful book assistant. Using only the following book information as context, answer the user's question. If the answer cannot be found in the context, say so.

Context:
{context}

Question: {question}

Provide a clear, helpful answer with specific book references."""
        
        claude = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = claude.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return {
            "answer": response.content[0].text.strip(),
            "sources": sources
        }
    except Exception as e:
        print(f"RAG error: {e}")
        return {"answer": "Sorry, unable to answer at this time.", "sources": []}
