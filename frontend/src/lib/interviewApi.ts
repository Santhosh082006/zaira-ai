import axios from "axios";

export interface InterviewStartRequest {
  interview_type: string;
  interview_level: string;
  assessment_goals: string[];
  technical_domain?: string | null;
  custom_goal?: string | null;
}

export interface Question {
  id: string;
  question_text: string;
  question_type: string;
  difficulty: number;
  topics: string[];
}

export interface InterviewStartResponse {
  session_id: string;
  current_question: Question | null;
  interview_type: string;
  interview_level: string;
  assessment_goals: string[];
  technical_domain: string | null;
  custom_goal?: string | null;
  completion_status: string;
  interview_progress: number;
}

export interface AnswerSubmission {
  session_id: string;
  question_id: string;
  transcript: string;
  content_analysis?: Record<string, unknown>;
  speech_metrics?: Record<string, number>;
  visual_metrics?: Record<string, number>;
  language_metrics?: Record<string, number>;
  duration?: number;
  media_reference?: string;
}

export interface AnswerRecord {
  answer_id: string;
  session_id: string;
  question_id: string;
  transcript: string;
  overall_answer_quality: number | null;
}

export interface ActionableFinding {
  finding: string;
  supporting_evidence: string;
  explanation: string;
  specific_correction: string;
  example_or_model_answer?: string;
}

export interface RubricCriterion {
  criterion_id: string;
  criterion_name: string;
  max_marks: number;
  marks_awarded: number;
  deduction: number;
  status: "full_credit" | "partial_credit" | "deduction" | "not_assessed" | string;
  evidence_quote?: string | null;
  reason_for_deduction?: string | null;
  improvement_advice?: string | null;
  exemplary_example?: string | null;
}

export interface RevisionDelta {
  original_answer_id: string;
  revised_answer_id: string;
  overall_quality_delta_pts: number;
  dimensional_deltas: Record<string, number>;
  new_strengths: string[];
  resolved_weaknesses: string[];
  wpm_delta: number;
  original_score: number;
  revised_score: number;
  is_improved: boolean;
}

export interface CompetencyEvidenceItem {
  competency_id: string;
  competency_name?: string;
  status?: "demonstrated" | "partially_demonstrated" | "needs_improvement" | "not_assessed" | string;
  evidence_type: "direct" | "inferred" | "insufficient" | string;
  excerpt: string | null;
  reasoning: string;
  score?: number | null;
}

export interface StructuredEvaluationData {
  evaluation_status: "success" | "invalid" | "unavailable" | string;
  overall_quality: number | null;
  relevance: number | null;
  clarity: number | null;
  structure: number | null;
  evidence_quality: number | null;
  completeness: number | null;
  technical_accuracy: number | null;
  strengths: string[];
  areas_to_improve: string[];
  recommendations?: string[];
  evidence_excerpts: string[];
  competency_evidence: CompetencyEvidenceItem[];
  actionable_findings?: ActionableFinding[];
  rubric_criteria?: RubricCriterion[];
  total_max_marks?: number;
  total_marks_awarded?: number;
  is_transcription_error?: boolean;
  transcription_error_details?: string | null;
  evaluation_limitations: string[];
  is_garbled_transcript?: boolean;
  garbled_reason?: string | null;
}

export interface AnswerSubmissionResponse {
  session_id: string;
  answer_id: string;
  processed_question_id: string;
  next_question: Question | null;
  completion_status: string;
  transcript: string;
  overall_answer_quality: number | null;
  detected_strengths: string[];
  detected_weaknesses: string[];
  detected_topics: string[];
  recommendations?: string[];
  structured_evaluation?: StructuredEvaluationData | null;
  actionable_findings?: ActionableFinding[];
  rubric_criteria?: RubricCriterion[];
  total_max_marks?: number;
  total_marks_awarded?: number;
  is_transcription_error?: boolean;
  transcription_error_details?: string | null;
  is_revision?: boolean;
  revision_delta?: RevisionDelta | null;
  speech_metrics?: Record<string, any>;
  visual_metrics?: Record<string, any>;
  language_metrics?: Record<string, any>;
  interview_progress?: number;
  decision: {
    decision_type: string;
    reason: string;
  };
}

export interface InterviewState {
  session_id: string;
  interview_type: string;
  interview_level: string;
  assessment_goals: string[];
  technical_domain: string | null;
  current_question_id: string | null;
  answer_history: string[];
  status: string; // e.g., 'in_progress', 'completed'
}

const getApiBase = () => {
  if (process.env.NEXT_PUBLIC_API_URL) return `${process.env.NEXT_PUBLIC_API_URL}/interview`;
  if (typeof window !== "undefined") {
    const host = window.location.hostname || "127.0.0.1";
    return `http://${host}:8000/api/interview`;
  }
  return "http://127.0.0.1:8000/api/interview";
};

export const startInterview = async (req: InterviewStartRequest): Promise<InterviewStartResponse> => {
  const res = await axios.post(`${getApiBase()}/start`, req);
  return res.data;
};

export const submitAnswerRest = async (req: AnswerSubmission): Promise<AnswerSubmissionResponse> => {
  const res = await axios.post(`${getApiBase()}/answer`, req);
  return res.data;
};

export const getInterviewState = async (sessionId: string): Promise<InterviewState> => {
  const res = await axios.get(`${getApiBase()}/state/${sessionId}`);
  return res.data;
};

export const submitMediaAnswerRest = async (
  sessionId: string,
  questionId: string,
  file: Blob,
  filename: string = "audio.webm"
): Promise<AnswerSubmissionResponse> => {
  const formData = new FormData();
  formData.append("question_id", questionId);
  formData.append("file", file, filename);

  const res = await axios.post(`${getApiBase()}/${sessionId}/answer/media`, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return res.data;
};

export interface AvatarTokenResponse {
  available: boolean;
  provider: string;
  token?: string | null;
  message?: string | null;
}

export const getAvatarSessionToken = async (): Promise<AvatarTokenResponse> => {
  try {
    const res = await axios.post(`${getApiBase()}/avatar/token`);
    return res.data;
  } catch (err: unknown) {
    return {
      available: false,
      provider: "heygen",
      message: err instanceof Error ? err.message : "Failed to connect to avatar token endpoint",
    };
  }
};

export const fetchQuestionAudio = async (text: string): Promise<Blob | null> => {
  try {
    const res = await axios.post(
      `${getApiBase()}/tts`,
      { text },
      { responseType: "blob", timeout: 8000 }
    );
    return res.data as Blob;
  } catch (err: unknown) {
    console.warn("TTS audio fetch failed, falling back to browser SpeechSynthesis:", err);
    return null;
  }
};

export interface RetryAnswerResponse {
  session_id: string;
  question: Question;
  previous_answer_id?: string | null;
  previous_score?: number | null;
  message: string;
}

export const retryAnswerRest = async (
  sessionId: string,
  questionId: string
): Promise<RetryAnswerResponse> => {
  const res = await axios.post(`${getApiBase()}/retry`, {
    session_id: sessionId,
    question_id: questionId,
  });
  return res.data;
};
