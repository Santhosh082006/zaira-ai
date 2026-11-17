"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  startInterview,
  InterviewStartRequest,
  Question,
  AnswerSubmissionResponse,
  submitMediaAnswerRest,
  submitAnswerRest,
  retryAnswerRest,
} from "../lib/interviewApi";
import { InterviewWebSocketClient, WebSocketServerEvent } from "../lib/interviewWebSocket";
import {
  InterviewTypeOption,
  InterviewLevelOption,
} from "../components/interview/InterviewConfig";
import { LiveFeedbackData } from "../components/AudioRecorder";

export type InterviewAppState =
  | "CONFIG"
  | "READY"
  | "PROCESSING"
  | "ANSWER_RESULT"
  | "COMPLETED"
  | "ERROR"
  | "EVAL_ERROR";

export interface EvalStreamingState {
  isEvaluating: boolean;
  stage: string;
  message: string;
  progress: number;
  thoughtTrace: string;
}

export function useInterviewSession() {
  const [appState, setAppState] = useState<InterviewAppState>("CONFIG");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [lastAnswerResult, setLastAnswerResult] = useState<AnswerSubmissionResponse | null>(null);
  const [isRetrying, setIsRetrying] = useState<boolean>(false);
  const [liveFeedback, setLiveFeedback] = useState<LiveFeedbackData | null>(null);

  // Streaming Evaluation Feedback State
  const [evalStreaming, setEvalStreaming] = useState<EvalStreamingState>({
    isEvaluating: false,
    stage: "idle",
    message: "",
    progress: 0,
    thoughtTrace: "",
  });

  // Configuration State
  const [interviewType, setInterviewType] = useState<InterviewTypeOption>("job");
  const [technicalDomain, setTechnicalDomain] = useState<string>("Python");
  const [customGoal, setCustomGoal] = useState<string>("");
  const [resumeText, setResumeText] = useState<string>("");
  const [jobDescription, setJobDescription] = useState<string>("");
  const [interviewLevel, setInterviewLevel] = useState<InterviewLevelOption>("intermediate");
  const [assessmentGoals, setAssessmentGoals] = useState<string[]>(["COMMUNICATION", "PERFORMANCE"]);

  // WebSocket reference
  const wsClientRef = useRef<InterviewWebSocketClient | null>(null);

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsClientRef.current) {
        wsClientRef.current.disconnect();
        wsClientRef.current = null;
      }
    };
  }, []);

  const toggleGoal = useCallback((goalId: string) => {
    setAssessmentGoals((prev) => {
      if (prev.includes(goalId)) {
        if (prev.length === 1) return prev; // Keep at least one goal
        return prev.filter((g) => g !== goalId);
      } else {
        return [...prev, goalId];
      }
    });
  }, []);

  const handleWsMessage = useCallback((event: WebSocketServerEvent) => {
    switch (event.type) {
      case "connected":
        setAppState("READY");
        break;
      case "question_ready": {
        const question = event.question ?? event.payload?.question;
        if (
          question &&
          typeof question === "object" &&
          typeof question.id === "string" &&
          typeof question.question_text === "string"
        ) {
          setCurrentQuestion(question);
          setAppState("READY");
        } else {
          setErrorMsg("Received invalid question data from server.");
          setAppState("ERROR");
        }
        break;
      }
      case "processing": {
        const stage = event.stage ?? event.payload?.stage ?? "evaluating";
        const progress = event.progress ?? event.payload?.progress ?? 50;
        const msg = event.message ?? event.payload?.message ?? "";
        setAppState("PROCESSING");
        setEvalStreaming((prev) => ({
          ...prev,
          isEvaluating: true,
          stage,
          message:
            msg ||
            (stage === "transcribing"
              ? "Transcribing speech and extracting acoustic telemetry with Whisper..."
              : stage === "telemetry"
              ? "Synthesizing facial gaze, speaking cadence, and vocal pitch..."
              : stage === "evaluating_rubric"
              ? "Evaluating answer against technical, structural, and communication rubrics..."
              : stage === "selecting_next_question"
              ? "Compiling rubric scorecard and selecting adaptive follow-up..."
              : "Evaluating candidate response..."),
          progress,
        }));
        break;
      }
      case "eval_stream_chunk": {
        const chunk = event.chunk ?? event.payload?.chunk ?? "";
        const progress = event.progress ?? event.payload?.progress ?? 75;
        const stage = event.stage ?? event.payload?.stage ?? "reasoning";
        setAppState("PROCESSING");
        setEvalStreaming((prev) => ({
          ...prev,
          isEvaluating: true,
          stage,
          progress,
          thoughtTrace: prev.thoughtTrace + chunk,
        }));
        break;
      }
      case "answer_result": {
        setEvalStreaming((prev) => ({
          ...prev,
          isEvaluating: false,
          progress: 100,
        }));
        const completionStatus = event.completion_status ?? event.payload?.completion_status;
        const nextQuestion = event.next_question ?? event.payload?.next_question;
        if (completionStatus === "completed") {
          setAppState("COMPLETED");
        } else if (nextQuestion && typeof nextQuestion === "object" && typeof nextQuestion.id === "string") {
          setCurrentQuestion(nextQuestion);
          setAppState("READY");
        } else if (completionStatus === "in_progress" && !nextQuestion) {
          setErrorMsg("Interview in progress but no next question received.");
          setAppState("ERROR");
        }
        break;
      }
      case "live_feedback": {
        setLiveFeedback({
          word_count: event.word_count,
          concepts_covered: event.concepts_covered,
          concepts_missing: event.concepts_missing,
          pacing_status: event.pacing_status,
          coaching_hint: event.coaching_hint,
        });
        break;
      }
      case "interview_completed":
        setEvalStreaming((prev) => ({ ...prev, isEvaluating: false, progress: 100 }));
        setAppState("COMPLETED");
        break;
      case "error": {
        setEvalStreaming((prev) => ({ ...prev, isEvaluating: false }));
        const message = event.message ?? event.payload?.message;
        setErrorMsg(typeof message === "string" && message ? message : "Server error occurred");
        setAppState("ERROR");
        break;
      }
      default:
        console.warn("Unknown WS event", event);
    }
  }, []);

  const startSession = useCallback(
    async (onBeforeStart?: () => void) => {
      // Unlock browser AudioContext during user gesture
      if (typeof window !== "undefined") {
        const AudioCtx =
          window.AudioContext ||
          (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        if (AudioCtx) {
          new AudioCtx().resume().catch(() => {});
        }
        try {
          const primeAudio = new Audio();
          primeAudio.src =
            "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA";
          primeAudio.volume = 0.01;
          primeAudio.play().catch(() => {});
        } catch {
          // ignore
        }
      }

      if (onBeforeStart) onBeforeStart();
      setAppState("PROCESSING");
      setErrorMsg(null);
      setLiveFeedback(null);

      try {
        const req: InterviewStartRequest = {
          interview_type: interviewType,
          interview_level: interviewLevel,
          assessment_goals: assessmentGoals.length > 0 ? assessmentGoals : ["COMMUNICATION"],
          technical_domain: interviewType === "technical" ? technicalDomain : null,
          custom_goal: interviewType === "custom" && customGoal.trim() ? customGoal.trim() : null,
          resume_text: resumeText.trim() ? resumeText.trim() : null,
          job_description: jobDescription.trim() ? jobDescription.trim() : null,
        };

        const res = await startInterview(req);
        setSessionId(res.session_id);
        setCurrentQuestion(res.current_question);

        // Connect WebSocket for updates
        const client = new InterviewWebSocketClient(
          res.session_id,
          handleWsMessage,
          (err) => {
            setErrorMsg(err);
            setAppState("ERROR");
          },
          () => {
            console.log("WS Closed");
          }
        );

        wsClientRef.current = client;
        client.connect();
      } catch (err: unknown) {
        if (err instanceof Error) {
          setErrorMsg(err.message);
        } else {
          setErrorMsg("Failed to start interview");
        }
        setAppState("ERROR");
      }
    },
    [interviewType, interviewLevel, assessmentGoals, technicalDomain, customGoal, resumeText, jobDescription, handleWsMessage]
  );

  const submitAudioAnswer = useCallback(
    async (mediaBlob: Blob, onBeforeSubmit?: () => void) => {
      if (!sessionId || !currentQuestion) return;

      if (onBeforeSubmit) onBeforeSubmit();
      setAppState("PROCESSING");
      setErrorMsg(null);
      setEvalStreaming({
        isEvaluating: true,
        stage: "transcribing",
        message: "Transcribing speech and extracting acoustic telemetry with Whisper...",
        progress: 15,
        thoughtTrace: "",
      });

      try {
        let ext = "webm";
        if (mediaBlob.type.includes("mp4")) ext = "mp4";
        if (mediaBlob.type.includes("ogg")) ext = "ogg";

        const result = await submitMediaAnswerRest(
          sessionId,
          currentQuestion.id,
          mediaBlob,
          `answer.${ext}`
        );

        if (result.decision.decision_type.startsWith("evaluation_")) {
          setLastAnswerResult(result);
          setErrorMsg(
            result.decision.reason ||
              "The AI evaluation service is currently unavailable. Your answer transcript has been saved."
          );
          setAppState("EVAL_ERROR");
          return;
        }

        setLastAnswerResult(result);
        setAppState("ANSWER_RESULT");
      } catch (err: unknown) {
        const errorResponse = err as { response?: { status?: number; data?: { detail?: string } } };
        let errorDetail = errorResponse.response?.data?.detail;
        if (!errorDetail) {
          if (errorResponse.response?.status === 404) {
            errorDetail = "Interview session not found.";
          } else if (errorResponse.response?.status === 409) {
            errorDetail = "This answer has already been processed or the question is no longer active.";
          } else if (errorResponse.response?.status === 422) {
            errorDetail = "No clear speech detected in your recording. Please speak clearly into your microphone and try again.";
          } else {
            errorDetail = "Something went wrong while analyzing your answer. Please try again.";
          }
        }
        setErrorMsg(errorDetail);
        setAppState("ERROR");
      }
    },
    [sessionId, currentQuestion]
  );

  const retryAnalysis = useCallback(async () => {
    if (!sessionId || !currentQuestion || !lastAnswerResult) return;

    setAppState("PROCESSING");
    setErrorMsg(null);
    setEvalStreaming({
      isEvaluating: true,
      stage: "evaluating_rubric",
      message: "Re-evaluating transcript against rubric criteria...",
      progress: 30,
      thoughtTrace: "",
    });

    try {
      const result = await submitAnswerRest({
        session_id: sessionId,
        question_id: currentQuestion.id,
        transcript: lastAnswerResult.transcript,
      });

      if (result.decision.decision_type.startsWith("evaluation_")) {
        setLastAnswerResult(result);
        setErrorMsg(result.decision.reason || "The AI evaluation service is still unavailable.");
        setAppState("EVAL_ERROR");
        return;
      }

      setLastAnswerResult(result);
      setAppState("ANSWER_RESULT");
    } catch {
      setErrorMsg("Something went wrong while retrying the evaluation. Please try again.");
      setAppState("ERROR");
    }
  }, [sessionId, currentQuestion, lastAnswerResult]);

  const retryQuestion = useCallback(
    async (onRetrySuccess?: () => void) => {
      if (!sessionId || !currentQuestion) return;
      try {
        setIsRetrying(true);
        setErrorMsg(null);
        const res = await retryAnswerRest(sessionId, currentQuestion.id);
        setCurrentQuestion(res.question);
        if (onRetrySuccess) onRetrySuccess();
        setAppState("READY");
      } catch (err: unknown) {
        console.error("Retry preparation failed:", err);
        setErrorMsg("Failed to prepare retry. Please proceed to the next question.");
      } finally {
        setIsRetrying(false);
      }
    },
    [sessionId, currentQuestion]
  );

  const proceedToNext = useCallback(
    (onNextQuestion?: () => void) => {
      if (!lastAnswerResult) return;
      if (lastAnswerResult.completion_status === "completed") {
        setAppState("COMPLETED");
      } else if (lastAnswerResult.next_question) {
        if (onNextQuestion) onNextQuestion();
        setCurrentQuestion(lastAnswerResult.next_question);
        setAppState("READY");
      }
    },
    [lastAnswerResult]
  );

  const sendLiveTranscript = useCallback(
    (transcript: string, isFinal: boolean) => {
      if (wsClientRef.current && currentQuestion) {
        wsClientRef.current.sendLiveTranscriptUpdate({
          question_id: currentQuestion.id,
          transcript,
          is_final: isFinal,
        });
      }
    },
    [currentQuestion]
  );

  const resetSession = useCallback((onReset?: () => void) => {
    if (wsClientRef.current) {
      wsClientRef.current.disconnect();
      wsClientRef.current = null;
    }
    if (onReset) onReset();
    setSessionId(null);
    setCurrentQuestion(null);
    setErrorMsg(null);
    setLiveFeedback(null);
    setLastAnswerResult(null);
    setAppState("CONFIG");
  }, []);

  const retryCurrentQuestion = useCallback(() => {
    setAppState("READY");
    setErrorMsg(null);
  }, []);

  return {
    appState,
    setAppState,
    sessionId,
    currentQuestion,
    errorMsg,
    setErrorMsg,
    lastAnswerResult,
    isRetrying,
    liveFeedback,
    evalStreaming,
    // Config
    interviewType,
    setInterviewType,
    technicalDomain,
    setTechnicalDomain,
    customGoal,
    setCustomGoal,
    resumeText,
    setResumeText,
    jobDescription,
    setJobDescription,
    interviewLevel,
    setInterviewLevel,
    assessmentGoals,
    toggleGoal,
    // Actions
    startSession,
    submitAudioAnswer,
    retryAnalysis,
    retryQuestion,
    proceedToNext,
    sendLiveTranscript,
    resetSession,
    retryCurrentQuestion,
  };
}