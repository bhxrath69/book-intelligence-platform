"""Recommendation agent.

Deterministic step: pull the book catalog via the Book model (plain Django ORM).
Then a single LLM call reasons over that list to produce recommendation text.

This agent works over metadata — it does NOT call hybrid_rag_query().
"""

from books.models import Book
from books.ai_service import call_ollama


def recommend(query: str) -> str:
    """Return a recommendation narrative for `query` based on book metadata."""
    # Deterministic step: gather the catalog (processed books with useful metadata).
    books = list(
        Book.objects.filter(is_processed=True)
        .order_by("-rating", "-num_reviews")
        .values("title", "author", "genre", "rating", "num_reviews", "description", "summary")
    )
    if not books:
        return "No books are available to recommend from yet."

    # Build a compact catalog representation for the LLM.
    lines = []
    for b in books[:20]:
        rating = f"{b['rating']:.1f}" if b["rating"] is not None else "N/A"
        lines.append(
            f"- {b['title']} by {b['author']} "
            f"(genre: {b['genre'] or 'unknown'}, rating: {rating}, "
            f"reviews: {b['num_reviews']}, summary: {b['summary'][:120]})"
        )
    catalog = "\n".join(lines)

    prompt = (
        "You are a book recommendation assistant. Based ONLY on the catalog of "
        "available books below, recommend the best book(s) for the user's request. "
        "Give a short, concrete recommendation with reasoning tied to the book's "
        "genre, rating, and summary. If none fit, say so clearly.\n\n"
        f"Available books:\n{catalog}\n\n"
        f"User request: {query}\n\n"
        "Recommendation:"
    )
    answer = call_ollama(prompt, max_tokens=400)
    return answer or "Sorry, unable to make a recommendation at this time."
