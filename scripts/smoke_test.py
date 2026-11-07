"""
Smoke test: confirms .env is wired up and the LLM providers respond.

1. Chat: OpenRouter (Claude Haiku) replies to "Reply with OK".
2. Embeddings: OpenAI embeds one string (skipped if OPENAI_API_KEY is unset).

Usage:
  .venv\\Scripts\\python.exe scripts\\smoke_test.py
"""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load the repo-root .env explicitly so the script works from any cwd
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Newest Haiku on https://openrouter.ai/api/v1/models as of 2026-10-28.
# Pinned rather than ~anthropic/claude-haiku-latest so results don't drift.
OPENROUTER_MODEL = "anthropic/claude-haiku-5.5"
DEFAULT_EMBED_MODEL = "text-embedding-3-small"


def check_chat() -> bool:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print(f"[chat] FAIL: OPENROUTER_API_KEY not set (looked in {ENV_PATH})")
        return False

    try:
        r = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": OPENROUTER_MODEL,
                "messages": [{"role": "user", "content": "Reply with OK"}],
                "max_tokens": 10,
            },
            timeout=60,
        )
    except requests.RequestException as e:
        print(f"[chat] FAIL: request error: {e}")
        return False

    if r.status_code != 200:
        print(f"[chat] FAIL: HTTP {r.status_code}: {r.text[:300]}")
        return False

    data = r.json()
    reply = data["choices"][0]["message"]["content"]
    print(f"[chat] requested model: {OPENROUTER_MODEL}")
    print(f"[chat] served by model: {data.get('model')}")
    print(f"[chat] response:        {reply!r}")
    return True


def check_embeddings() -> bool:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[embed] embeddings skipped (OPENAI_API_KEY not set)")
        return True

    from openai import OpenAI

    model = os.getenv("OPENAI_EMBED_MODEL") or DEFAULT_EMBED_MODEL
    try:
        resp = OpenAI(api_key=api_key).embeddings.create(model=model, input="smoke test")
    except Exception as e:
        print(f"[embed] FAIL: {type(e).__name__}: {e}")
        return False

    print(f"[embed] model:         {model}")
    print(f"[embed] vector length: {len(resp.data[0].embedding)}")
    return True


def main() -> int:
    results = [check_chat(), check_embeddings()]
    ok = all(results)
    print("\nSMOKE TEST PASSED" if ok else "\nSMOKE TEST FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
