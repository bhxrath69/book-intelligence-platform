"""Intent classification agent.

Classifies a user query into exactly one of the supported librarian intents
using the existing Ollama llama3.2 integration (books.ai_service.call_ollama).
"""

from books.ai_service import call_ollama

# The exact set of intents the librarian router understands.
ALLOWED_INTENTS = {
    "answer_question",
    "recommend_books",
    "compare_books",
    "summarize",
    "explain_theme",
    "find_quote",
}

DEFAULT_INTENT = "answer_question"


def classify_intent(query: str) -> str:
    """Classify `query` into one of ALLOWED_INTENTS.

    Returns exactly one label from the allowed set. If the LLM returns anything
    that is not an exact match (or fails), defaults to `answer_question`.
    """
    prompt = (
        "Classify the user's book-related request into exactly one intent. "
        "Reply with ONLY the label, nothing else. No punctuation, no explanation.\n\n"
        "Allowed labels:\n"
        "- answer_question: ask about characters, plot, facts, or anything a "
        "specific book's content can answer\n"
        "- recommend_books: asking for suggestions of what to read, similar "
        "books, or best-or-must-read picks\n"
        "- compare_books: asking to compare two or more specific books\n"
        "- summarize: asking for a summary or overview of a book\n"
        "- explain_theme: asking about themes, motifs, symbols, or deeper "
        "meaning of a book\n"
        "- find_quote: asking for a specific quote, passage, or line from a book\n\n"
        f"User request: {query}\n\n"
        "Intent:"
    )
    raw = call_ollama(prompt, max_tokens=10)
    if not raw:
        return DEFAULT_INTENT

    # Normalize: strip punctuation/whitespace, take the first token.
    candidate = raw.strip().lower().split()[:1]
    if not candidate:
        return DEFAULT_INTENT
    label = candidate[0].rstrip(",.;:")
    if label in ALLOWED_INTENTS:
        return label
    return DEFAULT_INTENT
