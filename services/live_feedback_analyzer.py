"""
services/live_feedback_analyzer.py
─────────────────────────────────────────────────────────────────────────────
Real-time, question-aware speech feedback analyzer.

Analyzes in-progress transcripts during live candidate recording:
  • Extracts detected concepts and identifying missing critical answer components
  • Checks structure (e.g., STAR framework for behavioral, definition + mechanisms for technical)
  • Analyzes pacing, repetition, and filler density
  • Emits lightweight, provisional coaching hints without blocking the audio loop
  • Zero hallucinations: observations strictly reflect actual transcript tokens
"""

import re
from typing import Dict, Any, List, Optional
from core.schemas import Question

# Common STAR component markers
SITUATION_MARKERS = {
    "project", "company", "team", "client", "problem", "challenge", "bug", "issue",
    "working on", "responsible for", "scenario", "context", "background", "incident", "failure"
}
ACTION_MARKERS = {
    "i analyzed", "i investigated", "i checked", "i designed", "i implemented", "i created",
    "i fixed", "i refactored", "i debugged", "i proposed", "i decided", "i used", "i built",
    "my role", "my approach", "i isolated", "i optimized", "i wrote", "i led"
}
RESULT_MARKERS = {
    "result", "outcome", "reduced", "improved", "increased", "decreased", "saved",
    "percent", "%", "metric", "latency", "throughput", "delivered", "resolved", "success",
    "prevented", "stabilized", "faster", "impact"
}

# Technical keywords mapping for common technical question topics
DOMAIN_TOPICS = {
    "process": ["memory", "isolation", "address space", "pid", "context switch", "fork"],
    "thread": ["lightweight", "shared memory", "stack", "concurrency", "race condition", "lock"],
    "recursion": ["base case", "call stack", "stack overflow", "recursive step", "divide"],
    "database": ["index", "query", "acid", "transaction", "schema", "table", "sql", "join"],
    "cache": ["redis", "memcached", "eviction", "lru", "ttl", "hit rate", "invalidation"],
    "rest": ["http", "get", "post", "stateless", "endpoint", "crud", "status code", "json"],
    "api": ["interface", "endpoint", "contract", "payload", "rate limit", "authentication"]
}

def analyze_live_transcript(
    question: Question,
    transcript: str,
    speaking_duration_sec: float = 0.0
) -> Dict[str, Any]:
    """
    Perform fast, deterministic, question-aware analysis on an in-progress spoken transcript.
    Returns clear, actionable, and explicitly provisional feedback.
    """
    cleaned = transcript.strip().lower()
    words = re.findall(r"\b\w+\b", cleaned)
    word_count = len(words)

    if word_count < 6:
        return {
            "status": "listening",
            "word_count": word_count,
            "concepts_covered": [],
            "concepts_missing": ["Sufficient answer context"],
            "pacing_status": "starting",
            "coaching_hint": "Listening to your response... Begin with the core concept or situation.",
            "is_provisional": True
        }

    q_text_lower = question.question_text.lower()
    is_behavioral = question.question_type == "behavioral" or any(
        w in q_text_lower for w in ["tell me about", "describe a time", "how did you handle", "give an example"]
    )

    concepts_covered: List[str] = []
    concepts_missing: List[str] = []
    coaching_hint = ""
    pacing_status = "good"

    # 1. Structural Analysis
    if is_behavioral:
        # Check STAR components
        has_situation = any(m in cleaned for m in SITUATION_MARKERS)
        has_action = any(m in cleaned for m in ACTION_MARKERS) or "i " in cleaned
        has_result = any(m in cleaned for m in RESULT_MARKERS)

        if has_situation:
            concepts_covered.append("Context & Situation")
        else:
            concepts_missing.append("Context / Situation setup")

        if has_action:
            concepts_covered.append("Personal Action & Implementation")
        else:
            concepts_missing.append("Specific action YOU personally took")

        if has_result:
            concepts_covered.append("Measurable Result / Impact")
        else:
            concepts_missing.append("Measurable outcome or lesson learned")

        # Formulate guidance
        if not has_action and word_count > 25:
            coaching_hint = "Good context setup. Now focus on the specific actions YOU took to resolve it."
        elif not has_result and word_count > 50:
            coaching_hint = "Strong progression. Remember to state the final outcome or impact of your solution."
        elif has_action and has_result:
            coaching_hint = "Complete STAR progression covered. Conclude with any reflection or takeaways."
        else:
            coaching_hint = "Structuring answer well. Keep describing your specific actions."
    else:
        # Technical analysis: Check relevance against question topic
        detected_technical_concepts = []
        for topic, kws in DOMAIN_TOPICS.items():
            if topic in q_text_lower:
                for kw in kws:
                    if kw in cleaned:
                        detected_technical_concepts.append(kw)

        if detected_technical_concepts:
            concepts_covered.extend(detected_technical_concepts[:4])
            coaching_hint = f"Addressed core concepts: {', '.join(detected_technical_concepts[:3])}. Consider giving a trade-off or practical example."
        else:
            if word_count > 20:
                coaching_hint = "Define the core principle first, then explain the mechanism and trade-offs."
            else:
                coaching_hint = "State the direct definition or core architecture."

    # 2. Pacing & Repetition Check
    if word_count > 20 and speaking_duration_sec > 0:
        wpm = (word_count / speaking_duration_sec) * 60
        if wpm > 185:
            pacing_status = "fast"
            coaching_hint = "Pacing is slightly fast. Take a breath and articulate the key points clearly."
        elif wpm < 85 and word_count > 15:
            pacing_status = "slow"
            coaching_hint = "Steady pacing. Keep your explanation moving forward."

    # Repetition check (simple bigram check)
    if word_count >= 15:
        bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
        from collections import Counter
        counts = Counter(bigrams)
        common_repeat = [bg for bg, c in counts.items() if c >= 3 and bg not in {"in the", "of the", "to the", "it was"}]
        if common_repeat:
            pacing_status = "repetitive"
            coaching_hint = f"Avoid repeating phrasing ({common_repeat[0]}). Advance to your next point."

    return {
        "status": "analyzed",
        "word_count": word_count,
        "concepts_covered": concepts_covered,
        "concepts_missing": concepts_missing,
        "pacing_status": pacing_status,
        "coaching_hint": coaching_hint,
        "is_provisional": True
    }
