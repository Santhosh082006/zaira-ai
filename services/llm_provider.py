"""
services/llm_provider.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Stage 3: Modular LLM provider.

This module acts as a thin adapter layer so the rest of the application
never needs to know which LLM backend is in use.  The active provider is
chosen at runtime via the LLM_PROVIDER environment variable.

Supported providers
───────────────────
  • "openrouter" – OpenRouter unified API  ← recommended
  • "gemini"     – Google Gemini API
  • "openai"     – OpenAI Chat Completions API
  • "ollama"     – Local Ollama instance (no API key required)

Environment variables (see .env.example for full reference)
────────────────────────────────────────────────────────────
  LLM_PROVIDER         Which provider to use.   Default: "openrouter"

  OPENROUTER_API_KEY   Required when using OpenRouter.
  OPENROUTER_MODEL     Optional.                Default: "google/gemini-flash-1.5"

  GEMINI_API_KEY       Required when using Gemini.
  GEMINI_MODEL         Optional.                Default: "gemini-1.5-flash"

  OPENAI_API_KEY       Required when using OpenAI.
  OPENAI_MODEL         Optional.                Default: "gpt-3.5-turbo"

  OLLAMA_BASE_URL      Optional.                Default: "http://localhost:11434"
  OLLAMA_MODEL         Optional.                Default: "llama3"
"""

from __future__ import annotations

import os
from typing import Optional


# ── Public interface ───────────────────────────────────────────────────────────

def get_active_provider() -> str:
    """Return the name of the currently configured LLM provider."""
    return os.getenv("LLM_PROVIDER", "openrouter").strip().lower()


def call_llm(prompt: str, system_prompt: Optional[str] = None) -> str:
    """
    Send a prompt to the configured LLM and return the text response.

    Parameters
    ----------
    prompt : str
        The user-facing prompt (e.g., the extraction request with transcript).
    system_prompt : str | None
        Optional system-level instructions for the model.

    Returns
    -------
    str
        The model's raw text response.

    Raises
    ------
    ValueError
        If LLM_PROVIDER is set to an unknown value, or a required API key
        is missing.
    ImportError
        If the Python package for the chosen provider is not installed.
    RuntimeError
        If the LLM call fails for any other reason.
    """
    provider = get_active_provider()

    dispatch = {
        "openrouter": _call_openrouter,
        "gemini":     _call_gemini,
        "openai":     _call_openai,
        "ollama":     _call_ollama,
    }

    if provider not in dispatch:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{provider}'. "
            "Valid options are: openrouter, gemini, openai, ollama."
        )

    return dispatch[provider](prompt, system_prompt)


# ── Provider implementations ───────────────────────────────────────────────────

def _call_openrouter(prompt: str, system_prompt: Optional[str]) -> str:
    """
    Call any model through OpenRouter (https://openrouter.ai).

    OpenRouter exposes an OpenAI-compatible REST API, so we reuse the
    official `openai` Python package — just pointing it at a different
    base URL with your OpenRouter key.

    Env vars
    --------
    OPENROUTER_API_KEY  Your OpenRouter API key.
    OPENROUTER_MODEL    Any model slug from openrouter.ai/models.
                        Default: "google/gemini-flash-1.5"
    """
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError(
            "openai is not installed. Run: pip install openai"
        ) from exc

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY is not set. "
            "Add it to your .env file: OPENROUTER_API_KEY=sk-or-..."
        )

    model_name = os.getenv("OPENROUTER_MODEL", "google/gemini-flash-1.5").strip()

    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=30.0,
        default_headers={
            # OpenRouter recommends including these headers
            "HTTP-Referer": "https://github.com/truthlens-ai",
            "X-Title":      "TruthLens AI",
        },
    )

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.0,
        )
        return response.choices[0].message.content
    except Exception as exc:
        raise RuntimeError(f"OpenRouter API call failed: {exc}") from exc


def _call_gemini(prompt: str, system_prompt: Optional[str]) -> str:
    """Call the Google Gemini API."""
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise ImportError(
            "google-generativeai is not installed. "
            "Run: pip install google-generativeai"
        ) from exc

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set. "
            "Add it to your .env file or set it as an environment variable."
        )

    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()
    genai.configure(api_key=api_key)

    # Combine system prompt and user prompt for Gemini
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

    try:
        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={"temperature": 0.0},
        )
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as exc:
        raise RuntimeError(f"Gemini API call failed: {exc}") from exc


def _call_openai(prompt: str, system_prompt: Optional[str]) -> str:
    """Call the OpenAI Chat Completions API."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ImportError(
            "openai is not installed. Run: pip install openai"
        ) from exc

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is not set. "
            "Add it to your .env file or set it as an environment variable."
        )

    model_name = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo").strip()
    client = OpenAI(api_key=api_key, timeout=30.0)

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.0,   # deterministic — no creative additions
        )
        return response.choices[0].message.content
    except Exception as exc:
        raise RuntimeError(f"OpenAI API call failed: {exc}") from exc


def _call_ollama(prompt: str, system_prompt: Optional[str]) -> str:
    """Call a locally running Ollama model via its HTTP API."""
    try:
        import requests
    except ImportError as exc:
        raise ImportError(
            "requests is not installed. Run: pip install requests"
        ) from exc

    base_url  = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model_name = os.getenv("OLLAMA_MODEL", "llama3").strip()

    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

    try:
        response = requests.post(
            f"{base_url}/api/generate",
            json={"model": model_name, "prompt": full_prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["response"]
    except Exception as exc:
        raise RuntimeError(f"Ollama call failed: {exc}") from exc
