import os


def get_anthropic_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        from anthropic import Anthropic
    except ImportError:
        return None

    return Anthropic(api_key=api_key)


def generate_summary(title: str, description: str) -> str:
    client = get_anthropic_client()
    if client is None:
        return "No summary available."

    try:
        prompt = (
            f"You are a literary assistant. Write a 2-sentence summary of the book '{title}'. "
            f"Description: {description}. Be concise and informative."
        )
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return "No summary available."


def classify_genre(title: str, description: str) -> str:
    client = get_anthropic_client()
    if client is None:
        return "Fiction"

    try:
        prompt = (
            "Classify this book into exactly one genre. Reply with only the genre name, nothing else. "
            "Choose from: Fiction, Mystery, Romance, Science Fiction, Fantasy, Thriller, Biography, "
            f"Self-Help, History, Children, Horror, Poetry, Business, Philosophy, Other. Book: '{title}'. "
            f"Description: {description}"
        )
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return "Fiction"


def analyze_sentiment(text: str) -> str:
    if not text:
        return "Neutral"

    client = get_anthropic_client()
    if client is None:
        return "Neutral"

    try:
        prompt = (
            "Analyze the sentiment of this book description. Reply with exactly one word: "
            f"Positive, Negative, or Neutral. Text: {text}"
        )
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return "Neutral"
