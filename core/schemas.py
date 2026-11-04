from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# ==========================================
# 1. QUESTION SCHEMA
# ==========================================
class MediaAnalysisResult(BaseModel):
    transcript: str
    duration: float = 0.0
    speech_metrics: Optional[Dict[str, Any]] = None
    language_metrics: Optional[Dict[str, Any]] = None
    visual_metrics: Optional[Dict[str, Any]] = None
    content_analysis: Dict[str, Any] = Field(default_factory=dict)
    media_reference: Optional[str] = None

class Question(BaseModel):
    id: str
    question_text: str
    interview_type: List[str]  # e.g., ["job", "hr", "technical"]
    level: str                 # "beginner", "intermediate", "advanced"
    topic: str
    difficulty: float          # 0.0 to 1.0
    question_type: str         # "behavioral", "technical", "situational", etc.
    competencies: List[str]    # e.g., ["communication_explanation", "problem_solving"]
    follow_up_tags: List[str] = []
    expected_answer_characteristics: List[str] = []
    technical_domain: Optional[str] = None


# ==========================================
# 2. COMPETENCY SCHEMA
# ==========================================
class Competency(BaseModel):
    id: str
    name: str
    category: str
    description: str
    evidence_markers: List[str] = []


# ==========================================
# 3. COMPETENCY COVERAGE SCHEMA
# ==========================================
class CompetencyCoverage(BaseModel):
    competency_id: str
    evidence_found: List[str] = []
    status: str = "not_tested" # "not_tested", "needs_improvement", "partially_demonstrated", "demonstrated"
    score: Optional[float] = None
    findings: List[str] = []

# ==========================================
# 4. INTERVIEW STATE SCHEMA
# ==========================================
class ControllerDecisionLog(BaseModel):
    decision: str
    reason: str

class InterviewState(BaseModel):
    session_id: str
    interview_type: str
    interview_level: str
    assessment_goals: List[str]
    technical_domain: Optional[str] = None
    custom_goal: Optional[str] = None
    current_question_id: Optional[str] = None
    question_history: List[str] = []
    answer_history: List[str] = []
    topics_discussed: List[str] = []
    claims_detected: List[str] = []
    strengths: List[str] = []
    weaknesses: List[str] = []
    competencies_tested: List[str] = []
    competencies_missing: List[str] = []
    current_difficulty: float = 0.5
    interview_progress: float = 0.0
    scores_so_far: Dict[str, float] = {}
    controller_history: List[ControllerDecisionLog] = []
    completion_status: str = "in_progress"  # "in_progress", "completed", "aborted"
    competency_coverage: Dict[str, CompetencyCoverage] = {}


# ==========================================
# 5. ANSWER RECORD & EVALUATION SCHEMAS
# ==========================================
from typing import List, Optional, Dict, Any, Literal

class ActionableFinding(BaseModel):
    finding: str
    supporting_evidence: Optional[str] = ""
    explanation: str
    specific_correction: str
    example_or_model_answer: Optional[str] = None

class RubricCriterionResult(BaseModel):
    criterion_id: str
    criterion_name: str
    max_marks: float
    marks_awarded: float
    deduction: float = 0.0
    status: Literal["full_credit", "partial_credit", "deduction", "not_assessed"] = "full_credit"
    evidence_quote: Optional[str] = None
    reason_for_deduction: Optional[str] = None
    improvement_advice: Optional[str] = None
    exemplary_example: Optional[str] = None

class CompetencyEvidenceDetail(BaseModel):
    competency_id: str
    status: Literal["demonstrated", "partially_demonstrated", "needs_improvement", "not_assessed"] = "not_assessed"
    evidence_type: str = "direct"  # "direct", "inferred", "insufficient"
    excerpt: Optional[str] = None
    reasoning: str
    score: Optional[float] = None

class StructuredEvaluation(BaseModel):
    evaluation_status: Literal["success", "invalid", "unavailable"] = "invalid"
    rubric_criteria: List[RubricCriterionResult] = []
    total_max_marks: float = 10.0
    total_marks_awarded: float = 0.0
    relevance: Optional[float] = None
    clarity: Optional[float] = None
    structure: Optional[float] = None
    evidence_quality: Optional[float] = None
    completeness: Optional[float] = None
    technical_accuracy: Optional[float] = None
    strengths: List[str] = []
    areas_to_improve: List[str] = []
    recommendations: List[str] = []
    evidence_excerpts: List[str] = []
    competency_evidence: List[CompetencyEvidenceDetail] = []
    actionable_findings: List[ActionableFinding] = []
    evaluation_limitations: List[str] = []
    overall_quality: Optional[float] = None
    is_garbled_transcript: bool = False
    garbled_reason: Optional[str] = None
    is_transcription_error: bool = False
    transcription_error_details: Optional[str] = None

class AnswerRecord(BaseModel):
    answer_id: str
    session_id: str
    question_id: str
    media_reference: str
    transcript: str
    duration: float
    speech_metrics: Dict[str, Any] = {}
    language_metrics: Dict[str, Any] = {}
    visual_metrics: Dict[str, Any] = {}
    content_analysis: Dict[str, Any] = {} # Legacy
    structured_evaluation: Optional[StructuredEvaluation] = None
    rubric_criteria: List[RubricCriterionResult] = []
    total_max_marks: float = 10.0
    total_marks_awarded: float = 0.0
    actionable_findings: List[ActionableFinding] = []
    detected_strengths: List[str] = []
    detected_weaknesses: List[str] = []
    recommendations: List[str] = []
    detected_topics: List[str] = []
    detected_claims: List[str] = []
    competency_evidence: Dict[str, Any] = {}
    overall_answer_quality: Optional[float] = None
    is_revision: bool = False
    revision_target_answer_id: Optional[str] = None


# ==========================================
# 5. NEXT QUESTION DECISION SCHEMA
# ==========================================
class NextQuestionDecision(BaseModel):
    next_question_id: Optional[str] = None
    decision_type: str         # "deeper_probe", "clarification", "new_topic", "finalize"
    reason: str
    target_competencies: List[str] = []
    target_topic: Optional[str] = None
    difficulty_change: float = 0.0
    priority: float = 1.0
