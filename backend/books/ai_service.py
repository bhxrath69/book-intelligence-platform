import requests
import logging

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


def call_ollama(prompt: str, max_tokens: int = 500) -> str:
    try:
        response = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens}
        }, timeout=120)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as exc:
        logger.warning("Ollama error: %s", exc)
        return ""


def generate_summary(title: str, description: str) -> str:
    prompt = (
        f"Write a 2-sentence summary of the book '{title}'. "
        f"Description: {description}. Be concise and informative."
    )
    result = call_ollama(prompt, max_tokens=200)
    return result or "No summary available."


def classify_genre(title: str, description: str) -> str:
    prompt = (
        "Classify this book into exactly one genre. Reply with only the genre name, "
        "nothing else. Choose from: Fiction, Mystery, Romance, Science Fiction, Fantasy, "
        "Thriller, Biography, Self-Help, History, Children, Horror, Poetry, Business, "
        f"Philosophy, Other. Book: '{title}'. Description: {description}"
    )
    result = call_ollama(prompt, max_tokens=10)
    return result or "Fiction"


def analyze_sentiment(text: str) -> str:
    if not text:
        return "Neutral"
    prompt = (
        "Analyze the sentiment of this book description. Reply with exactly one word: "
        f"Positive, Negative, or Neutral. Text: {text}"
    )
    result = call_ollama(prompt, max_tokens=5)
    return result or "Neutral"


def get_anthropic_client():
    return None