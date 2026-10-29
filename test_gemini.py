"""Quick check that GEMINI_API_KEY is loaded from .env and that the Gemini API responds."""
import os

from dotenv import load_dotenv
from google import genai

MODEL = "gemini-2.5-flash"


def main():
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    print("key loaded:", bool(key), "| length:", len(key or ""))
    if not key:
        raise SystemExit("Key not found")

    client = genai.Client(api_key=key)
    try:
        response = client.models.generate_content(model=MODEL, contents="Say OK")
        print("Gemini reply:", response.text)
    except Exception as e:
        print("Gemini error:", type(e).__name__, str(e)[:300])


if __name__ == "__main__":
    main()