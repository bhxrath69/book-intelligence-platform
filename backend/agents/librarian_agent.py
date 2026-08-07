"""Librarian agent — the routing/orchestration layer.

plan_and_execute() classifies the user's query into an intent and routes it to
the appropriate agent or directly to the existing hybrid RAG pipeline. This
module is a router only; it adds no new retrieval logic.
"""

from typing import Optional

from .intent_agent import classify_intent
from .recommendation_agent import recommend
from .theme_agent import explain_theme, compare_books
from books.rag_service import hybrid_rag_query


def plan_and_execute(
    query: str,
    book_id: Optional[int] = None,
    session_id: Optional[str] = None,
) -> dict:
    """Classify `query` and route to the correct handler.

    Returns {"intent": <intent>, "answer": <text>, "book_id": book_id}.
    """
    intent = classify_intent(query)

    # These intents are answered directly by the existing hybrid RAG pipeline.
    if intent in ("answer_question", "find_quote", "summarize"):
        if book_id is None:
            return {
                "intent": intent,
                "answer": "This request needs a book_id. Please provide one.",
                "book_id": None,
            }
        result = hybrid_rag_query(question=query, book_id=book_id, session_id=session_id)
        return {
            "intent": intent,
            "answer": result.get("answer", ""),
            "book_id": book_id,
        }

    if intent == "recommend_books":
        answer = recommend(query)
        return {
            "intent": intent,
            "answer": answer,
            "book_id": book_id,
        }

    if intent == "explain_theme":
        if book_id is None:
            return {
                "intent": intent,
                "answer": "This request needs a book_id. Please provide one.",
                "book_id": None,
            }
        answer = explain_theme(query, book_id)
        return {
            "intent": intent,
            "answer": answer,
            "book_id": book_id,
        }

    if intent == "compare_books":
        # Use the single provided book_id; the view may pass a list separately.
        book_ids = query.get("book_ids") if isinstance(query, dict) else None
        if not book_ids and book_id is not None:
            book_ids = [book_id]
        answer = compare_books(query if isinstance(query, str) else "", book_ids)
        return {
            "intent": intent,
            "answer": answer,
            "book_id": book_id,
        }

    # Fallback — should not normally be reached (intent is validated upstream).
    return {
        "intent": intent,
        "answer": "Sorry, I could not handle that request.",
        "book_id": book_id,
    }
