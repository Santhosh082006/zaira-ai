"""
tests/mock_llm.py
─────────────────────────────────────────────────────────────────────────────
Extracted mock LLM responses for deterministic testing.

This module contains mock logic that was previously inline inside
`services/llm_provider.call_llm()`, gated by the TEST_MOCK_LLM env var.
"""

from __future__ import annotations

import json
import re
from typing import Optional, Callable


def mock_call_llm(
    prompt: str,
    system_prompt: Optional[str] = None,
    on_chunk: Optional[Callable[[str], None]] = None
) -> str:
    """
    Return deterministic mock LLM responses for testing.

    Handles two cases:
    1. Interview question generation — returns a JSON question object.
    2. Everything else — returns a JSON evaluation stub.
    """
    if on_chunk:
        on_chunk("Evaluating candidate response against rubric criteria...\n")
        on_chunk("Checking technical accuracy and structural completeness...\n")

    if (system_prompt and "interview question" in system_prompt.lower()) or "INTERVIEW CONFIGURATION" in prompt:

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
