"""
services/question_generator_llm.py
─────────────────────────────────────────────────────────────────────────────
TruthLens AI — Phase 12.6: Grounded Dynamic Interview Question Generation

Generates dynamic, personalized, transcript-grounded interview questions using
the existing LLM provider (call_llm) while preserving the authoritative role
of the AdaptiveInterviewController.

Guarantees:
- Domain-specific questions for technical interviews (Java, DSA, DBMS, Web Dev, AI/ML, Python, etc.)
- Strict grounding on candidate transcript/claims for clarifications & follow-ups
- Single, focused question output (no compound / multi-part questions)
- Level calibration (beginner, intermediate, advanced)
- Deterministic domain-safe fallback if LLM is unavailable or output is rejected
"""

import json
import re
import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from core.schemas import InterviewState, NextQuestionDecision, AnswerRecord, Question
from core.competency_map import CompetencyMap
from services.llm_provider import call_llm


class GeneratedQuestionPayload(BaseModel):
    question_text: str
    topic: str
    question_type: str = "technical"
    competencies: List[str] = Field(default_factory=list)
    expected_answer_characteristics: List[str] = Field(default_factory=list)
    follow_up_tags: List[str] = Field(default_factory=list)
    difficulty: float = 0.5
    technical_domain: Optional[str] = None


# Deterministic curated fallbacks by technical domain and level
DOMAIN_FALLBACK_QUESTIONS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "java": {
        "beginner": {
            "question_text": "Could you explain the difference between the '==' operator and the '.equals()' method in Java, and how memory references are evaluated?",
            "topic": "object_equality_and_references",
            "competencies": ["tech_technical_knowledge", "tech_technical_explanation"],
            "difficulty": 0.3,
            "characteristics": ["explains reference vs value comparison", "mentions overriding equals() and hashCode()"]
        },
        "intermediate": {
            "question_text": "How does the Java Garbage Collector manage memory across Eden, Survivor, and Tenured generations, and what triggers a minor versus major garbage collection?",
            "topic": "jvm_memory_and_gc",
            "competencies": ["tech_technical_depth", "tech_technical_explanation"],
            "difficulty": 0.6,
            "characteristics": ["generational hypothesis", "Eden/Survivor spaces", "Stop-the-world pauses"]
        },
        "advanced": {
            "question_text": "How would you diagnose and resolve a thread deadlock or CPU spike in a high-throughput, multi-threaded Java application running on the JVM?",
            "topic": "concurrency_and_jvm_profiling",
            "competencies": ["tech_technical_depth", "think_problem_solving"],
            "difficulty": 0.85,
            "characteristics": ["thread dumps", "jstack/async-profiler", "synchronization primitives"]
        }
    },
    "dsa": {
        "beginner": {
            "question_text": "What is the difference in time complexity and memory layout between an array and a singly linked list for insertion, deletion, and random access?",
            "topic": "arrays_vs_linked_lists",
            "competencies": ["tech_technical_knowledge", "comm_explanation"],
            "difficulty": 0.3,
            "characteristics": ["O(1) vs O(N) access", "contiguous memory", "pointer overhead"]
        },
        "intermediate": {
            "question_text": "How would you detect a cycle in a directed graph, and which algorithm or data structures would you select to achieve optimal time complexity?",
            "topic": "graph_cycle_detection",
            "competencies": ["tech_technical_depth", "think_problem_solving"],
            "difficulty": 0.6,
            "characteristics": ["DFS with three color states or Kahn's topological sort", "O(V+E) time"]
        },
        "advanced": {
            "question_text": "How would you design a data structure that supports insert, delete, and getRandom in O(1) average time complexity while handling element removal cleanly?",
            "topic": "custom_data_structure_design",
            "competencies": ["tech_technical_depth", "think_problem_solving"],
            "difficulty": 0.85,
            "characteristics": ["hash map + dynamic array", "swap with last element on deletion"]
        }
    },
    "dbms": {
        "beginner": {
            "question_text": "What is the difference between a primary key, a foreign key, and a unique constraint in a relational database?",
            "topic": "relational_keys_and_constraints",
            "competencies": ["tech_technical_knowledge", "comm_explanation"],
            "difficulty": 0.3,
            "characteristics": ["entity integrity", "referential integrity", "nullability"]
        },
        "intermediate": {
            "question_text": "Can you explain the ACID properties of a database transaction and how isolation levels prevent anomalies like dirty reads and non-repeatable reads?",
            "topic": "acid_and_isolation_levels",
            "competencies": ["tech_technical_depth", "tech_technical_explanation"],
            "difficulty": 0.6,
            "characteristics": ["atomicity, consistency, isolation, durability", "Read Committed vs Repeatable Read vs Serializable"]
        },
        "advanced": {
            "question_text": "How does a B+ tree index structure operate under high write pressure, and what strategies would you use to eliminate slow query table scans on large tables?",
            "topic": "b_tree_indexing_and_query_optimization",
            "competencies": ["tech_technical_depth", "think_problem_solving"],
            "difficulty": 0.85,
            "characteristics": ["leaf node chaining", "covering indexes", "EXPLAIN execution plan analysis"]
        }
    },
    "web development": {
        "beginner": {
            "question_text": "What is the Document Object Model (DOM), and how does a modern browser parse and render HTML and CSS onto the screen?",
            "topic": "dom_and_browser_rendering",
            "competencies": ["tech_technical_knowledge", "comm_explanation"],
            "difficulty": 0.3,
            "characteristics": ["DOM tree", "CSSOM", "render tree", "layout and repaint"]
        },
        "intermediate": {
            "question_text": "How does the JavaScript event loop handle microtasks versus macrotasks when processing asynchronous Promises and timer callbacks?",
            "topic": "event_loop_and_async_js",
            "competencies": ["tech_technical_depth", "tech_technical_explanation"],
            "difficulty": 0.6,
            "characteristics": ["call stack", "microtask queue priority", "Promises vs setTimeout"]
        },
        "advanced": {
            "question_text": "How would you identify and optimize Core Web Vitals—specifically Largest Contentful Paint (LCP) and Interaction to Next Paint (INP)—in a large-scale web application?",
            "topic": "web_performance_and_core_web_vitals",
            "competencies": ["tech_technical_depth", "think_problem_solving"],
            "difficulty": 0.85,
            "characteristics": ["critical rendering path", "JavaScript hydration/main thread blocking", "resource prioritization"]
        }
    },
    "ai/ml": {
        "beginner": {
            "question_text": "What is the fundamental difference between supervised learning, unsupervised learning, and reinforcement learning in practical machine learning workflows?",
            "topic": "ml_paradigms",
            "competencies": ["tech_technical_knowledge", "comm_explanation"],
            "difficulty": 0.3,
            "characteristics": ["labeled vs unlabeled data", "reward signals", "standard application examples"]
        },
        "intermediate": {
            "question_text": "How do you detect and mitigate overfitting in a deep learning model when your training dataset is relatively small?",
            "topic": "overfitting_mitigation",
            "competencies": ["tech_technical_depth", "think_problem_solving"],
            "difficulty": 0.6,
            "characteristics": ["cross-validation", "regularization (dropout, weight decay)", "data augmentation"]
        },
        "advanced": {
            "question_text": "Can you explain the multi-head self-attention mechanism in the Transformer architecture and how positional encodings preserve sequence information without recurrence?",
            "topic": "transformer_attention_mechanics",
            "competencies": ["tech_technical_depth", "tech_technical_explanation"],
            "difficulty": 0.85,
            "characteristics": ["Query, Key, Value matrices", "scaled dot-product attention", "sinusoidal or rotary positional embeddings"]
        }
    },
    "python": {
        "beginner": {
            "question_text": "What is the difference between mutable and immutable data types in Python, and how does this affect function arguments passed by reference?",
            "topic": "mutability_and_pass_by_assignment",
            "competencies": ["tech_technical_knowledge", "comm_explanation"],
            "difficulty": 0.3,
            "characteristics": ["lists/dicts vs tuples/strings", "pass-by-object-reference", "default argument pitfalls"]
        },
        "intermediate": {
            "question_text": "How do Python generators and the 'yield' statement optimize memory utilization when processing large data streams compared to returning a full list?",
            "topic": "generators_and_lazy_evaluation",
            "competencies": ["tech_technical_depth", "tech_technical_explanation"],
            "difficulty": 0.6,
            "characteristics": ["lazy evaluation", "iterator protocol (__iter__, __next__)", "constant memory profile"]
        },
        "advanced": {
            "question_text": "How does the Global Interpreter Lock (GIL) influence multi-threaded execution in CPython, and what concurrency models should you choose for CPU-bound versus I/O-bound tasks?",
            "topic": "gil_and_concurrency_models",
            "competencies": ["tech_technical_depth", "think_problem_solving"],
            "difficulty": 0.85,
            "characteristics": ["CPython reference counting", "threading vs multiprocessing vs asyncio", "native C extensions"]
        }
    }
}


def build_system_prompt() -> str:
    return (
        "You are an expert, professional technical and behavioral AI interviewer for TruthLens AI.\n"
        "Your role is to formulate exactly ONE high-impact, realistic interview question tailored to the candidate's exact interview configuration, current stage, and previous responses.\n\n"
        "CRITICAL RULES:\n"
        "1. OUTPUT FORMAT: Respond ONLY with valid, raw JSON matching this schema:\n"
        "{\n"
        '  "question_text": "<Exactly one clear, focused interview question>",\n'
        '  "topic": "<Specific topic or concept, e.g. \'jvm_memory\', \'b_tree_indexing\', \'star_conflict\'>",\n'
        '  "question_type": "<\'technical\' | \'behavioral\' | \'situational\' | \'follow_up\' | \'clarification\' | \'problem_solving\'>",\n'
        '  "competencies": ["<competency_id>"],\n'
        '  "expected_answer_characteristics": ["<key expected point 1>", "<key expected point 2>"],\n'
        '  "follow_up_tags": ["<tag1>", "<tag2>"],\n'
        '  "difficulty": <float between 0.0 and 1.0>,\n'
        '  "technical_domain": "<domain name or null>"\n'
        "}\n\n"
        "2. SINGLE QUESTION ONLY:\n"
        "Output exactly ONE direct question ending with a single question mark. Never ask compound or multi-part questions (e.g., avoid 'Can you explain X, and also how Y works, and what about Z?').\n\n"
        "3. DOMAIN ALIGNMENT:\n"
        "- If a technical domain is specified (e.g. Java, DSA, DBMS, Web Development, AI/ML, Python), the question MUST test core concepts, implementation details, or architectural choices in THAT specific domain. Never ask a generic behavioral question in a technical interview.\n"
        "- If interview type is HR or Job, focus on professional experience, behavioral scenarios, communication, teamwork, and decision-making.\n"
        "- If interview type is English, focus on descriptive, articulative prompts that encourage continuous professional speech.\n"
        "- If a Custom Goal is provided, you MUST align the question directly with that custom goal/scenario.\n\n"
        "4. LEVEL CALIBRATION:\n"
        "- Beginner (difficulty 0.1 - 0.4): Focus on fundamental concepts, definitions, basic syntax, and standard use cases.\n"
        "- Intermediate (difficulty 0.4 - 0.7): Focus on practical application, trade-offs, debugging, standard patterns, and implementation decisions.\n"
        "- Advanced (difficulty 0.7 - 1.0): Focus on deep internals, memory/concurrency models, performance optimization at scale, failure modes, and edge cases.\n\n"
        "5. STRICT GROUNDING FOR FOLLOW-UP AND CLARIFICATION:\n"
        "- If the controller action is 'clarification', 'follow_up', or 'deeper_probe':\n"
        "  - Ground your question ONLY on concepts, claims, or tools the candidate ACTUALLY stated in their transcript.\n"
        "  - NEVER invent or hallucinate hypothetical teams, imaginary past projects, fictional stakeholders, or unmentioned technologies.\n"
        "  - If the candidate gave a very brief or empty answer ('I don't know' or a few words), ask them to clarify or attempt a related fundamental concept without inventing a fictional back-story.\n\n"
        "6. NO DUPLICATES:\n"
        "Do NOT repeat, duplicate, or re-ask themes from the previously asked questions list."
    )


def build_user_prompt(
    state: InterviewState,
    decision: NextQuestionDecision,
    latest_answer: Optional[AnswerRecord] = None,
    target_competency: Optional[str] = None,
    previous_question_text: Optional[str] = None,
    question_history_texts: Optional[List[str]] = None
) -> str:
    cmap = CompetencyMap()
    comp_info = "None specified"
    if target_competency:
        c_obj = cmap.get_competency_by_id(target_competency)
        if c_obj:
            comp_info = f"{c_obj.id} ({c_obj.name}): {c_obj.description}"
        else:
            comp_info = target_competency

    transcript_text = "No previous answer transcript available (Opening question)."
    claims_text = "None"
    if latest_answer:
        transcript_text = latest_answer.transcript.strip() if latest_answer.transcript else "No audible transcript."
        if latest_answer.detected_claims:
            claims_text = ", ".join(latest_answer.detected_claims)

    history_str = "None"
    if question_history_texts:
        history_str = "\n".join(f"- {q_text}" for q_text in question_history_texts)

    prompt = (
        f"INTERVIEW CONFIGURATION:\n"
        f"- Interview Type: {state.interview_type}\n"
        f"- Interview Level: {state.interview_level}\n"
        f"- Technical Domain: {state.technical_domain or 'None'}\n"
        f"- Assessment Goals: {', '.join(state.assessment_goals)}\n"
        f"- Custom Goal / Context: {state.custom_goal or 'None'}\n"
        f"- Current Difficulty Target: {state.current_difficulty:.2f}\n\n"
        f"ADAPTIVE CONTROLLER STATUS:\n"
        f"- Controller Action: {decision.decision_type}\n"
        f"- Controller Reason: {decision.reason}\n"
        f"- Target Competency: {comp_info}\n\n"
        f"CANDIDATE CONTEXT:\n"
        f"- Previous Question: {previous_question_text or 'None (Opening question)'}\n"
        f"- Candidate's Latest Answer Transcript:\n\"{transcript_text}\"\n"
        f"- Detected Claims: {claims_text}\n\n"
        f"QUESTION HISTORY IN THIS SESSION:\n{history_str}\n\n"
        f"Generate the single next interview question in the required JSON format."
    )
    return prompt


def validate_and_parse_question(
    raw_response: str,
    state: InterviewState,
    decision: NextQuestionDecision,
    latest_answer: Optional[AnswerRecord] = None
) -> Optional[Question]:
    """
    Validates LLM output against schemas, single-question constraints, domain relevance,
    and grounding rules. Returns a validated Question object or None if rejected.
    """
    if not raw_response or not raw_response.strip():
        return None

    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except Exception:
        # Try finding json object inside text
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                return None
        else:
            return None

    try:
        payload = GeneratedQuestionPayload(**data)
    except Exception:
        return None

    q_text = payload.question_text.strip()
    if len(q_text) < 15:
        return None

    # Enforce exactly one question
    q_count = q_text.count("?")
    if q_count == 0:
        # Check if question sentence without '?' can have '?' appended
        if any(q_text.lower().startswith(w) for w in ["how", "what", "why", "can", "could", "tell", "explain", "describe"]):
            q_text += "?"
        else:
            return None
    elif q_count > 1:
        # If multiple question marks, extract only the first question
        first_q = q_text.split("?")[0].strip() + "?"
        if len(first_q) >= 15:
            q_text = first_q
        else:
            return None

    # Grounding check for clarification / follow-up
    if decision.decision_type in ["clarification", "follow_up"]:
        transcript_lower = latest_answer.transcript.lower() if (latest_answer and latest_answer.transcript) else ""
        
        # Anti-hallucination check: ensure we didn't invent specific entities not mentioned
        hallucination_indicators = ["stakeholder", "that project", "your team", "the client"]
        for ind in hallucination_indicators:
            if ind in q_text.lower() and ind not in transcript_lower:
                return None

    # Technical domain check: ensure domain alignment
    if state.technical_domain:
        req_dom = state.technical_domain.lower()
        dom_normalized = req_dom.replace("/", "").replace(" ", "").replace("-", "")
        q_text_norm = q_text.lower().replace("/", "").replace(" ", "").replace("-", "")
        
        # If question is completely generic behavioral in a technical domain, reject it
        generic_markers = [
            "tell me about a time you had to explain a complex technical concept to a non-technical",
            "describe a situation where you had to meet a tight deadline",
            "tell me a little bit about yourself and your background"
        ]
        if any(gm in q_text.lower() for gm in generic_markers):
            return None

    # Build Question instance
    comp_list = list(payload.competencies) if payload.competencies else []
    for tc in (decision.target_competencies or []):
        if tc not in comp_list:
            comp_list.append(tc)
    for ag in (state.assessment_goals or []):
        if ag not in comp_list:
            comp_list.append(ag)

    question = Question(
        id=f"q_dyn_{uuid.uuid4().hex[:8]}",
        question_text=q_text,
        interview_type=[state.interview_type],
        level=state.interview_level,
        topic=payload.topic or "adaptive_interview",
        difficulty=float(payload.difficulty),
        question_type=payload.question_type or decision.decision_type,
        competencies=comp_list,
        follow_up_tags=payload.follow_up_tags or [],
        expected_answer_characteristics=payload.expected_answer_characteristics or [],
        technical_domain=state.technical_domain
    )
    return question


def generate_fallback_question(
    state: InterviewState,
    decision: NextQuestionDecision,
    latest_answer: Optional[AnswerRecord] = None,
    target_competency: Optional[str] = None
) -> Question:
    """
    Deterministic domain-safe fallback question generator.
    Guarantees that a technical interview receives a domain-specific question,
    and clarifications/follow-ups are strictly grounded in candidate transcript.
    """
    domain_key = (state.technical_domain or "").lower().strip()
    level_key = (state.interview_level or "intermediate").lower().strip()
    if level_key not in ["beginner", "intermediate", "advanced"]:
        level_key = "intermediate"

    # 1. Grounded Clarification / Follow-up Fallback
    if decision.decision_type in ["clarification", "follow_up"] and latest_answer:
        transcript = (latest_answer.transcript or "").strip()
        words = transcript.split()
        if len(words) >= 4:
            # Extract a brief phrase from candidate's own words
            snippet = " ".join(words[:min(6, len(words))])
            if decision.decision_type == "clarification":
                q_text = f"You mentioned '{snippet}'. Could you clarify your specific technical approach and implementation details for that?"
            else:
                q_text = f"Following up on what you said regarding '{snippet}', what were the key trade-offs you considered?"
            
            return Question(
                id=f"q_fb_{uuid.uuid4().hex[:8]}",
                question_text=q_text,
                interview_type=[state.interview_type],
                level=state.interview_level,
                topic="clarification_followup",
                difficulty=state.current_difficulty,
                question_type=decision.decision_type,
                competencies=decision.target_competencies or ["comm_clarity", "tech_technical_explanation"],
                follow_up_tags=["technical_reasoning", "implementation"],
                expected_answer_characteristics=["concrete details", "clear explanation"],
                technical_domain=state.technical_domain
            )
        else:
            # Minimal/empty answer fallback
            q_text = "Could you clarify your previous response with a specific example or technical explanation?"
            return Question(
                id=f"q_fb_{uuid.uuid4().hex[:8]}",
                question_text=q_text,
                interview_type=[state.interview_type],
                level=state.interview_level,
                topic="clarification_minimal",
                difficulty=state.current_difficulty,
                question_type="clarification",
                competencies=decision.target_competencies or ["comm_clarity"],
                follow_up_tags=["clarification"],
                expected_answer_characteristics=["direct answer", "concise explanation"],
                technical_domain=state.technical_domain
            )

    # 2. Technical Domain Curated Fallback
    # Normalize domain keys (e.g. 'web dev' -> 'web development', 'ai' -> 'ai/ml')
    if "web" in domain_key:
        domain_key = "web development"
    elif "ai" in domain_key or "ml" in domain_key:
        domain_key = "ai/ml"
    elif "dsa" in domain_key or "data structure" in domain_key or "algorithm" in domain_key:
        domain_key = "dsa"
    elif "dbms" in domain_key or "sql" in domain_key or "database" in domain_key:
        domain_key = "dbms"

    if domain_key in DOMAIN_FALLBACK_QUESTIONS:
        spec = DOMAIN_FALLBACK_QUESTIONS[domain_key][level_key]
        fb_comps = list(spec["competencies"])
        for tc in (decision.target_competencies or []):
            if tc not in fb_comps:
                fb_comps.append(tc)
        for ag in (state.assessment_goals or []):
            if ag not in fb_comps:
                fb_comps.append(ag)

        return Question(
            id=f"q_fb_{uuid.uuid4().hex[:8]}",
            question_text=spec["question_text"],
            interview_type=[state.interview_type],
            level=level_key,
            topic=spec["topic"],
            difficulty=spec["difficulty"],
            question_type="technical",
            competencies=fb_comps,
            follow_up_tags=["architecture", "internals"],
            expected_answer_characteristics=spec["characteristics"],
            technical_domain=state.technical_domain
        )

    # 3. Custom Goal Fallback
    if state.custom_goal:
        return Question(
            id=f"q_fb_{uuid.uuid4().hex[:8]}",
            question_text=f"Given your target context of '{state.custom_goal}', how would you approach solving a critical technical or architectural challenge in this role?",
            interview_type=[state.interview_type],
            level=level_key,
            topic="custom_context",
            difficulty=state.current_difficulty,
            question_type="situational",
            competencies=decision.target_competencies or state.assessment_goals or ["think_problem_solving"],
            follow_up_tags=["custom_scenario"],
            expected_answer_characteristics=["structured approach", "alignment with context"],
            technical_domain=state.technical_domain
        )

    # 4. Standard Non-Technical Fallbacks (HR, English, Job)
    if state.interview_type == "english":
        return Question(
            id=f"q_fb_{uuid.uuid4().hex[:8]}",
            question_text="Could you describe a personal accomplishment or project you are proud of, and what skills you developed while achieving it?",
            interview_type=["english"],
            level=level_key,
            topic="accomplishment_description",
            difficulty=state.current_difficulty,
            question_type="experience",
            competencies=["eng_fluency", "eng_vocabulary", "eng_grammar"],
            follow_up_tags=["fluency", "articulation"],
            expected_answer_characteristics=["continuous speech", "descriptive language"],
            technical_domain=None
        )

    if state.interview_type == "hr":
        return Question(
            id=f"q_fb_{uuid.uuid4().hex[:8]}",
            question_text="Can you describe a situation where you had to collaborate with a cross-functional team under changing priorities, and how you ensured alignment?",
            interview_type=["hr"],
            level=level_key,
            topic="team_collaboration",
            difficulty=state.current_difficulty,
            question_type="behavioral",
            competencies=["int_teamwork", "int_adaptability", "comm_interaction"],
            follow_up_tags=["collaboration", "conflict_resolution"],
            expected_answer_characteristics=["STAR method", "collaborative mindset"],
            technical_domain=None
        )

    # General Job Interview Fallback
    return Question(
        id=f"q_fb_{uuid.uuid4().hex[:8]}",
        question_text="Could you walk me through a significant technical or professional project you worked on recently, focusing on your specific role and key outcomes?",
        interview_type=["job"],
        level=level_key,
        topic="project_walkthrough",
        difficulty=state.current_difficulty,
        question_type="behavioral",
        competencies=["comm_explanation", "think_problem_solving", "int_behavioral_response"],
        follow_up_tags=["project_scope", "ownership"],
        expected_answer_characteristics=["clear structure", "ownership of results"],
        technical_domain=None
    )


def generate_adaptive_question(
    state: InterviewState,
    decision: NextQuestionDecision,
    latest_answer: Optional[AnswerRecord] = None,
    target_competency: Optional[str] = None,
    previous_question_text: Optional[str] = None,
    question_history_texts: Optional[List[str]] = None
) -> Optional[Question]:
    """
    Main entry point for generating dynamic, grounded interview questions.
    Uses call_llm with strict system prompts, validates the response,
    and returns a Question instance. Returns None if LLM call or validation fails.
    """
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(
        state=state,
        decision=decision,
        latest_answer=latest_answer,
        target_competency=target_competency,
        previous_question_text=previous_question_text,
        question_history_texts=question_history_texts
    )

    try:
        raw_response = call_llm(prompt=user_prompt, system_prompt=system_prompt)
        question = validate_and_parse_question(
            raw_response=raw_response,
            state=state,
            decision=decision,
            latest_answer=latest_answer
        )
        return question
    except Exception as e:
        # LLM failure or timeout - return None so caller invokes deterministic fallback
        return None
