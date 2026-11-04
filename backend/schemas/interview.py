from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class StartInterviewRequest(BaseModel):
    interview_type: str
    interview_level: str
    assessment_goals: List[str]
    technical_domain: Optional[str] = None
    custom_goal: Optional[str] = None

class QuestionModel(BaseModel):
    id: str
    question_text: str
    question_type: str
    difficulty: float
    topics: List[str]

class StartInterviewResponse(BaseModel):
    session_id: str
    current_question: Optional[QuestionModel] = None
    interview_type: str
    interview_level: str
    assessment_goals: List[str]
    technical_domain: Optional[str] = None
    custom_goal: Optional[str] = None
    completion_status: str
    interview_progress: float

class AnswerSubmissionRequest(BaseModel):
    session_id: str
    question_id: str
    transcript: str
    duration: float = 0.0
    media_reference: str = ""
    # Raw metrics processed elsewhere, but accepted here for pure integration
    content_analysis: Dict[str, Any] = Field(default_factory=dict)
    speech_metrics: Optional[Dict[str, float]] = None
    visual_metrics: Optional[Dict[str, float]] = None
    language_metrics: Optional[Dict[str, float]] = None

class NextQuestionDecisionModel(BaseModel):
    decision_type: str
    reason: str
    next_question_id: Optional[str] = None

class ActionableFindingModel(BaseModel):
    finding: str
    supporting_evidence: Optional[str] = ""
    explanation: str
    specific_correction: str
    example_or_model_answer: Optional[str] = None

class RubricCriterionModel(BaseModel):
    criterion_id: str
    criterion_name: str
    max_marks: float
    marks_awarded: float
    deduction: float = 0.0
    status: str = "evaluated"  # "full_credit", "partial_credit", "deduction", "not_assessed"
    evidence_quote: Optional[str] = None
    reason_for_deduction: Optional[str] = None
    improvement_advice: Optional[str] = None
    exemplary_example: Optional[str] = None

class CompetencyEvidenceItem(BaseModel):
    competency_id: str
    competency_name: Optional[str] = None
    status: Optional[str] = "not_assessed"
    evidence_type: str = "direct"  # "direct", "inferred", "insufficient"
    excerpt: Optional[str] = None
    reasoning: str
    score: Optional[float] = None

class StructuredEvaluationModel(BaseModel):
    evaluation_status: str = "success"
    overall_quality: Optional[float] = None
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
    competency_evidence: List[CompetencyEvidenceItem] = []
    actionable_findings: List[ActionableFindingModel] = []
    rubric_criteria: List[RubricCriterionModel] = []
    total_max_marks: float = 10.0
    total_marks_awarded: float = 0.0
    is_transcription_error: bool = False
    transcription_error_details: Optional[str] = None
    evaluation_limitations: List[str] = []
    is_garbled_transcript: bool = False
    garbled_reason: Optional[str] = None

class AnswerSubmissionResponse(BaseModel):
    session_id: str
    answer_id: str
    processed_question_id: str
    next_question: Optional[QuestionModel] = None
    decision: NextQuestionDecisionModel
    interview_progress: float
    completion_status: str
    competency_coverage_status: Dict[str, str]  # Map of competency_id -> status
    language_metrics: Optional[Dict[str, float]] = None
    speech_metrics: Optional[Dict[str, Any]] = None
    visual_metrics: Optional[Dict[str, Any]] = None
    transcript: str
    overall_answer_quality: Optional[float] = None
    detected_strengths: List[str] = []
    detected_weaknesses: List[str] = []
    detected_topics: List[str] = []
    recommendations: List[str] = []
    structured_evaluation: Optional[StructuredEvaluationModel] = None
    actionable_findings: List[ActionableFindingModel] = []
    rubric_criteria: List[RubricCriterionModel] = []
    total_max_marks: float = 10.0
    total_marks_awarded: float = 0.0
    is_transcription_error: bool = False
    transcription_error_details: Optional[str] = None
    is_revision: bool = False
    revision_delta: Optional[Dict[str, Any]] = None

class AvatarTokenResponse(BaseModel):
    available: bool
    provider: str
    token: Optional[str] = None
    message: Optional[str] = None

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "en-US-AvaNeural"

class RetryAnswerRequest(BaseModel):
    session_id: str
    question_id: str

class RetryAnswerResponse(BaseModel):
    session_id: str
    question: QuestionModel
    previous_answer_id: Optional[str] = None
    previous_score: Optional[float] = None
    message: str
