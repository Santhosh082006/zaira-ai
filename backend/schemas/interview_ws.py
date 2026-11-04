from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Union, List

# ---------------------------------------------------------
# SHARED MODELS (Borrowed from REST schemas for consistency)
# ---------------------------------------------------------
class WSQuestionModel(BaseModel):
    id: str
    question_text: str
    question_type: str
    difficulty: float
    topics: List[str]

class WSDecisionModel(BaseModel):
    decision_type: str
    reason: str
    next_question_id: Optional[str] = None


# ---------------------------------------------------------
# CLIENT -> SERVER EVENTS
# ---------------------------------------------------------
class WSClientSubmitAnswer(BaseModel):
    type: str = "submit_answer"
    question_id: str
    transcript: str
    duration: float = 0.0
    media_reference: Optional[str] = None
    speech_metrics: Optional[Dict[str, float]] = None
    language_metrics: Optional[Dict[str, float]] = None
    visual_metrics: Optional[Dict[str, float]] = None
class WSClientLiveTranscriptUpdate(BaseModel):
    type: str = "live_transcript_update"
    question_id: str
    transcript: str
    duration: float = 0.0
    is_final: bool = False

class WSClientGetState(BaseModel):
    type: str = "get_state"

# ---------------------------------------------------------
# SERVER -> CLIENT EVENTS
# ---------------------------------------------------------
class WSServerLiveFeedback(BaseModel):
    type: str = "live_feedback"
    question_id: str
    word_count: int
    concepts_covered: List[str] = []
    concepts_missing: List[str] = []
    pacing_status: str = "good"
    coaching_hint: str = ""
    is_provisional: bool = True
class WSServerConnected(BaseModel):
    type: str = "connected"
    session_id: str

class WSServerQuestionReady(BaseModel):
    type: str = "question_ready"
    question: WSQuestionModel

class WSServerProcessing(BaseModel):
    type: str = "processing"
    stage: str
    progress: int

class WSServerAnswerResult(BaseModel):
    type: str = "answer_result"
    answer_id: str
    question_id: str
    next_question: Optional[WSQuestionModel] = None
    decision: str
    decision_reason: str
    interview_progress: float
    completion_status: str

class WSServerInterviewCompleted(BaseModel):
    type: str = "interview_completed"
    reason: str

class WSServerError(BaseModel):
    type: str = "error"
    code: str
    message: str

class WSServerState(BaseModel):
    type: str = "state"
    session_id: str
    completion_status: str
    current_question_id: Optional[str] = None
    interview_progress: float
    competency_coverage_status: Dict[str, str]
