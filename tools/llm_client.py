"""
LLM client used to wire prompt-based tools (e.g. triage_defect_ai) directly
to a real model, so the server can return a computed answer instead of a
bare prompt template for the calling client to fill in.

Reads which provider/model to use from LLM_MODEL, e.g.
"groq:openai/gpt-oss-120b" or "openai:gpt-4o-mini". Falls back to whichever
of GROQ_API_KEY / OPENAI_API_KEY is set if LLM_MODEL has no provider prefix.
"""

import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def _resolve_provider_and_model():
    raw = (os.environ.get("LLM_MODEL") or "").strip()
    if ":" in raw:
        provider, model = raw.split(":", 1)
        return provider.strip().lower(), model.strip()
    if raw:
        if os.environ.get("GROQ_API_KEY"):
            return "groq", raw
        return "openai", raw
    return "", ""


def call_llm(prompt: str, temperature: float = 0.2) -> str:
    """
    Send a prompt to the configured LLM (from LLM_MODEL / GROQ_API_KEY /
    OPENAI_API_KEY in .env) and return its text response.

    Args:
        prompt: The full prompt text to send.
        temperature: Sampling temperature (lower = more deterministic).

    Returns:
        The model's text response, or an error message.
    """
    provider, model = _resolve_provider_and_model()

    if provider == "groq":
        url, api_key = GROQ_URL, os.environ.get("GROQ_API_KEY")
    elif provider == "openai":
        url, api_key = OPENAI_URL, os.environ.get("OPENAI_API_KEY")
    else:
        return (
            "Error: no LLM configured. Set LLM_MODEL (e.g. "
            "'groq:openai/gpt-oss-120b') and the matching API key in .env."
        )

    if not api_key:
        return f"Error: {provider.upper()}_API_KEY is not configured."

    # Log to stderr, not stdout — stdout is reserved for the MCP stdio
    # protocol and printing there would corrupt it.
    print(f"[llm_client] using {provider}:{model}", file=sys.stderr)

    try:
        response = httpx.post(
            url,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )
    except httpx.RequestError as exc:
        return f"Error: could not reach {provider} ({exc})."

    if response.status_code != 200:
        return f"Error: {provider} returned {response.status_code}: {response.text[:300]}"

    data = response.json()
    try:
        answer = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError):
        return f"Error: unexpected response shape from {provider}: {data}"

    return f"[Model used: {provider}:{model}]\n\n{answer}"
