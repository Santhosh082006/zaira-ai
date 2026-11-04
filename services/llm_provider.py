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
  OLLAMA_MODEL         Optional.                Default: "qwen2.5:7b"
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
    import os
    if os.environ.get("TEST_MOCK_LLM") == "1":
        if (system_prompt and "interview question" in system_prompt.lower()) or "INTERVIEW CONFIGURATION" in prompt:
            import json
            import re
            domain = None
            if "Technical Domain: Java" in prompt:
                domain = "Java"
                q_text = "How does the Java Virtual Machine manage memory allocation between the Heap and Stack, and how does Garbage Collection affect application performance?"
                topic = "jvm_memory_and_gc"
            elif "Technical Domain: DSA" in prompt:
                domain = "DSA"
                q_text = "How would you implement an efficient algorithm to detect a cycle in a directed graph, and what is its time and space complexity?"
                topic = "graph_algorithms"
            elif "Technical Domain: DBMS" in prompt:
                domain = "DBMS"
                q_text = "Can you explain how database indexing with B+ trees works and how transaction isolation levels mitigate concurrency anomalies?"
                topic = "indexing_and_transactions"
            elif "Technical Domain: Web Development" in prompt:
                domain = "Web Development"
                q_text = "How does the browser event loop handle microtasks versus macrotasks when processing asynchronous operations?"
                topic = "event_loop_and_async"
            elif "Technical Domain: AI/ML" in prompt:
                domain = "AI/ML"
                q_text = "Can you explain the difference between L1 and L2 regularization and how they prevent overfitting in deep neural networks?"
                topic = "regularization_and_overfitting"
            elif "Controller Action: clarification" in prompt or "Controller Action: follow_up" in prompt:
                m = re.search(r'Candidate\'s Latest Answer Transcript:\s*"([^"]+)"', prompt)
                snip = m.group(1).strip() if m else "your previous point"
                if len(snip) > 30:
                    snip = snip[:30] + "..."
                q_text = f"You mentioned '{snip}'. Could you explain the specific steps and reasoning behind that decision?"
                topic = "clarification"
            elif "Custom Goal / Context:" in prompt and "None" not in prompt.split("Custom Goal / Context:")[1].split("\n")[0]:
                custom_txt = prompt.split("Custom Goal / Context:")[1].split("\n")[0].strip()
                q_text = f"Given your focus on {custom_txt}, how would you approach architecting this solution to ensure scalability?"
                topic = "custom_scenario"
            else:
                q_text = "Tell me about a challenging technical problem you solved recently and the trade-offs you considered."
                topic = "problem_solving"

            return json.dumps({
                "question_text": q_text,
                "topic": topic,
                "question_type": "technical" if domain else "behavioral",
                "competencies": ["tech_technical_explanation", "think_problem_solving"],
                "expected_answer_characteristics": ["clarity", "depth", "concrete examples"],
                "follow_up_tags": ["architecture", "trade_offs"],
                "difficulty": 0.6,
                "technical_domain": domain
            })

        return """
        {
            "evaluation_status": "success",
            "relevance": 0.9, "clarity": 0.9, "structure": 0.9,
            "evidence_quality": 0.9, "completeness": 0.9,
            "strengths": ["Excellent response"], "areas_to_improve": [],
            "recommendations": ["Structure complex answers with STAR methodology."],
            "evidence_excerpts": [], "evaluation_limitations": [],
            "competency_evidence": [{"competency_id": "think_problem_solving", "evidence_type": "direct", "excerpt": "mocked transcript", "reasoning": "Valid"}]
        }
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
    max_tokens_env = os.getenv("OPENROUTER_MAX_TOKENS", "").strip()
    try:
        max_tokens = int(max_tokens_env) if max_tokens_env else 1600
    except ValueError:
        max_tokens = 1600

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

    import time
    import re
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.0,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as exc:
            err_str = str(exc)
            # 1. Token allocation adjustment (adaptive retry)
            if "fewer max_tokens" in err_str and attempt < max_retries - 1:
                m = re.search(r"can only afford (\d+)", err_str)
                if m:
                    max_tokens = max(400, int(m.group(1)) - 50)
                else:
                    max_tokens = max(400, max_tokens // 2)
                time.sleep(1.0)
                continue

            # 2. Permanent errors: Never retry insufficient credits, invalid credentials, or forbidden requests
            err_lower = err_str.lower()
            if (
                "insufficient credits" in err_lower
                or "never purchased credits" in err_lower
                or "invalid api key" in err_lower
                or "unauthorized" in err_lower
                or "401" in err_str
                or "403" in err_str
            ):
                raise RuntimeError(f"OpenRouter API call failed (permanent error): {exc}") from exc

            # 3. Transient errors: Retry only rate limits or in-flight buffer exhaustion
            if ("429" in err_str or "in_flight" in err_str or "rate limit" in err_lower) and attempt < max_retries - 1:
                time.sleep(3.0 * (attempt + 1))
                continue

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

    gen_config = {"temperature": 0.0}
    max_tokens_env = os.getenv("GEMINI_MAX_TOKENS", "").strip()
    if max_tokens_env:
        try:
            gen_config["max_output_tokens"] = int(max_tokens_env)
        except ValueError:
            pass

    try:
        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=gen_config,
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
    max_tokens_env = os.getenv("OPENAI_MAX_TOKENS", "").strip()
    try:
        max_tokens = int(max_tokens_env) if max_tokens_env else 2048
    except ValueError:
        max_tokens = 2048

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
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
    except Exception as exc:
        raise RuntimeError(f"OpenAI API call failed: {exc}") from exc


def _call_ollama(prompt: str, system_prompt: Optional[str]) -> str:
    """
    Call a locally running Ollama model via its HTTP API.

    Env vars
    --------
    OLLAMA_BASE_URL   Base URL for local Ollama daemon. Default: "http://localhost:11434"
    OLLAMA_MODEL      Model name.                       Default: "qwen2.5:7b"
    OLLAMA_TIMEOUT    Request timeout in seconds.       Default: 300.0
    OLLAMA_MAX_TOKENS Maximum tokens to generate.       Default: 1024
    """
    try:
        import requests
    except ImportError as exc:
        raise ImportError(
            "requests is not installed. Run: pip install requests"
        ) from exc

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model_name = os.getenv("OLLAMA_MODEL", "qwen2.5:7b").strip()

    timeout_env = os.getenv("OLLAMA_TIMEOUT", "").strip()
    try:
        timeout = float(timeout_env) if timeout_env else 300.0
    except ValueError:
        timeout = 300.0

    max_tokens_env = os.getenv("OLLAMA_MAX_TOKENS", "").strip()
    try:
        max_tokens = int(max_tokens_env) if max_tokens_env else 1024
    except ValueError:
        max_tokens = 1024

    payload: dict = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": max_tokens,
        },
    }
    if system_prompt:
        payload["system"] = system_prompt

    # If JSON output is requested, enforce Ollama's schema-constrained JSON format
    combined_instructions = (prompt + " " + (system_prompt or "")).lower()
    if "json" in combined_instructions and any(
        kw in combined_instructions
        for kw in ("schema", "format", "valid json", "raw json", "output json", "json only", "respond only with")
    ):
        payload["format"] = "json"

    try:
        response = requests.post(
            f"{base_url}/api/generate",
            json=payload,
            timeout=timeout,
        )
        if response.status_code == 404:
            raise RuntimeError(
                f"Ollama model '{model_name}' not found at {base_url} (HTTP 404). "
                f"Ensure the model is pulled by running 'ollama pull {model_name}'."
            )
        response.raise_for_status()
        resp_json = response.json()
        return resp_json.get("response", "")
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            f"Ollama connection failed: Could not connect to Ollama at {base_url} (port 11434). "
            "Ensure the local Ollama daemon is running."
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(
            f"Ollama request to model '{model_name}' timed out after {timeout}s."
        ) from exc
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(f"Ollama call failed: {exc}") from exc
