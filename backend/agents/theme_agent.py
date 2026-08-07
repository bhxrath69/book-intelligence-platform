"""Theme agent.

- explain_theme(query, book_id) -> str: reuses hybrid_rag_query() for grounding,
  then one LLM call to synthesize the theme explanation.
- compare_books(query, book_ids) -> str: single LLM call; if the query clearly
  requires per-book grounding, calls hybrid_rag_query() once per book_id then
  synthesizes.
"""

from typing import List

from books.ai_service import call_ollama
from books.rag_service import hybrid_rag_query


def explain_theme(query: str, book_id: int) -> str:
    """Explain/analyze a theme grounded in the given book's content."""
    result = hybrid_rag_query(query, book_id)
    context = result.get("answer", "")
    sources = result.get("sources", [])

    prompt = (
        "You are a literary analysis assistant. Based on the grounded context "
        "retrieved from the book, explain the theme, motif, or deeper meaning "
        "the user asked about. Ground your answer entirely in the provided "
        "content and cite the work by its title.\n\n"
        f"Grounded content:\n{context}\n\n"
        f"Book sources: {', '.join(sources) if sources else 'unknown'}\n\n"
        f"User request: {query}\n\n"
        "Theme analysis:"
    )
    answer = call_ollama(prompt, max_tokens=500)
    return answer or "Sorry, unable to provide a theme analysis at this time."


def compare_books(query: str, book_ids: List[int]) -> str:
    """Compare two or more books. Uses per-book grounding when book_ids <= 4."""
    if not book_ids:
        return "Please provide at least one book to compare."

    # Per-book grounding for a small number of books.
    if len(book_ids) <= 4:
        grounded = []
        for bid in book_ids:
            result = hybrid_rag_query(query, bid)
            title = result.get("sources", ["unknown"])[0] if result.get("sources") else "unknown"
            grounded.append(f"Book '{title}': {result.get('answer', '')[:500]}")
        grounding_text = "\n\n".join(grounded)
    else:
        grounding_text = ""

    prompt = (
        "You are a book comparison assistant. Compare the books the user asked "
        "about on the dimensions they care about (plot, themes, style, characters). "
        "Be balanced and specific.\n\n"
    )
    if grounding_text:
        prompt += f"Per-book grounded content:\n{grounding_text}\n\n"
    prompt += f"User request: {query}\n\nComparison:"

    answer = call_ollama(prompt, max_tokens=500)
    return answer or "Sorry, unable to compare these books at this time."
