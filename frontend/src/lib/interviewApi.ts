import axios from "axios";
import { getApiBase } from "./apiConfig";

export interface InterviewStartRequest {
  interview_type: string;
  interview_level: string;
  assessment_goals: string[];
  technical_domain?: string | null;
  custom_goal?: string | null;
  resume_text?: string | null;
  job_description?: string | null;
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
  resume_text?: string | null;
  job_description?: string | null;
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

const getInterviewApiBase = () => `${getApiBase()}/api/interview`;

export const startInterview = async (req: InterviewStartRequest): Promise<InterviewStartResponse> => {
  const res = await axios.post(`${getInterviewApiBase()}/start`, req);
  return res.data;
};

export const submitAnswerRest = async (req: AnswerSubmission): Promise<AnswerSubmissionResponse> => {
  const res = await axios.post(`${getInterviewApiBase()}/answer`, req);
  return res.data;
};

export const getInterviewState = async (sessionId: string): Promise<InterviewState> => {
  const res = await axios.get(`${getInterviewApiBase()}/state/${sessionId}`);
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

  const res = await axios.post(`${getInterviewApiBase()}/${sessionId}/answer/media`, formData, {
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
  session_id?: string | null;
  avatar_id?: string | null;
  voice_id?: string | null;
  message?: string | null;
}

export const getAvatarSessionToken = async (): Promise<AvatarTokenResponse> => {
  try {
    const res = await axios.post(`${getInterviewApiBase()}/avatar/token`);
    return res.data;
  } catch (err: unknown) {
    return {
      available: false,
      provider: "heygen",
      message: err instanceof Error ? err.message : "Failed to connect to avatar token endpoint",
    };
  }
};

export interface PcmAudioResponse {
  status: string;
  format: string;
  sample_rate: number;
  channels: number;
  duration_sec: number;
  total_bytes: number;
  chunks: string[];
}

export const fetchQuestionPcmAudio = async (
  text: string,
  voice: string = "en-US-AvaNeural",
  rate: string = "-3%"
): Promise<PcmAudioResponse | null> => {
  try {
    const res = await axios.post(`${getInterviewApiBase()}/tts`, {
      text,
      voice,
      rate,
      conversational_flow: true,
      audio_format: "pcm24k",
    });
    return res.data as PcmAudioResponse;
  } catch (err: unknown) {
    console.warn("PCM audio fetch error:", err);
    return null;
  }
};

export interface TimedAudioResponse {
  audioBlob: Blob;
  wordTimings: Array<{ word: string; offset_ms: number; duration_ms: number }>;
  spokenText: string;
}

export const fetchQuestionTimedAudio = async (
  text: string,
  voice: string = "en-US-AvaNeural",
  rate: string = "-3%"
): Promise<TimedAudioResponse | null> => {
  try {
    const res = await axios.post(
      `${getInterviewApiBase()}/tts`,
      { text, voice, rate, conversational_flow: true, audio_format: "mp3_timings" },
      { timeout: 15000 }
    );
    const data = res.data;
    if (!data || !data.audio_base64) return null;
    const binary = atob(data.audio_base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i);
    }
    return {
      audioBlob: new Blob([bytes], { type: data.mime_type || "audio/mpeg" }),
      wordTimings: Array.isArray(data.word_timings) ? data.word_timings : [],
      spokenText: data.spoken_text || text,
    };
  } catch (err: unknown) {
    console.warn("Timed TTS audio fetch failed, falling back to plain MP3/SpeechSynthesis:", err);
    return null;
  }
};

export const fetchQuestionAudio = async (
  text: string,
  voice: string = "en-US-AvaNeural",
  rate: string = "-3%"
): Promise<Blob | null> => {
  try {
    const res = await axios.post(
      `${getInterviewApiBase()}/tts`,
      { text, voice, rate, conversational_flow: true },
      { responseType: "blob", timeout: 12000 }
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
  const res = await axios.post(`${getInterviewApiBase()}/retry`, {
    session_id: sessionId,
    question_id: questionId,
  });
  return res.data;
};

export interface CompetencyReportItem {
  id: string;
  name: string;
  category: string;
  status: string;
  score: number;
  evidence_count: number;
  evidence_found?: string[];
  findings?: string[];
}

export interface AggregateTelemetry {
  avg_wpm: number | null;
  total_speaking_time_sec: number;
  avg_face_presence_pct: number | null;
  avg_pause_duration_sec: number | null;
  total_questions_answered: number;
}

export interface QuestionAuditItem {
  question_number: number;
  question_id: string;
  question_text: string;
  question_type: string;
  transcript: string;
  score: number;
  total_marks_awarded: number;
  total_max_marks: number;
  duration_sec: number;
  wpm: number | null;
  rubric_criteria: RubricCriterion[];
  strengths: string[];
  weaknesses: string[];
  actionable_findings: ActionableFinding[];
}

export interface InterviewReport {
  session_id: string;
  interview_type: string;
  interview_level: string;
  technical_domain?: string | null;
  custom_goal?: string | null;
  overall_score: number;
  performance_level: string;
  summary_assessment: string;
  completion_status: string;
  aggregate_telemetry: AggregateTelemetry;
  competency_breakdown: CompetencyReportItem[];
  strengths: string[];
  growth_targets: string[];
  questions_audit: QuestionAuditItem[];
}

export const fetchInterviewReport = async (sessionId: string): Promise<InterviewReport> => {
  const res = await axios.get(`${getInterviewApiBase()}/${sessionId}/report`);
  return res.data as InterviewReport;
};

export interface ResumeParseResult {
  success: boolean;
  filename: string;
  text: string;
  word_count: number;
  char_count: number;
  page_count: number;
  error?: string | null;
}

export const parseResumeFile = async (file: File): Promise<ResumeParseResult> => {
  const formData = new FormData();
  formData.append("file", file);
  const res = await axios.post(`${getInterviewApiBase()}/parse-resume`, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return res.data;
};
