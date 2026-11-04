import json
import logging
import re
from typing import Dict, Any, List, Optional
from pydantic import ValidationError

from services.llm_provider import call_llm
from core.schemas import StructuredEvaluation, Question, Competency, RubricCriterionResult, ActionableFinding, CompetencyEvidenceDetail

logger = logging.getLogger(__name__)

EVALUATION_PROMPT_TEMPLATE = """
You are an experienced, principled senior technical interviewer and communication coach.
Evaluate the candidate's answer based strictly on the transcript below.

INTERVIEW CONTEXT:
Type: {interview_type}
Level: {level}
Assessment Goals: {assessment_goals}

QUESTION:
{question_text}
(Type: {question_type})

TARGET COMPETENCIES & MARKERS:
{competency_context}

CANDIDATE TRANSCRIPT:
"{transcript}"

CRITICAL INTERVIEWER EVALUATION PRINCIPLES:
1. NON-NEGOTIABLE RULE: Every mark deduction must be traceable to a specific rubric criterion and supported by evidence from the candidate's answer.
   If marks are deducted (marks_awarded < max_marks):
   - evidence_quote: Exact quote from the transcript (or clear observable pattern). NEVER invent quotes.
   - reason_for_deduction: Precise explanation of what was incorrect, incomplete, vague, or missing.
   - improvement_advice: Concrete guidance on what the candidate should understand, include, or do differently.
   - exemplary_example: A strong, technically sound 1-2 sentence model answer addressing that exact gap.
2. FAIR CREDIT FOR ALTERNATIVE VALID APPROACHES:
   If the candidate provides an alternative technically valid paradigm, algorithm, or solution (e.g. iterative instead of recursive, different valid library, or valid architecture), award full credit! Do not penalize a candidate merely because they didn't recite a single canonical textbook wording.
3. STRICT SEPARATION OF CONCERNS:
   - Do NOT reward confident, polished speaking when the technical answer is incorrect.
   - Do NOT penalize technical knowledge solely because communication is weak. If the candidate knows the architecture deeply but rambles or is informal, award high/full marks on technical correctness and take the deduction ONLY in communication clarity!
4. TRANSCRIPTION FAILURES VS KNOWLEDGE FAILURES:
   - Do NOT treat audio dropouts, acoustic glitches, or transcription noise as candidate knowledge failures.
   - If the transcript is corrupted or garbled by audio issues, flag "is_transcription_error": true, do not dock knowledge marks, and advise mic check & retry.
5. NO PENALTY FOR UNASSESSED CRITERIA:
   - If a criterion is not relevant to this interview (e.g., technical correctness for a pure conversational prompt), set max_marks = 0.0 and status = "not_assessed". Never award zero marks for criteria not assessed.
6. ARITHMETIC & FEEDBACK ALIGNMENT:
   - Marks awarded across criteria must sum up to total_marks_awarded.
   - Deductions, strengths, weaknesses, and scores must be completely aligned without contradiction.
7. LEGITIMATE SHORT ANSWERS VS AUDIO GLITCHES:
   - Concise, direct short answers such as "No.", "A stack.", "Reference counting.", or "O(n log n)." are legitimate candidate responses, NOT audio or microphone failures.
   - If a short answer is technically accurate for the question asked (e.g. "A stack." for DFS data structure), award full credit on technical correctness!
   - If a short answer is incomplete or missing explanation, evaluate it fairly on its content; do NOT flag it as an audio glitch unless explicit audio corruption markers are present.
8. VERBATIM EVIDENCE QUOTES:
   - Every "evidence_quote" MUST be an exact verbatim substring from the candidate transcript.
   - NEVER invent or paraphrase candidate words. If pointing out a missing concept, leave evidence_quote null and describe the omitted concept in reason_for_deduction.

RUBRIC CRITERIA TO ASSESS (Default sum: 10.0 Marks):
1. "technical_correctness" (Name: "Technical Correctness & Domain Accuracy", Default Max Marks: 4.0):
   Domain factual accuracy, core architectural mechanisms, correct terminology, absence of technical hallucinations. (Set max_marks: 0.0 if pure conversational interview).
2. "structural_completeness" (Name: "Structural Completeness & Core Concepts", Default Max Marks: 3.0):
   Addresses all parts of the prompt (STAR structure for behavioral; definition + mechanism + edge cases for technical).
3. "communication_clarity" (Name: "Communication Clarity & Articulation", Default Max Marks: 2.0):
   Logical organization, conciseness, articulation. (Evaluated independently of technical accuracy).
4. "evidence_grounding" (Name: "Evidence & Concrete Grounding", Default Max Marks: 1.0):
   Specific examples, metrics, code references, or practical grounding rather than vague buzzwords.

JSON SCHEMA:
{{
  "is_transcription_error": boolean,
  "transcription_error_details": string | null,
  "is_garbled_transcript": boolean,
  "garbled_reason": string | null,
  "rubric_criteria": [
    {{
      "criterion_id": "technical_correctness" | "structural_completeness" | "communication_clarity" | "evidence_grounding",
      "criterion_name": string,
      "max_marks": float,
      "marks_awarded": float,
      "deduction": float,
      "status": "full_credit" | "partial_credit" | "deduction" | "not_assessed",
      "evidence_quote": string | null,
      "reason_for_deduction": string | null,
      "improvement_advice": string | null,
      "exemplary_example": string | null
    }}
  ],
  "total_max_marks": float,
  "total_marks_awarded": float,
  "relevance": float | null,
  "clarity": float | null,
  "structure": float | null,
  "evidence_quality": float | null,
  "completeness": float | null,
  "technical_accuracy": float | null,
  "strengths": [string, ...],
  "areas_to_improve": [string, ...],
  "recommendations": [string, ...],
  "evidence_excerpts": [string, ...],
  "actionable_findings": [
    {{
      "finding": string,
      "supporting_evidence": string,
      "explanation": string,
      "specific_correction": string,
      "example_or_model_answer": string
    }}
  ],
  "competency_evidence": [
    {{
      "competency_id": string,
      "status": "demonstrated" | "partially_demonstrated" | "needs_improvement" | "not_assessed",
      "evidence_type": "direct" | "inferred" | "insufficient",
      "excerpt": string | null,
      "reasoning": string,
      "score": float | null
    }}
  ],
  "evaluation_limitations": [string, ...],
  "overall_quality": float | null
}}
"""

def verify_and_align_evidence_quote(quote: Optional[str], transcript: str) -> Optional[str]:
    """
    Verifies that an evidence quote exists verbatim in the candidate transcript.
    - If verbatim exact/case-insensitive match: returns the exact verbatim transcript slice.
    - If minor edge punctuation / quotes differ: trims and matches verbatim.
    - If slightly paraphrased or altered but contains a substantive verbatim sequence (>= 3 words or all words if < 3),
      extracts the actual verbatim matching sequence from the transcript.
    - If fabricated (cannot be found in transcript): returns None (rejects fabricated quote).
    """
    if not quote or not transcript:
        return None
        
    cleaned_quote = quote.strip().strip('"\'“”`')
    punct_stripped_q = cleaned_quote.strip(" .,;!?:-—\"'()[]{}")
    if not punct_stripped_q:
        return None

    cleaned_transcript = transcript.strip()
    lower_t = cleaned_transcript.lower()
    lower_q = punct_stripped_q.lower()
    
    # 1. Exact case-insensitive substring match (punctuation-stripped)
    idx = lower_t.find(lower_q)
    if idx != -1:
        return cleaned_transcript[idx : idx + len(lower_q)]
            
    # 3. Sub-sequence matching for slightly altered / paraphrased quotations
    q_words = re.findall(r"\b\w+\b", lower_q)
    if not q_words:
        return None
        
    # If quote has 1 or 2 words, check if word exists in transcript
    if len(q_words) <= 2:
        pattern = r"\b" + re.escape(punct_stripped_q.lower()) + r"\b"
        m = re.search(pattern, lower_t)
        if m:
            return cleaned_transcript[m.start():m.end()]
        return None
        
    # For longer quotes, find the longest contiguous sequence of words from the quote that exists in transcript
    best_match = None
    best_len = 0
    
    for start in range(len(q_words)):
        for end in range(len(q_words), start + 1, -1):
            sub_words = q_words[start:end]
            if len(sub_words) < 2:
                continue
            word_regex = r"\b" + r"\b[\s,;!?:.\-—]+\b".join(re.escape(w) for w in sub_words) + r"\b"
            m = re.search(word_regex, lower_t)
            if m:
                match_len = end - start
                if match_len > best_len:
                    best_len = match_len
                    best_match = cleaned_transcript[m.start():m.end()]
                break
                
    # Accept aligned match only if it covers at least 3 words and at least 40% of the quote's words
    if best_match and (best_len >= 3 or best_len == len(q_words)) and (best_len / len(q_words) >= 0.4):
        return best_match
        
    # If quote cannot be found in transcript, it is fabricated
    return None

def _detect_transcription_glitch(transcript: str) -> tuple:
    """
    Detects whether an audio/transcription failure genuinely occurred.
    Returns: (is_glitch, reason_message)
    
    Legitimate short answers (e.g. 'No.', 'A stack.', 'Reference counting.', 'O(n log n).')
    are NOT transcription failures. A short answer may be incomplete or concise, but that
    does not indicate hardware or recording failure.
    
    True glitches include:
    - Empty or pure whitespace recording
    - Explicit audio/transcription error markers ([inaudible], [static], [buzz], [cut out], [corrupted], etc.)
    - Corrupted or unparseable non-lexical audio artifacts (e.g. '...', '???', '###')
    """
    cleaned_t = transcript.strip() if transcript else ""
    if not cleaned_t:
        return True, "No audio or speech input was captured by the microphone."
        
    lower_t = cleaned_t.lower()
    glitch_tokens = [
        "[inaudible]", "[static]", "[buzz]", "[buzzing]", "[cut out]",
        "[cutting out]", "[audio corrupted]", "[corrupted]", "[audio drop]",
        "[dropout]", "[garbled]", "[unclear]", "[screech]", "[distortion]",
        "[silence]", "[silent]", "[recording error]", "[capture failed]"
    ]
    has_glitch_token = any(token in lower_t for token in glitch_tokens)
    if has_glitch_token:
        return True, "Spoken audio contained inaudible fragments, audio dropouts, or transmission noise."
        
    # Check if there are alphanumeric characters
    has_alphanumeric = any(c.isalnum() for c in cleaned_t)
    if not has_alphanumeric:
        return True, "Audio stream contained non-lexical static or corrupted symbols without intelligible speech."
        
    return False, ""

def _detect_inconclusive_filler(transcript: str) -> bool:
    """
    Detects if an answer consists purely of acoustic hesitation noises (e.g. 'uh', 'um')
    with no substantive words. This is NOT a transcription failure, but an inconclusive answer.
    """
    cleaned_t = transcript.strip() if transcript else ""
    words = re.findall(r"\b\w+\b", cleaned_t.lower())
    filler_tokens = {"uh", "um", "ah", "hmm", "er"}
    return len(words) > 0 and all(w in filler_tokens for w in words)

def _clean_and_parse_json(raw_response: str) -> dict:
    """Robustly strips markdown fences, single-line comments, and trailing commas from LLM output."""
    raw = raw_response.strip()
    if "```json" in raw:
        raw = raw.split("```json", 1)[1]
        if "```" in raw:
            raw = raw.split("```", 1)[0]
    elif "```" in raw:
        raw = raw.split("```", 1)[1]
        if "```" in raw:
            raw = raw.split("```", 1)[0]
            
    first_brace = raw.find("{")
    last_brace = raw.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        raw = raw[first_brace:last_brace + 1]
    elif first_brace != -1:
        raw = raw[first_brace:]
        
    # Strip single line JS comments
    raw = re.sub(r'//[^\n\r]*', '', raw)
    # Strip trailing commas
    raw = re.sub(r',\s*([}\]])', r'\1', raw)
    
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        # Fallback repair for trailing truncation
        s = raw.strip()
        # Remove trailing unclosed string or incomplete key/value
        s = re.sub(r',\s*$', '', s)
        open_curlies = s.count("{") - s.count("}")
        open_squares = s.count("[") - s.count("]")
        s += ("]" * max(0, open_squares)) + ("}" * max(0, open_curlies))
        return json.loads(s)

def generate_structured_evaluation(
    question: Question,
    transcript: str,
    interview_type: str,
    level: str,
    assessment_goals: List[str],
    target_competencies: List[Competency]
) -> StructuredEvaluation:
    """Calls the LLM provider to evaluate an answer and strictly parses the output."""
    
    cleaned_t = transcript.strip() if transcript else ""
    is_glitch_detected, glitch_err_msg = _detect_transcription_glitch(transcript)

    # 1. Deterministic guard for genuine hardware/audio transcription failures
    if is_glitch_detected:
        rubric_criteria = [
            RubricCriterionResult(
                criterion_id="technical_correctness",
                criterion_name="Technical Correctness & Domain Accuracy",
                max_marks=0.0,
                marks_awarded=0.0,
                deduction=0.0,
                status="not_assessed",
                evidence_quote=cleaned_t or "[No audible speech]",
                reason_for_deduction=None,
                improvement_advice="Check microphone setup and re-record your answer.",
                exemplary_example="State the core technical definition clearly in complete sentences."
            ),
            RubricCriterionResult(
                criterion_id="structural_completeness",
                criterion_name="Structural Completeness & Core Concepts",
                max_marks=0.0,
                marks_awarded=0.0,
                deduction=0.0,
                status="not_assessed",
                evidence_quote=cleaned_t or "[No audible speech]",
                reason_for_deduction=None,
                improvement_advice="Ensure your answer has a beginning, mechanism, and conclusion.",
                exemplary_example="Structure your answer with definition, mechanism, and real-world example."
            ),
            RubricCriterionResult(
                criterion_id="communication_clarity",
                criterion_name="Communication Clarity & Articulation",
                max_marks=2.0,
                marks_awarded=1.0,
                deduction=1.0,
                status="partial_credit",
                evidence_quote=cleaned_t or "[No audible speech]",
                reason_for_deduction="Audio was inaudible or interrupted by transmission artifacts.",
                improvement_advice="Speak with clear articulation into the microphone at a steady volume.",
                exemplary_example="Deliver your answer steadily into the microphone."
            ),
            RubricCriterionResult(
                criterion_id="evidence_grounding",
                criterion_name="Evidence & Concrete Grounding",
                max_marks=0.0,
                marks_awarded=0.0,
                deduction=0.0,
                status="not_assessed",
                evidence_quote=None,
                reason_for_deduction=None,
                improvement_advice=None,
                exemplary_example=None
            )
        ]

        return StructuredEvaluation(
            evaluation_status="success",
            is_transcription_error=True,
            transcription_error_details=glitch_err_msg,
            is_garbled_transcript=True,
            garbled_reason=glitch_err_msg,
            rubric_criteria=rubric_criteria,
            total_max_marks=2.0,
            total_marks_awarded=1.0,
            relevance=0.0,
            clarity=0.5,
            structure=0.0,
            evidence_quality=0.0,
            completeness=0.0,
            technical_accuracy=None,
            overall_quality=0.5,
            strengths=[],
            areas_to_improve=["Audio input was disrupted by inaudible fragments or transmission noise."],
            recommendations=["Check that your microphone is securely connected and speak clearly into the device."],
            evaluation_limitations=["Audio transcript was inaudible; candidate was not penalized on technical knowledge."],
            actionable_findings=[
                ActionableFinding(
                    finding="Indistinct or Inaudible Audio Input",
                    supporting_evidence=cleaned_t or "[Inaudible Audio]",
                    explanation="The audio transcript contains inaudible fragments or insufficient words to evaluate domain knowledge.",
                    specific_correction="Check that your microphone input volume is adequate and restate your answer.",
                    example_or_model_answer="Start by defining the core principle in your first sentence."
                )
            ],
            competency_evidence=[
                CompetencyEvidenceDetail(
                    competency_id=c.id,
                    status="not_assessed",
                    evidence_type="insufficient",
                    reasoning="Inaudible or distorted audio transcript; competency unassessed without penalty.",
                    score=None
                ) for c in target_competencies
            ]
        )

    # 2. Inconclusive hesitation sounds (pure filler with 0 substantive words)
    if _detect_inconclusive_filler(transcript):
        rubric_criteria = [
            RubricCriterionResult(
                criterion_id="technical_correctness",
                criterion_name="Technical Correctness & Domain Accuracy",
                max_marks=0.0,
                marks_awarded=0.0,
                deduction=0.0,
                status="not_assessed",
                evidence_quote=cleaned_t,
                reason_for_deduction=None,
                improvement_advice="State your answer directly rather than pausing with filler sounds.",
                exemplary_example="State the core principle and mechanisms directly."
            ),
            RubricCriterionResult(
                criterion_id="structural_completeness",
                criterion_name="Structural Completeness & Core Concepts",
                max_marks=0.0,
                marks_awarded=0.0,
                deduction=0.0,
                status="not_assessed",
                evidence_quote=cleaned_t,
                reason_for_deduction=None,
                improvement_advice="Provide a complete response addressing the question.",
                exemplary_example="Structure your answer with a definition and supporting detail."
            ),
            RubricCriterionResult(
                criterion_id="communication_clarity",
                criterion_name="Communication Clarity & Articulation",
                max_marks=2.0,
                marks_awarded=0.5,
                deduction=1.5,
                status="partial_credit",
                evidence_quote=cleaned_t,
                reason_for_deduction="Response contained only hesitation sounds without articulated content.",
                improvement_advice="Take a brief moment to gather your thoughts before answering.",
                exemplary_example="Begin speaking once your initial point is formulated."
            ),
            RubricCriterionResult(
                criterion_id="evidence_grounding",
                criterion_name="Evidence & Concrete Grounding",
                max_marks=0.0,
                marks_awarded=0.0,
                deduction=0.0,
                status="not_assessed",
                evidence_quote=None,
                reason_for_deduction=None,
                improvement_advice=None,
                exemplary_example=None
            )
        ]

        return StructuredEvaluation(
            evaluation_status="success",
            is_transcription_error=False,
            transcription_error_details=None,
            is_garbled_transcript=False,
            garbled_reason="Spoken answer consisted only of hesitation sounds without substantive content.",
            rubric_criteria=rubric_criteria,
            total_max_marks=2.0,
            total_marks_awarded=0.5,
            relevance=0.0,
            clarity=0.25,
            structure=0.0,
            evidence_quality=0.0,
            completeness=0.0,
            technical_accuracy=None,
            overall_quality=0.25,
            strengths=[],
            areas_to_improve=["Response consisted only of hesitation sounds without answering the question."],
            recommendations=["Take a breath, organize your key points, and state your response clearly."],
            evaluation_limitations=["Answer was inconclusive; technical competency marked not_assessed to avoid unfair penalty."],
            actionable_findings=[
                ActionableFinding(
                    finding="Inconclusive Answer / Hesitation Only",
                    supporting_evidence=cleaned_t,
                    explanation="The candidate only spoke filler sounds without addressing the topic.",
                    specific_correction="State the primary definition or answer directly in your first sentence.",
                    example_or_model_answer="Start by defining the core principle directly."
                )
            ],
            competency_evidence=[
                CompetencyEvidenceDetail(
                    competency_id=c.id,
                    status="not_assessed",
                    evidence_type="insufficient",
                    reasoning="Hesitation sounds only; competency marked not_assessed without penalty.",
                    score=None
                ) for c in target_competencies
            ]
        )

    # 2. Format the context
    competency_context = ""
    for comp in target_competencies:
        markers = ", ".join(comp.evidence_markers)
        competency_context += f"- {comp.id} ({comp.name}): {comp.description}\n  Markers: {markers}\n"
        
    prompt = EVALUATION_PROMPT_TEMPLATE.format(
        interview_type=interview_type,
        level=level,
        assessment_goals=", ".join(assessment_goals),
        question_text=question.question_text,
        question_type=question.question_type,
        competency_context=competency_context,
        transcript=transcript
    )
    
    # 3. Call LLM
    try:
        raw_response = call_llm(prompt=prompt, system_prompt="You are a strict, objective, experienced interviewer. Output valid JSON only.")
        
        # 4. Clean and parse JSON
        data = _clean_and_parse_json(raw_response)
        
        # Normalize fields before Pydantic validation
        if isinstance(data, dict):
            if "actionable_findings" in data and isinstance(data["actionable_findings"], list):
                for f in data["actionable_findings"]:
                    if isinstance(f, dict):
                        if f.get("supporting_evidence") is None:
                            f["supporting_evidence"] = ""
            if "rubric_criteria" in data and isinstance(data["rubric_criteria"], list):
                for c in data["rubric_criteria"]:
                    if isinstance(c, dict):
                        if c.get("evidence_quote") is None:
                            c["evidence_quote"] = None
        
        # 5. Validate with Pydantic
        evaluation = StructuredEvaluation(**data)
        
        # 6. Post-processing Arithmetic & Rubric Consistency Enforcer
        # Guarantee default criteria exist if LLM omitted them
        existing_criteria_ids = {c.criterion_id for c in evaluation.rubric_criteria}
        
        is_tech = (interview_type == "technical" or question.question_type == "technical")
        default_criteria_defs = [
            ("technical_correctness", "Technical Correctness & Domain Accuracy", 4.0 if is_tech else 2.0),
            ("structural_completeness", "Structural Completeness & Core Concepts", 3.0),
            ("communication_clarity", "Communication Clarity & Articulation", 2.0),
            ("evidence_grounding", "Evidence & Concrete Grounding", 1.0)
        ]
        
        # If rubric criteria is empty or missing required dimensions, populate them
        if not evaluation.rubric_criteria:
            evaluation.rubric_criteria = []
            for cid, cname, max_m in default_criteria_defs:
                score_factor = 0.5
                if cid == "technical_correctness":
                    score_factor = evaluation.technical_accuracy if evaluation.technical_accuracy is not None else (evaluation.relevance or 0.5)
                elif cid == "structural_completeness":
                    score_factor = evaluation.structure or evaluation.completeness or 0.5
                elif cid == "communication_clarity":
                    score_factor = evaluation.clarity or 0.5
                elif cid == "evidence_grounding":
                    score_factor = evaluation.evidence_quality or 0.5
                
                awarded = round(max_m * score_factor, 1)
                ded = round(max_m - awarded, 1)
                status = "full_credit" if ded <= 0 else ("partial_credit" if awarded > 0 else "deduction")
                
                evaluation.rubric_criteria.append(RubricCriterionResult(
                    criterion_id=cid,
                    criterion_name=cname,
                    max_marks=max_m,
                    marks_awarded=awarded,
                    deduction=ded,
                    status=status,
                    evidence_quote=cleaned_t[:120] if ded > 0 else cleaned_t[:80],
                    reason_for_deduction=f"Deficiencies observed in {cname.lower()}." if ded > 0 else None,
                    improvement_advice=f"Focus on strengthening {cname.lower()} with structured details." if ded > 0 else None,
                    exemplary_example="Provide a clear, direct explanation demonstrating full domain mastery." if ded > 0 else None
                ))
        
        # Enforce exact arithmetic on rubric criteria & verify evidence quotes
        valid_criteria = []
        for c in evaluation.rubric_criteria:
            c.max_marks = max(0.0, float(c.max_marks))
            c.marks_awarded = max(0.0, min(c.max_marks, float(c.marks_awarded)))
            c.deduction = round(max(0.0, c.max_marks - c.marks_awarded), 2)
            
            # Verbatim quote verification and alignment
            if c.evidence_quote:
                verified_q = verify_and_align_evidence_quote(c.evidence_quote, cleaned_t)
                if verified_q:
                    c.evidence_quote = verified_q
                else:
                    logger.warning(f"Discarding fabricated quote for criterion '{c.criterion_id}': '{c.evidence_quote}'")
                    c.evidence_quote = None
                    lim_msg = f"Discarded non-verbatim quote for criterion '{c.criterion_id}'."
                    if lim_msg not in evaluation.evaluation_limitations:
                        evaluation.evaluation_limitations.append(lim_msg)

            if c.max_marks == 0.0:
                c.status = "not_assessed"
                c.deduction = 0.0
            elif c.deduction <= 0.001:
                c.status = "full_credit"
            elif c.marks_awarded > 0.0:
                c.status = "partial_credit"
            else:
                c.status = "deduction"
                
            # Guarantee deductions have reasons, advice, and examples
            if c.deduction > 0 and c.status != "not_assessed":
                if not c.reason_for_deduction:
                    c.reason_for_deduction = f"Answer was incomplete or contained inaccuracies in {c.criterion_name}."
                if not c.improvement_advice:
                    c.improvement_advice = f"State the required mechanisms and details for {c.criterion_name} explicitly."
                if not c.exemplary_example:
                    c.exemplary_example = "State the core principle directly and contrast its mechanisms."
            valid_criteria.append(c)
            
        evaluation.rubric_criteria = valid_criteria
        
        # Verify evidence in actionable findings
        for f in evaluation.actionable_findings:
            if f.supporting_evidence:
                verified_f = verify_and_align_evidence_quote(f.supporting_evidence, cleaned_t)
                if verified_f:
                    f.supporting_evidence = verified_f
                else:
                    f.supporting_evidence = ""

        # Verify evidence in competency details
        for ev in evaluation.competency_evidence:
            if ev.excerpt:
                verified_ev = verify_and_align_evidence_quote(ev.excerpt, cleaned_t)
                if verified_ev:
                    ev.excerpt = verified_ev
                else:
                    ev.excerpt = None

        # Exact arithmetic sum
        assessed_criteria = [c for c in evaluation.rubric_criteria if c.status != "not_assessed"]
        evaluation.total_max_marks = sum(c.max_marks for c in assessed_criteria)
        evaluation.total_marks_awarded = round(sum(c.marks_awarded for c in assessed_criteria), 2)
        
        if evaluation.total_max_marks > 0:
            evaluation.overall_quality = round(evaluation.total_marks_awarded / evaluation.total_max_marks, 2)
        else:
            evaluation.overall_quality = 0.0
            
        # Force bounds on numerical scores
        def bound_score(v):
            if v is None: return None
            return max(0.0, min(1.0, float(v)))
            
        evaluation.relevance = bound_score(evaluation.relevance)
        evaluation.clarity = bound_score(evaluation.clarity)
        evaluation.structure = bound_score(evaluation.structure)
        evaluation.evidence_quality = bound_score(evaluation.evidence_quality)
        evaluation.completeness = bound_score(evaluation.completeness)
        evaluation.technical_accuracy = bound_score(evaluation.technical_accuracy)
        evaluation.overall_quality = bound_score(evaluation.overall_quality)
        for ev in evaluation.competency_evidence:
            ev.score = bound_score(ev.score)
        
        # Synchronize actionable findings with deductions to prevent contradictions
        deducted_criteria = [c for c in assessed_criteria if c.deduction > 0]
        if deducted_criteria and not evaluation.actionable_findings:
            evaluation.actionable_findings = []
            for dc in deducted_criteria[:3]:
                evaluation.actionable_findings.append(ActionableFinding(
                    finding=f"Deduction in {dc.criterion_name} (-{dc.deduction} marks)",
                    supporting_evidence=dc.evidence_quote or cleaned_t[:100],
                    explanation=dc.reason_for_deduction or "Gap observed against target rubric.",
                    specific_correction=dc.improvement_advice or "Address all required rubric dimensions.",
                    example_or_model_answer=dc.exemplary_example or "Provide a comprehensive model response."
                ))
        
        # Set explicit success
        evaluation.evaluation_status = "success"
        
        return evaluation
        
    except (json.JSONDecodeError, ValidationError) as e:
        logger.error(f"Failed to generate structured evaluation (invalid): {e}")
        return StructuredEvaluation(
            evaluation_status="invalid",
            evaluation_limitations=[f"Evaluation engine failed to parse the response: {str(e)}"],
            strengths=[],
            areas_to_improve=[]
        )
    except Exception as e:
        err_str = str(e)
        logger.error(f"Failed to generate structured evaluation (unavailable): {e}")
        
        # Clean user-facing actionable guidance
        err_lower = err_str.lower()
        if "insufficient credits" in err_lower or "never purchased credits" in err_lower:
            clean_reason = "The LLM provider account has exhausted its available credit balance. Please add credits at openrouter.ai or configure a local/alternative provider."
        elif "fewer max_tokens" in err_lower:
            clean_reason = "The evaluation request exceeded the provider's token allocation. Please submit a more concise response or adjust OPENROUTER_MAX_TOKENS."
        elif "rate limit" in err_lower or "429" in err_str:
            clean_reason = "The LLM provider is currently rate-limited. Please wait a moment before submitting your next answer."
        elif "timeout" in err_lower:
            clean_reason = "The request to the AI evaluation service timed out. Please check your network connection and retry."
        elif "invalid api key" in err_lower or "unauthorized" in err_lower or "401" in err_str:
            clean_reason = "The configured LLM provider API key is missing or invalid. Please verify your .env settings."
        elif "connection refused" in err_lower or "11434" in err_str:
            clean_reason = "Local LLM service (Ollama) is not running on port 11434. Please start the Ollama service or switch providers."
        else:
            clean_reason = f"AI evaluation service is temporarily unavailable: {err_str[:140]}"

        return StructuredEvaluation(
            evaluation_status="unavailable",
            evaluation_limitations=[clean_reason],
            strengths=[],
            areas_to_improve=[]
        )

# Backward-compatible alias
evaluate_answer_llm = generate_structured_evaluation

