import os
from anthropic import Anthropic
from typing import Optional

# Global client removed to prevent import crash
# Client created lazily inside functions

def generate_summary(title: str, description: str) -> str:
    try:
        prompt = f"You are a literary assistant. Write a 2-sentence summary of the book '{title}'. Description: {description}. Be concise and informative."
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except:
        return "No summary available."

def classify_genre(title: str, description: str) -> str:
    try:
        prompt = f"Classify this book into exactly one genre. Reply with only the genre name, nothing else. Choose from: Fiction, Mystery, Romance, Science Fiction, Fantasy, Thriller, Biography, Self-Help, History, Children, Horror, Poetry, Business, Philosophy, Other. Book: '{title}'. Description: {description}"
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except:
        return "Fiction"

def analyze_sentiment(text: str) -> str:
    if not text:
        return "Neutral"
    try:
        prompt = f"Analyze the sentiment of this book description. Reply with exactly one word: Positive, Negative, or Neutral. Text: {text}"
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except:
        return "Neutral"
