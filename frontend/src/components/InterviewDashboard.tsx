"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  startInterview,
  InterviewStartRequest,
  Question,
  AnswerSubmissionResponse,
  submitMediaAnswerRest,
  submitAnswerRest,
  fetchQuestionAudio,
  retryAnswerRest,
  ActionableFinding,
  RevisionDelta,
  RubricCriterion,
} from "../lib/interviewApi";
import { InterviewWebSocketClient, WebSocketServerEvent } from "../lib/interviewWebSocket";
import {
  AlertCircle,
  CheckCircle,
  Volume2,
  VolumeX,
  Briefcase,
  Users,
  Code,
  Languages,
  Sparkles,
  ArrowRight,
  Award,
  TrendingUp,
  Lightbulb,
  Compass,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Quote,
  RotateCcw,
  X,
  Activity,
  ShieldAlert,
  Target,
  BarChart2,
  Check,
  Scale,
} from "lucide-react";
import { QuestionSpeaker } from "../lib/speechSynthesis";
import { AudioRecorder, LiveFeedbackData } from "./AudioRecorder";
import { InterviewerAvatar } from "./InterviewerAvatar";

type InterviewTypeOption = "job" | "hr" | "technical" | "english" | "custom";
type InterviewLevelOption = "beginner" | "intermediate" | "advanced";

const TECHNICAL_DOMAINS = [
  "Java",
  "Python",
  "DSA",
  "DBMS",
  "Web Development",
  "AI/ML",
  "Other",
];

const ASSESSMENT_GOAL_OPTIONS = [
  { id: "COMMUNICATION", label: "Communication", desc: "Clarity, concise explanations, logical structure" },
  { id: "ENGLISH", label: "English", desc: "Spoken fluency, vocabulary breadth, grammatical precision" },
  { id: "PERFORMANCE", label: "Performance", desc: "Eye contact, confidence, controlled pacing" },
  { id: "THINKING", label: "Thinking", desc: "Problem solving, reasoning, critical depth" },
  { id: "TECHNICAL", label: "Technical", desc: "Technical accuracy, depth, architectural understanding" },
];

export default function InterviewDashboard() {
  const [appState, setAppState] = useState<
    "CONFIG" | "READY" | "PROCESSING" | "ANSWER_RESULT" | "COMPLETED" | "ERROR" | "EVAL_ERROR"
  >("CONFIG");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [lastAnswerResult, setLastAnswerResult] = useState<AnswerSubmissionResponse | null>(null);
  const [isRetrying, setIsRetrying] = useState<boolean>(false);

  // Live real-time question-aware feedback state
  const [liveFeedback, setLiveFeedback] = useState<LiveFeedbackData | null>(null);

  // Configuration State
  const [interviewType, setInterviewType] = useState<InterviewTypeOption>("job");
  const [technicalDomain, setTechnicalDomain] = useState<string>("Python");
  const [customGoal, setCustomGoal] = useState<string>("");
  const [interviewLevel, setInterviewLevel] = useState<InterviewLevelOption>("intermediate");
  const [assessmentGoals, setAssessmentGoals] = useState<string[]>(["COMMUNICATION", "PERFORMANCE"]);

  // Question speaking sequence phase: "SPEAKING" (question text hidden) vs "READY_TO_ANSWER" (question text revealed)
  const [questionPhase, setQuestionPhase] = useState<"SPEAKING" | "READY_TO_ANSWER">("SPEAKING");
  const [speechFailed, setSpeechFailed] = useState<boolean>(false);
  const [activeWord, setActiveWord] = useState<string>("");
  const [questionAudioBlob, setQuestionAudioBlob] = useState<Blob | null>(null);

  // Voice synthesis speaker & state tracking
  const speakerRef = useRef<QuestionSpeaker | null>(null);
  const lastSpokenQuestionIdRef = useRef<string | null>(null);

  // WS Client ref to ensure single instance
  const wsClientRef = useRef<InterviewWebSocketClient | null>(null);

  // Initialize speaker and cleanup on unmount
  useEffect(() => {
    speakerRef.current = new QuestionSpeaker();
    return () => {
      if (wsClientRef.current) {
        wsClientRef.current.disconnect();
        wsClientRef.current = null;
      }
      if (speakerRef.current) {
        speakerRef.current.stop();
        speakerRef.current = null;
      }
    };
  }, []);

  const handleAvatarSpeechEnd = useCallback(() => {
    setActiveWord("");
    setQuestionPhase("READY_TO_ANSWER");
  }, []);

  const stopSpeaking = useCallback(() => {
    if (speakerRef.current) {
      speakerRef.current.stop();
    }
    setQuestionAudioBlob(null);
    setActiveWord("");
    setQuestionPhase("READY_TO_ANSWER");
  }, []);

  const speakQuestion = useCallback(async (question: Question) => {
    setQuestionPhase("SPEAKING");
    setSpeechFailed(false);
    setActiveWord("");

    // Attempt to fetch free neural audio for the 3D talking avatar
    const blob = await fetchQuestionAudio(question.question_text);
    if (blob) {
      setQuestionAudioBlob(blob);
      return;
    }

    // Fallback: browser SpeechSynthesis
    setQuestionAudioBlob(null);
    if (!speakerRef.current || !speakerRef.current.isAvailable()) {
      setSpeechFailed(true);
      setActiveWord("");
      setQuestionPhase("READY_TO_ANSWER");
      return;
    }

    speakerRef.current.speak(
      question.question_text,
      () => {
        // onStart: confirm speaking state
        setQuestionPhase("SPEAKING");
      },
      () => {
        // onEnd: speech completed cleanly, reveal question text
        setActiveWord("");
        setQuestionPhase("READY_TO_ANSWER");
      },
      (err: unknown) => {
        console.warn("Speech synthesis playback error / fallback:", err);
        setSpeechFailed(true);
        setActiveWord("");
        // Reveal question text on error so candidate is never blocked
        setQuestionPhase("READY_TO_ANSWER");
      },
      (_charIndex, _charLength, word) => {
        setActiveWord(word);
      }
    );
  }, []);

  const replayQuestion = useCallback(() => {
    if (!currentQuestion) return;
    if (speakerRef.current) {
      speakerRef.current.stop();
    }
    setActiveWord("");
    setQuestionPhase("SPEAKING");
    setSpeechFailed(false);

    // Unlock browser AudioContext during user click gesture
    if (typeof window !== "undefined") {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        new AudioCtx().resume().catch(() => {});
      }
    }

    if (questionAudioBlob) {
      // Create a fresh blob reference so InterviewerAvatar triggers immediate replay
      const freshBlob = questionAudioBlob.slice();
      setQuestionAudioBlob(freshBlob);
    } else {
      speakQuestion(currentQuestion);
    }
  }, [currentQuestion, questionAudioBlob, speakQuestion]);

  const resetInterview = () => {
    if (wsClientRef.current) {
      wsClientRef.current.disconnect();
      wsClientRef.current = null;
    }
    if (speakerRef.current) {
      speakerRef.current.stop();
    }
    setActiveWord("");
    lastSpokenQuestionIdRef.current = null;
    setSpeechFailed(false);
    setQuestionPhase("SPEAKING");
    setSessionId(null);
    setCurrentQuestion(null);
    setErrorMsg(null);
    setLiveFeedback(null);
    setAppState("CONFIG");
  };

  // Automatically speak new questions exactly ONCE when READY.
  // lastSpokenQuestionIdRef prevents duplicate playback on rerenders or duplicate events.
  useEffect(() => {
    if (appState === "READY" && currentQuestion) {
      if (lastSpokenQuestionIdRef.current !== currentQuestion.id) {
        lastSpokenQuestionIdRef.current = currentQuestion.id;
        speakQuestion(currentQuestion);
      }
    } else {
      if (speakerRef.current) {
        speakerRef.current.stop();
      }
    }
  }, [appState, currentQuestion, speakQuestion]);

  const toggleGoal = (goalId: string) => {
    setAssessmentGoals((prev) => {
      if (prev.includes(goalId)) {
        if (prev.length === 1) return prev; // Keep at least one goal
        return prev.filter((g) => g !== goalId);
      } else {
        return [...prev, goalId];
      }
    });
  };

  const handleStart = async () => {
    // Unlock browser AudioContext during user gesture so avatar speech can play immediately
    if (typeof window !== "undefined") {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        new AudioCtx().resume().catch(() => {});
      }
    }

    try {
      setAppState("PROCESSING");
      setErrorMsg(null);
      setLiveFeedback(null);
      setQuestionPhase("SPEAKING");

      const req: InterviewStartRequest = {
        interview_type: interviewType,
        interview_level: interviewLevel,
        assessment_goals: assessmentGoals.length > 0 ? assessmentGoals : ["COMMUNICATION"],
        technical_domain: interviewType === "technical" ? technicalDomain : null,
        custom_goal: interviewType === "custom" && customGoal.trim() ? customGoal.trim() : null,
      };

      const res = await startInterview(req);
      setSessionId(res.session_id);
      setCurrentQuestion(res.current_question);

      // Connect WebSocket for passive state listening and updates
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
  };

  const handleWsMessage = (event: WebSocketServerEvent) => {
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
          setQuestionPhase("SPEAKING");
          setCurrentQuestion(question);
          setAppState("READY");
        } else {
          setErrorMsg("Received invalid question data from server.");
          setAppState("ERROR");
        }
        break;
      }
      case "processing":
        setAppState("PROCESSING");
        break;
      case "answer_result": {
        const completionStatus = event.completion_status ?? event.payload?.completion_status;
        const nextQuestion = event.next_question ?? event.payload?.next_question;
        if (completionStatus === "completed") {
          setAppState("COMPLETED");
        } else if (nextQuestion && typeof nextQuestion === "object" && typeof nextQuestion.id === "string") {
          setQuestionPhase("SPEAKING");
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
        setAppState("COMPLETED");
        break;
      case "error": {
        const message = event.message ?? event.payload?.message;
        setErrorMsg(typeof message === "string" && message ? message : "Server error occurred");
        setAppState("ERROR");
        break;
      }
      default:
        console.warn("Unknown WS event", event);
    }
  };

  const handleLiveTranscriptUpdate = useCallback(
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

  const handleRetryAnalysis = async () => {
    if (!sessionId || !currentQuestion || !lastAnswerResult) return;

    setAppState("PROCESSING");
    setErrorMsg(null);

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
  };

  const handleAudioSubmit = async (mediaBlob: Blob) => {
    if (!sessionId || !currentQuestion) return;

    stopSpeaking();
    setAppState("PROCESSING");
    setErrorMsg(null);

    try {
      let ext = "webm";
      if (mediaBlob.type.includes("mp4")) ext = "mp4";
      if (mediaBlob.type.includes("ogg")) ext = "ogg";

      const result = await submitMediaAnswerRest(sessionId, currentQuestion.id, mediaBlob, `answer.${ext}`);

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
      let errorDetail = "Something went wrong while analyzing your answer. Please try again.";
      const errorResponse = err as { response?: { status?: number; data?: { detail?: string } } };
      if (errorResponse.response?.status === 404) {
        errorDetail = "Interview session not found.";
      } else if (errorResponse.response?.status === 409) {
        errorDetail = "This answer has already been processed or the question is no longer active.";
      } else if (errorResponse.response?.status === 422) {
        errorDetail = errorResponse.response.data?.detail || "The audio could not be processed. Please record again.";
      }
      setAppState("ERROR");
    }
  };

  const handleRetry = async () => {
    if (!sessionId || !currentQuestion) return;
    try {
      setIsRetrying(true);
      setErrorMsg(null);
      const res = await retryAnswerRest(sessionId, currentQuestion.id);
      setCurrentQuestion(res.question);
      setQuestionPhase("READY_TO_ANSWER");
      setAppState("READY");
    } catch (err: unknown) {
      console.error("Retry preparation failed:", err);
      setErrorMsg("Failed to prepare retry. Please proceed to the next question.");
    } finally {
      setIsRetrying(false);
    }
  };

  return (
    <div className="flex-1 p-4 sm:p-6 lg:p-8 text-white min-h-screen">
      <div
        className={`mx-auto transition-all duration-300 ${
          appState === "READY" || appState === "PROCESSING"
            ? "max-w-[1580px] w-full space-y-6"
            : appState === "ANSWER_RESULT"
            ? "max-w-6xl w-full space-y-6"
            : "max-w-5xl w-full space-y-6"
        }`}
      >
        {/* Top Header & Breadcrumb */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-white/[0.07] pb-5">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-[10px] font-mono tracking-widest text-emerald-400/90 uppercase font-semibold">
                Zaira AI
              </span>
              <span className="text-white/20 text-xs">•</span>
              <span className="text-[10px] font-mono tracking-wider text-white/50 uppercase">
                AI Communication & Interview Assistance
              </span>
            </div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-white">
              AI Adaptive Interview
            </h1>
            <p className="text-xs md:text-sm text-white/50 mt-1">
              Spoken prompt generation with real-time multi-modal candidate assessment and adaptive inquiry.
            </p>
          </div>
          {appState !== "CONFIG" && (
            <button
              onClick={resetInterview}
              className="self-start sm:self-center flex items-center gap-2 text-xs text-white/60 hover:text-white px-3.5 py-2 rounded-lg border border-white/10 bg-white/[0.03] hover:bg-white/[0.08] transition-all hover:border-white/20"
            >
              <X className="w-3.5 h-3.5 text-white/50" />
              <span>Exit Session</span>
            </button>
          )}
        </div>

        {/* Global Error Banner */}
        {errorMsg && (
          <div className="p-4 bg-red-950/30 border border-red-500/30 rounded-xl flex flex-col gap-3 text-red-200 backdrop-blur-xl">
            <div className="flex gap-3 items-start">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5 text-red-400" />
              <p className="text-sm text-red-200/90 leading-relaxed">{errorMsg}</p>
            </div>
            {appState === "ERROR" && (
              <div className="flex justify-end gap-3 pt-2 border-t border-red-500/20">
                {sessionId && currentQuestion && (
                  <button
                    onClick={() => {
                      setAppState("READY");
                      setErrorMsg(null);
                    }}
                    className="px-4 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-xs font-medium transition-colors text-white"
                  >
                    Retry Current Question
                  </button>
                )}
                <button
                  onClick={resetInterview}
                  className="px-4 py-1.5 bg-red-500/20 hover:bg-red-500/30 rounded-lg text-xs font-medium transition-colors text-white"
                >
                  Start New Interview
                </button>
              </div>
            )}
            {appState === "EVAL_ERROR" && (
              <div className="flex justify-end gap-3 pt-2 border-t border-red-500/20">
                <button
                  onClick={handleRetryAnalysis}
                  className="px-4 py-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/30 rounded-lg text-xs font-medium transition-colors text-emerald-300"
                >
                  Retry Evaluation
                </button>
                <button
                  onClick={() => {
                    setAppState("READY");
                    setErrorMsg(null);
                  }}
                  className="px-4 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-xs font-medium transition-colors text-white"
                >
                  Record New Answer
                </button>
              </div>
            )}
          </div>
        )}

        {/* ============================================================== */}
        {/* PART 2 — CONFIGURATION FLOW (STEPS A, B, C, D)                */}
        {/* ============================================================== */}
        {appState === "CONFIG" && (
          <div className="p-6 md:p-8 border border-white/[0.07] rounded-2xl space-y-8 bg-zinc-950/70 backdrop-blur-xl shadow-2xl relative overflow-hidden">
            {/* Step A: Interview Type */}
            <div className="space-y-4">
              <div className="flex items-center gap-2.5">
                <span className="w-6 h-6 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono font-bold flex items-center justify-center">
                  A
                </span>
                <h2 className="text-base font-semibold tracking-tight text-white">Select Interview Category</h2>
                <span className="text-xs text-white/40">• Adaptive prompt configuration</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {/* 1. Job / Placement */}
                <button
                  type="button"
                  onClick={() => setInterviewType("job")}
                  className={`text-left p-4 rounded-xl border transition-all flex flex-col justify-between ${
                    interviewType === "job"
                      ? "border-emerald-500/70 bg-emerald-500/[0.08] shadow-[0_0_20px_rgba(16,185,129,0.12)]"
                      : "border-white/[0.07] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.05]"
                  }`}
                >
                  <div className="flex items-center gap-2.5 mb-2">
                    <div className={`p-2 rounded-lg ${interviewType === "job" ? "bg-emerald-500/20 text-emerald-400" : "bg-white/5 text-white/50"}`}>
                      <Briefcase className="w-4 h-4" />
                    </div>
                    <span className="font-semibold text-sm text-white">Job / Placement</span>
                  </div>
                  <p className="text-xs text-white/50 leading-relaxed">
                    Comprehensive career interview covering background, experience, and structured problem solving.
                  </p>
                </button>

                {/* 2. HR Interview */}
                <button
                  type="button"
                  onClick={() => setInterviewType("hr")}
                  className={`text-left p-4 rounded-xl border transition-all flex flex-col justify-between ${
                    interviewType === "hr"
                      ? "border-emerald-500/70 bg-emerald-500/[0.08] shadow-[0_0_20px_rgba(16,185,129,0.12)]"
                      : "border-white/[0.07] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.05]"
                  }`}
                >
                  <div className="flex items-center gap-2.5 mb-2">
                    <div className={`p-2 rounded-lg ${interviewType === "hr" ? "bg-emerald-500/20 text-emerald-400" : "bg-white/5 text-white/50"}`}>
                      <Users className="w-4 h-4" />
                    </div>
                    <span className="font-semibold text-sm text-white">HR Interview</span>
                  </div>
                  <p className="text-xs text-white/50 leading-relaxed">
                    Behavioral questions, interpersonal alignment, conflict management, and workplace adaptability.
                  </p>
                </button>

                {/* 3. Technical Interview */}
                <button
                  type="button"
                  onClick={() => setInterviewType("technical")}
                  className={`text-left p-4 rounded-xl border transition-all flex flex-col justify-between ${
                    interviewType === "technical"
                      ? "border-emerald-500/70 bg-emerald-500/[0.08] shadow-[0_0_20px_rgba(16,185,129,0.12)]"
                      : "border-white/[0.07] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.05]"
                  }`}
                >
                  <div className="flex items-center gap-2.5 mb-2">
                    <div className={`p-2 rounded-lg ${interviewType === "technical" ? "bg-emerald-500/20 text-emerald-400" : "bg-white/5 text-white/50"}`}>
                      <Code className="w-4 h-4" />
                    </div>
                    <span className="font-semibold text-sm text-white">Technical Interview</span>
                  </div>
                  <p className="text-xs text-white/50 leading-relaxed">
                    In-depth questions on engineering practices, domain concepts, and technical trade-offs.
                  </p>
                </button>

                {/* 4. English Speaking */}
                <button
                  type="button"
                  onClick={() => setInterviewType("english")}
                  className={`text-left p-4 rounded-xl border transition-all flex flex-col justify-between ${
                    interviewType === "english"
                      ? "border-emerald-500/70 bg-emerald-500/[0.08] shadow-[0_0_20px_rgba(16,185,129,0.12)]"
                      : "border-white/[0.07] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.05]"
                  }`}
                >
                  <div className="flex items-center gap-2.5 mb-2">
                    <div className={`p-2 rounded-lg ${interviewType === "english" ? "bg-emerald-500/20 text-emerald-400" : "bg-white/5 text-white/50"}`}>
                      <Languages className="w-4 h-4" />
                    </div>
                    <span className="font-semibold text-sm text-white">English Speaking</span>
                  </div>
                  <p className="text-xs text-white/50 leading-relaxed">
                    Evaluates spoken fluency, pronunciation clarity, sentence variety, and conversational vocabulary.
                  </p>
                </button>

                {/* 5. Custom Interview */}
                <button
                  type="button"
                  onClick={() => setInterviewType("custom")}
                  className={`text-left p-4 rounded-xl border transition-all flex flex-col justify-between ${
                    interviewType === "custom"
                      ? "border-emerald-500/70 bg-emerald-500/[0.08] shadow-[0_0_20px_rgba(16,185,129,0.12)]"
                      : "border-white/[0.07] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.05]"
                  }`}
                >
                  <div className="flex items-center gap-2.5 mb-2">
                    <div className={`p-2 rounded-lg ${interviewType === "custom" ? "bg-emerald-500/20 text-emerald-400" : "bg-white/5 text-white/50"}`}>
                      <Sparkles className="w-4 h-4" />
                    </div>
                    <span className="font-semibold text-sm text-white">Custom Interview</span>
                  </div>
                  <p className="text-xs text-white/50 leading-relaxed">
                    Tailor the interview for a specific role description, target company, or custom scenario.
                  </p>
                </button>
              </div>

              {/* Technical Domain Selector (when Technical Interview selected) */}
              {interviewType === "technical" && (
                <div className="p-4 bg-black/50 border border-white/[0.07] rounded-xl space-y-2 mt-3 animate-fadeIn">
                  <label className="text-[11px] font-mono uppercase tracking-wider text-emerald-400/90 block font-semibold">
                    Target Technical Domain
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {TECHNICAL_DOMAINS.map((domain) => (
                      <button
                        key={domain}
                        type="button"
                        onClick={() => setTechnicalDomain(domain)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                          technicalDomain === domain
                            ? "bg-emerald-500/20 border-emerald-500/80 text-emerald-300 font-semibold shadow-[0_0_12px_rgba(16,185,129,0.2)]"
                            : "bg-white/[0.03] border-white/10 text-white/60 hover:text-white hover:bg-white/[0.08]"
                        }`}
                      >
                        {domain}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Custom Goal Input (when Custom Interview selected) */}
              {interviewType === "custom" && (
                <div className="p-4 bg-black/50 border border-white/[0.07] rounded-xl space-y-2 mt-3 animate-fadeIn">
                  <label className="text-[11px] font-mono uppercase tracking-wider text-emerald-400/90 block font-semibold">
                    Custom Scenario or Assessment Goal
                  </label>
                  <input
                    type="text"
                    value={customGoal}
                    onChange={(e) => setCustomGoal(e.target.value)}
                    placeholder="e.g. Senior Backend Engineer interview focusing on high-throughput microservices"
                    className="w-full bg-[#050508] border border-white/10 rounded-lg px-3.5 py-2.5 text-xs md:text-sm text-white placeholder-white/30 focus:outline-none focus:border-emerald-500/70 transition-colors"
                  />
                </div>
              )}
            </div>

            {/* Step B: Interview Level */}
            <div className="space-y-4">
              <div className="flex items-center gap-2.5">
                <span className="w-6 h-6 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono font-bold flex items-center justify-center">
                  B
                </span>
                <h2 className="text-base font-semibold tracking-tight text-white">Select Experience Level</h2>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {[
                  { id: "beginner", title: "Beginner", desc: "Foundational questions & gentle pacing" },
                  { id: "intermediate", title: "Intermediate", desc: "Standard professional depth (Default)" },
                  { id: "advanced", title: "Advanced", desc: "Complex trade-offs & senior evaluations" },
                ].map((lvl) => (
                  <button
                    key={lvl.id}
                    type="button"
                    onClick={() => setInterviewLevel(lvl.id as InterviewLevelOption)}
                    className={`text-left p-4 rounded-xl border transition-all ${
                      interviewLevel === lvl.id
                        ? "border-emerald-500/70 bg-emerald-500/[0.08] shadow-[0_0_20px_rgba(16,185,129,0.12)]"
                        : "border-white/[0.07] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.05]"
                    }`}
                  >
                    <div className="font-semibold text-sm text-white mb-1">{lvl.title}</div>
                    <p className="text-xs text-white/50 leading-relaxed">{lvl.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Step C: Assessment Goals */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="w-6 h-6 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono font-bold flex items-center justify-center">
                    C
                  </span>
                  <h2 className="text-base font-semibold tracking-tight text-white">Select Competency Objectives</h2>
                </div>
                <span className="text-[11px] font-mono text-white/40 uppercase">Multi-select enabled</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {ASSESSMENT_GOAL_OPTIONS.map((goal) => {
                  const isChecked = assessmentGoals.includes(goal.id);
                  return (
                    <button
                      key={goal.id}
                      type="button"
                      onClick={() => toggleGoal(goal.id)}
                      className={`text-left p-4 rounded-xl border transition-all flex items-start justify-between gap-2 ${
                        isChecked
                          ? "border-emerald-500/60 bg-emerald-500/[0.06] text-white"
                          : "border-white/[0.07] bg-white/[0.02] text-white/70 hover:border-white/20 hover:bg-white/[0.05]"
                      }`}
                    >
                      <div>
                        <div className="font-semibold text-sm mb-1 text-white">{goal.label}</div>
                        <p className="text-xs text-white/50 leading-relaxed">{goal.desc}</p>
                      </div>
                      <div
                        className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 mt-0.5 transition-colors ${
                          isChecked ? "bg-emerald-500 border-emerald-400" : "border-white/20 bg-black/40"
                        }`}
                      >
                        {isChecked && <CheckCircle className="w-3.5 h-3.5 text-black stroke-[3]" />}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Step D: Start Interview CTA */}
            <div className="pt-6 border-t border-white/[0.07] flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="text-xs text-white/50 leading-relaxed">
                Spoken prompts will be articulated dynamically by the 3D AI Interviewer with neural speech synthesis.
              </div>
              <button
                type="button"
                onClick={handleStart}
                className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-3.5 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-black font-semibold rounded-xl shadow-[0_0_25px_rgba(16,185,129,0.25)] transition-all transform hover:-translate-y-0.5 active:translate-y-0"
              >
                <span>Initialize AI Session</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Initializing / Generating Opening Question Loading State */}
        {appState === "PROCESSING" && !currentQuestion && (
          <div className="p-12 border border-white/[0.07] rounded-2xl bg-zinc-950/70 backdrop-blur-xl shadow-2xl flex flex-col items-center justify-center text-center space-y-5 animate-fadeIn">
            <div className="relative w-16 h-16 flex items-center justify-center">
              <div className="absolute inset-0 rounded-full border-2 border-emerald-500/20 animate-ping pointer-events-none" />
              <div className="w-14 h-14 rounded-full border-2 border-emerald-500/30 border-t-emerald-400 animate-spin flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-emerald-400" />
              </div>
            </div>
            <div className="space-y-1.5 max-w-md">
              <h2 className="text-lg font-semibold text-white tracking-tight">
                Initializing AI Interview Session
              </h2>
              <p className="text-xs text-white/50 leading-relaxed">
                Calibrating interview rubric, connecting real-time telemetry, and formulating your tailored opening question...
              </p>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* PART 3 & 4 — SPEECH-FIRST QUESTION WORKFLOW & RECORDING        */}
        {/* ============================================================== */}
        {(appState === "READY" || appState === "PROCESSING") && currentQuestion && (
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 lg:gap-8 items-start">
            {/* Left Column (7 cols): Hero AI Interviewer Stage */}
            <div className="xl:col-span-7 2xl:col-span-7 space-y-4">
              <InterviewerAvatar
                isSpeaking={questionPhase === "SPEAKING"}
                isThinking={appState === "PROCESSING"}
                onSkip={stopSpeaking}
                onSpeechEnd={handleAvatarSpeechEnd}
                audioBlob={questionAudioBlob}
                currentWord={activeWord}
              />
            </div>

            {/* Right Column (5 cols): Active Question & Candidate Console */}
            <div className="xl:col-span-5 2xl:col-span-5 space-y-5">
              {/* Clean Active Question Card */}
              <div className="p-6 md:p-7 border border-white/[0.08] rounded-2xl bg-zinc-950/80 backdrop-blur-xl shadow-xl space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs text-white/50">
                    <span className="font-semibold text-white/70 capitalize">{interviewType} Interview</span>
                    {technicalDomain && interviewType === "technical" && (
                      <>
                        <span className="text-white/20">•</span>
                        <span className="text-white/60">{technicalDomain}</span>
                      </>
                    )}
                  </div>

                  {/* Clean Audio Action */}
                  {questionPhase === "SPEAKING" ? (
                    <button
                      onClick={stopSpeaking}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/[0.06] hover:bg-white/[0.12] text-zinc-300 hover:text-white border border-white/10 transition-all"
                    >
                      <VolumeX className="w-3.5 h-3.5 text-zinc-400" />
                      <span>Skip Audio</span>
                    </button>
                  ) : (
                    <button
                      onClick={replayQuestion}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white/[0.04] text-white/70 hover:text-white hover:bg-white/[0.09] transition-all border border-white/10"
                      aria-label="Replay canonical question aloud"
                    >
                      <Volume2 className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Replay Audio</span>
                    </button>
                  )}
                </div>

                <h2 className="text-lg md:text-xl font-medium leading-relaxed text-white">
                  {currentQuestion.question_text}
                </h2>

                {speechFailed && (
                  <p className="text-xs text-amber-400/90 pt-1">
                    Note: Audio playback was unavailable in this browser session. You can read the question prompt above, or click &apos;Replay Audio&apos; to retry.
                  </p>
                )}
              </div>

              {/* Candidate Recording Controls */}
              {questionPhase === "READY_TO_ANSWER" && (
                <AudioRecorder
                  key={currentQuestion.id}
                  questionId={currentQuestion.id}
                  autoStart={true}
                  onRecordingStart={stopSpeaking}
                  onRecordingComplete={handleAudioSubmit}
                  onLiveTranscriptUpdate={handleLiveTranscriptUpdate}
                  liveFeedback={liveFeedback}
                  isProcessing={appState === "PROCESSING"}
                  disabled={appState === "PROCESSING"}
                />
              )}
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* ANSWER RESULT VIEW — EVALUATION REPORT                          */}
        {/* ============================================================== */}
        {appState === "ANSWER_RESULT" && lastAnswerResult && (
          <div className="p-6 md:p-8 border border-white/[0.07] rounded-2xl space-y-6 bg-zinc-950/80 backdrop-blur-xl shadow-2xl">
            {/* 1. Header with Evaluation Status */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.07] pb-4">
              <div>
                <h2 className="text-xl md:text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
                  <Award className="w-5 h-5 text-emerald-400" />
                  Performance Evaluation Report
                </h2>
                <p className="text-xs text-white/50 mt-0.5">
                  Verified multi-modal evaluation and objective competency evidence
                </p>
              </div>
              <div className="flex items-center gap-2">
                {lastAnswerResult.is_revision && (
                  <span className="text-xs px-2.5 py-1 rounded-full font-mono font-semibold bg-teal-500/15 text-teal-300 border border-teal-500/30 flex items-center gap-1.5">
                    <RotateCcw className="w-3 h-3 text-teal-400" />
                    Revision Evaluated
                  </span>
                )}
                <span
                  className={`text-xs px-3 py-1 rounded-full font-medium border flex items-center gap-1.5 ${
                    lastAnswerResult.structured_evaluation?.evaluation_status === "success" ||
                    lastAnswerResult.overall_answer_quality !== null
                      ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                      : "bg-amber-500/15 text-amber-300 border-amber-500/30"
                  }`}
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  {lastAnswerResult.structured_evaluation?.evaluation_status === "success"
                    ? "Evaluation Verified"
                    : "Evaluation Complete"}
                </span>
              </div>
            </div>

            {/* Evaluated Question Banner */}
            {currentQuestion && (
              <div className="p-4 bg-white/[0.02] border border-white/[0.08] rounded-xl space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono text-emerald-400 uppercase tracking-widest font-semibold flex items-center gap-1.5">
                    <Target className="w-3.5 h-3.5 text-emerald-400" />
                    Evaluated Question
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 text-white/60 border border-white/10 uppercase">
                      {(currentQuestion.topics && currentQuestion.topics.length > 0) ? currentQuestion.topics.join(", ") : currentQuestion.question_type}
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      Difficulty: {Math.round(currentQuestion.difficulty * 100)}%
                    </span>
                  </div>
                </div>
                <h3 className="text-sm md:text-base font-semibold text-white tracking-tight">
                  {currentQuestion.question_text}
                </h3>
              </div>
            )}

            {/* 2. REVISION DELTA COMPARISON (if candidate retried this question) */}
            {lastAnswerResult.is_revision && lastAnswerResult.revision_delta && (
              <div className="p-5 bg-gradient-to-br from-teal-500/[0.08] to-emerald-500/[0.04] border border-teal-500/30 rounded-xl space-y-4 shadow-[0_0_25px_rgba(20,184,166,0.1)]">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-teal-500/20 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-md bg-teal-500/20 text-teal-300 flex items-center justify-center font-mono font-bold text-xs">
                      Δ
                    </span>
                    <span className="text-sm font-bold text-white tracking-tight">
                      Revision Comparison & Growth Delta
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs px-2.5 py-0.5 rounded font-mono font-bold border ${
                        lastAnswerResult.revision_delta.overall_quality_delta_pts >= 0
                          ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                          : "bg-amber-500/20 text-amber-300 border-amber-500/40"
                      }`}
                    >
                      {lastAnswerResult.revision_delta.overall_quality_delta_pts >= 0 ? "+" : ""}
                      {lastAnswerResult.revision_delta.overall_quality_delta_pts} pts Overall Score
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="p-3 bg-black/40 rounded-lg border border-white/[0.06]">
                    <div className="text-[10px] text-white/50 uppercase font-mono">Original Score</div>
                    <div className="text-xl font-bold font-mono text-white/70 mt-1">
                      {lastAnswerResult.revision_delta.original_score}
                      <span className="text-xs text-white/40"> / 100</span>
                    </div>
                  </div>
                  <div className="p-3 bg-black/40 rounded-lg border border-teal-500/20">
                    <div className="text-[10px] text-teal-300/70 uppercase font-mono">Revised Score</div>
                    <div className="text-xl font-bold font-mono text-teal-300 mt-1">
                      {lastAnswerResult.revision_delta.revised_score}
                      <span className="text-xs text-white/40"> / 100</span>
                    </div>
                  </div>
                  {lastAnswerResult.revision_delta.wpm_delta !== 0 && (
                    <div className="p-3 bg-black/40 rounded-lg border border-white/[0.06]">
                      <div className="text-[10px] text-white/50 uppercase font-mono">Pacing Delta</div>
                      <div className="text-xl font-bold font-mono text-white mt-1">
                        {lastAnswerResult.revision_delta.wpm_delta > 0 ? "+" : ""}
                        {lastAnswerResult.revision_delta.wpm_delta}{" "}
                        <span className="text-xs text-white/40 font-sans">WPM</span>
                      </div>
                    </div>
                  )}
                  {Object.keys(lastAnswerResult.revision_delta.dimensional_deltas).length > 0 && (
                    <div className="p-3 bg-black/40 rounded-lg border border-white/[0.06] sm:col-span-2 md:col-span-1">
                      <div className="text-[10px] text-white/50 uppercase font-mono">Key Metric Gain</div>
                      <div className="text-xs text-white/80 mt-1.5 space-y-0.5">
                        {Object.entries(lastAnswerResult.revision_delta.dimensional_deltas)
                          .slice(0, 2)
                          .map(([k, v]) => (
                            <div key={k} className="flex justify-between font-mono text-[11px]">
                              <span className="capitalize">{k}:</span>
                              <span className={v >= 0 ? "text-emerald-400" : "text-amber-400"}>
                                {v > 0 ? `+${v}%` : `${v}%`}
                              </span>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Resolved Weaknesses & New Strengths */}
                {(lastAnswerResult.revision_delta.resolved_weaknesses.length > 0 ||
                  lastAnswerResult.revision_delta.new_strengths.length > 0) && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                    {lastAnswerResult.revision_delta.resolved_weaknesses.length > 0 && (
                      <div className="p-3 bg-emerald-500/[0.04] rounded-lg border border-emerald-500/20 text-xs">
                        <div className="font-semibold text-emerald-400 mb-1.5 flex items-center gap-1.5 text-[11px]">
                          <Check className="w-3.5 h-3.5" />
                          Addressed in This Revision:
                        </div>
                        <ul className="space-y-1 text-white/70">
                          {lastAnswerResult.revision_delta.resolved_weaknesses.map((w, idx) => (
                            <li key={idx} className="flex items-start gap-1.5">
                              <span className="text-emerald-400 shrink-0">•</span>
                              <span>{w}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {lastAnswerResult.revision_delta.new_strengths.length > 0 && (
                      <div className="p-3 bg-teal-500/[0.04] rounded-lg border border-teal-500/20 text-xs">
                        <div className="font-semibold text-teal-300 mb-1.5 flex items-center gap-1.5 text-[11px]">
                          <Sparkles className="w-3.5 h-3.5 text-teal-400" />
                          New Verified Strengths:
                        </div>
                        <ul className="space-y-1 text-white/70">
                          {lastAnswerResult.revision_delta.new_strengths.map((s, idx) => (
                            <li key={idx} className="flex items-start gap-1.5">
                              <span className="text-teal-400 shrink-0">•</span>
                              <span>{s}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* 3. Garbled Transcript Diagnostic Warning (if audio was indistinct) */}
            {lastAnswerResult.structured_evaluation?.is_garbled_transcript && (
              <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start gap-3">
                <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-semibold text-amber-300 text-sm">
                    Audio Input Was Indistinct or Incomplete
                  </div>
                  <p className="text-xs text-white/70 leading-relaxed">
                    {lastAnswerResult.structured_evaluation.garbled_reason ||
                      "The system could not detect sufficient clear speech to accurately benchmark your answer."}
                  </p>
                  <p className="text-xs text-white/50 pt-1">
                    Tip: Click the <strong className="text-white">Retry Answer</strong> button below to restate your response with clear microphone audio.
                  </p>
                </div>
              </div>
            )}

            {/* Audio Glitch Protection Notice */}
            {(lastAnswerResult.is_transcription_error || lastAnswerResult.structured_evaluation?.is_transcription_error) && (
              <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <h4 className="text-xs font-semibold text-amber-300">
                    Microphone / Transcription Disruption Detected
                  </h4>
                  <p className="text-xs text-amber-200/80 leading-relaxed">
                    {lastAnswerResult.transcription_error_details ||
                      lastAnswerResult.structured_evaluation?.transcription_error_details ||
                      "Audio contained severe static or inaudible segments. Technical knowledge was preserved and not unfairly penalized."}
                  </p>
                </div>
              </div>
            )}

            {/* 4. Overall Performance Score & Strategy Direction */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Overall Score */}
              <div className="p-5 bg-[#0a0a0f] rounded-xl border border-white/[0.07] flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono font-semibold text-white/50 uppercase tracking-widest">
                    Overall Score
                  </span>
                  {(lastAnswerResult.total_marks_awarded !== undefined || lastAnswerResult.structured_evaluation?.total_marks_awarded !== undefined) && (
                    <span className="text-[11px] font-mono text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                      {(lastAnswerResult.total_marks_awarded ?? lastAnswerResult.structured_evaluation?.total_marks_awarded ?? 0).toFixed(1)} / {(lastAnswerResult.total_max_marks ?? lastAnswerResult.structured_evaluation?.total_max_marks ?? 10).toFixed(1)} Marks
                    </span>
                  )}
                </div>
                <div className="my-2 flex items-baseline gap-2">
                  {lastAnswerResult.overall_answer_quality !== null &&
                  lastAnswerResult.overall_answer_quality !== undefined ? (
                    <>
                      <span className="text-4xl font-extrabold text-white font-mono tracking-tight">
                        {Math.round(lastAnswerResult.overall_answer_quality * 100)}
                      </span>
                      <span className="text-xs text-white/40 font-mono">/ 100</span>
                    </>
                  ) : (
                    <span className="text-sm text-white/40 italic">Score Unavailable</span>
                  )}
                </div>
                <div>
                  {lastAnswerResult.overall_answer_quality !== null &&
                  lastAnswerResult.overall_answer_quality !== undefined ? (
                    <span
                      className={`text-[11px] font-medium px-2 py-0.5 rounded border ${
                        lastAnswerResult.overall_answer_quality >= 0.8
                          ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                          : lastAnswerResult.overall_answer_quality >= 0.6
                          ? "bg-teal-500/15 text-teal-300 border-teal-500/30"
                          : lastAnswerResult.overall_answer_quality >= 0.4
                          ? "bg-yellow-500/15 text-yellow-300 border-yellow-500/30"
                          : "bg-red-500/15 text-red-300 border-red-500/30"
                      }`}
                    >
                      {lastAnswerResult.overall_answer_quality >= 0.8
                        ? "Strong Delivery"
                        : lastAnswerResult.overall_answer_quality >= 0.6
                        ? "Competent"
                        : lastAnswerResult.overall_answer_quality >= 0.4
                        ? "Developing"
                        : "Needs Revision"}
                    </span>
                  ) : (
                    <span className="text-[11px] text-white/40">Insufficient evidence</span>
                  )}
                </div>
              </div>

              {/* Adaptive Next Step */}
              <div className="p-5 bg-[#0a0a0f] rounded-xl border border-white/[0.07] md:col-span-2 flex flex-col justify-between">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-mono font-semibold text-white/50 uppercase tracking-widest flex items-center gap-1.5">
                    <Compass className="w-3.5 h-3.5 text-teal-400" />
                    Interviewer Direction & Strategy
                  </span>
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-white/10 text-white/80 border border-white/5">
                    {lastAnswerResult.decision.decision_type.replace(/_/g, " ")}
                  </span>
                </div>
                <p className="text-xs text-white/70 leading-relaxed mt-1">
                  {lastAnswerResult.decision.reason}
                </p>
                <div className="mt-3 text-[11px] text-white/50 flex items-center gap-2">
                  <span>Session Progress:</span>
                  <div className="flex-1 max-w-[140px] h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full transition-all"
                      style={{
                        width: `${Math.round(
                          (lastAnswerResult.interview_progress ?? 0) * 100
                        )}%`,
                      }}
                    />
                  </div>
                  <span className="font-mono text-white/70">
                    {Math.round((lastAnswerResult.interview_progress ?? 0) * 100)}%
                  </span>
                </div>
              </div>
            </div>

            {/* 5. Dimensional Scoring Breakdown */}
            {lastAnswerResult.structured_evaluation && (
              <div className="p-5 bg-[#0a0a0f] rounded-xl border border-white/[0.07] space-y-3">
                <p className="text-[10px] font-mono font-semibold text-white/50 uppercase tracking-widest flex items-center gap-1.5">
                  <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
                  Dimensional Evaluation Breakdown
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
                  {[
                    { label: "Relevance", val: lastAnswerResult.structured_evaluation.relevance },
                    { label: "Clarity", val: lastAnswerResult.structured_evaluation.clarity },
                    { label: "Structure", val: lastAnswerResult.structured_evaluation.structure },
                    { label: "Evidence", val: lastAnswerResult.structured_evaluation.evidence_quality },
                    { label: "Completeness", val: lastAnswerResult.structured_evaluation.completeness },
                  ].map((dim) => (
                    <div key={dim.label} className="p-3 bg-white/[0.02] rounded-lg border border-white/[0.05] flex flex-col justify-between">
                      <div className="text-[11px] text-white/50">{dim.label}</div>
                      <div className="text-base font-bold font-mono text-white mt-1">
                        {dim.val !== null && dim.val !== undefined ? `${Math.round(dim.val * 100)}%` : "N/A"}
                      </div>
                      <div className="w-full h-1 bg-white/10 rounded-full mt-2 overflow-hidden">
                        <div
                          className="h-full bg-emerald-500 rounded-full"
                          style={{
                            width: `${dim.val !== null && dim.val !== undefined ? Math.round(dim.val * 100) : 0}%`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 6. Spoken Transcript */}
            <div className="p-5 bg-[#0a0a0f] rounded-xl border border-white/[0.07] space-y-2">
              <p className="text-[10px] font-mono text-white/50 uppercase tracking-widest font-semibold flex items-center gap-1.5">
                <Quote className="w-3.5 h-3.5 text-emerald-400" />
                Spoken Answer Transcript
              </p>
              <p className="text-xs md:text-sm text-white/80 italic leading-relaxed pl-3 border-l-2 border-emerald-500/50">
                &quot;{lastAnswerResult.transcript}&quot;
              </p>
            </div>

            {/* 6.5. RUBRIC CRITERIA & TRACEABLE MARK DEDUCTIONS */}
            {((lastAnswerResult.rubric_criteria && lastAnswerResult.rubric_criteria.length > 0) ||
              (lastAnswerResult.structured_evaluation?.rubric_criteria &&
                lastAnswerResult.structured_evaluation.rubric_criteria.length > 0)) && (
              <div className="p-5 bg-[#0a0a0f] rounded-xl border border-white/[0.07] space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <p className="text-[10px] font-mono font-semibold text-white/50 uppercase tracking-widest flex items-center gap-1.5">
                      <Scale className="w-3.5 h-3.5 text-emerald-400" />
                      Rubric Assessment & Traceable Mark Deductions
                    </p>
                    <span className="text-xs text-white/50">
                      Every deduction is itemized with direct candidate evidence, deduction reason, and targeted improvement.
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="text-xs font-mono text-emerald-400 font-semibold px-2.5 py-1 rounded bg-emerald-500/10 border border-emerald-500/20">
                      Total Marks: {(lastAnswerResult.total_marks_awarded ?? lastAnswerResult.structured_evaluation?.total_marks_awarded ?? 0).toFixed(1)} / {(lastAnswerResult.total_max_marks ?? lastAnswerResult.structured_evaluation?.total_max_marks ?? 10).toFixed(1)}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-3.5">
                  {(
                    lastAnswerResult.rubric_criteria ??
                    lastAnswerResult.structured_evaluation?.rubric_criteria ??
                    []
                  ).map((rc, idx) => {
                    const isFull = rc.status === "full_credit" || rc.deduction === 0;
                    const isUnassessed = rc.status === "not_assessed" || rc.max_marks === 0;
                    return (
                      <div
                        key={idx}
                        className={`p-4 rounded-xl border transition-all ${
                          isUnassessed
                            ? "bg-white/[0.01] border-white/[0.05] opacity-60"
                            : isFull
                            ? "bg-emerald-500/[0.03] border-emerald-500/25"
                            : "bg-amber-500/[0.03] border-amber-500/30"
                        }`}
                      >
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-white/[0.05]">
                          <div className="flex items-center gap-2">
                            <span
                              className={`w-6 h-6 rounded-md font-mono text-xs font-bold flex items-center justify-center shrink-0 border ${
                                isUnassessed
                                  ? "bg-white/5 text-white/40 border-white/10"
                                  : isFull
                                  ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                                  : "bg-amber-500/15 text-amber-300 border-amber-500/30"
                              }`}
                            >
                              {idx + 1}
                            </span>
                            <h4 className="text-xs md:text-sm font-semibold text-white">
                              {rc.criterion_name}
                            </h4>
                          </div>

                          <div className="flex items-center gap-2">
                            {isUnassessed ? (
                              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-white/50 border border-white/10">
                                Not Assessed (0 Marks)
                              </span>
                            ) : (
                              <>
                                <span className="text-xs font-mono font-bold text-white px-2 py-0.5 rounded bg-white/10 border border-white/5">
                                  {rc.marks_awarded.toFixed(1)} / {rc.max_marks.toFixed(1)} Marks
                                </span>
                                {rc.deduction > 0 ? (
                                  <span className="text-[11px] font-mono font-medium text-rose-300 bg-rose-500/15 border border-rose-500/30 px-2 py-0.5 rounded">
                                    -{rc.deduction.toFixed(1)} Deduction
                                  </span>
                                ) : (
                                  <span className="text-[11px] font-mono font-medium text-emerald-300 bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 rounded">
                                    Full Credit
                                  </span>
                                )}
                              </>
                            )}
                          </div>
                        </div>

                        {/* Breakdown details */}
                        {!isUnassessed && (
                          <div className="mt-3 space-y-2.5 text-xs">
                            {rc.evidence_quote && (
                              <div className="text-[11px] text-white/80 pl-3 border-l-2 border-amber-500/50 italic bg-amber-500/[0.02] py-1 rounded-r">
                                Evidence in Answer: &quot;{rc.evidence_quote}&quot;
                              </div>
                            )}

                            {rc.reason_for_deduction && rc.deduction > 0 && (
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                                <div className="space-y-1">
                                  <span className="text-[10px] font-mono text-rose-400 uppercase font-semibold">
                                    Reason for Deduction:
                                  </span>
                                  <p className="text-white/70 text-[11px] leading-relaxed">
                                    {rc.reason_for_deduction}
                                  </p>
                                </div>
                                {rc.improvement_advice && (
                                  <div className="space-y-1">
                                    <span className="text-[10px] font-mono text-emerald-400 uppercase font-semibold">
                                      What a Strong Answer Includes:
                                    </span>
                                    <p className="text-emerald-300/90 text-[11px] leading-relaxed">
                                      {rc.improvement_advice}
                                    </p>
                                  </div>
                                )}
                              </div>
                            )}

                            {rc.exemplary_example && (
                              <div className="mt-2 p-2.5 bg-emerald-500/[0.04] border border-emerald-500/20 rounded-lg">
                                <span className="text-[10px] font-mono text-emerald-400 uppercase font-semibold flex items-center gap-1.5 mb-1">
                                  <Sparkles className="w-3 h-3 text-emerald-400" />
                                  Exemplary Model Response:
                                </span>
                                <p className="text-xs text-white/85 italic leading-relaxed">
                                  &quot;{rc.exemplary_example}&quot;
                                </p>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 7. ACTIONABLE FINDINGS & MODEL ANSWERS (Finding -> Evidence -> Explanation -> Correction -> Model Answer) */}
            {((lastAnswerResult.actionable_findings && lastAnswerResult.actionable_findings.length > 0) ||
              (lastAnswerResult.structured_evaluation?.actionable_findings &&
                lastAnswerResult.structured_evaluation.actionable_findings.length > 0)) && (
              <div className="p-5 bg-[#0a0a0f] rounded-xl border border-white/[0.07] space-y-4">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] font-mono font-semibold text-white/50 uppercase tracking-widest flex items-center gap-1.5">
                    <Target className="w-3.5 h-3.5 text-teal-400" />
                    Actionable Coaching Findings & Model Answers
                  </p>
                  <span className="text-[10px] font-mono text-white/40">
                    Finding → Evidence → Correction
                  </span>
                </div>
                <div className="space-y-3">
                  {(
                    lastAnswerResult.actionable_findings ??
                    lastAnswerResult.structured_evaluation?.actionable_findings ??
                    []
                  ).map((finding, idx) => (
                    <div
                      key={idx}
                      className="p-4 bg-white/[0.02] rounded-xl border border-white/[0.06] space-y-3"
                    >
                      <div className="flex items-start gap-2">
                        <span className="w-5 h-5 rounded-md bg-amber-500/15 text-amber-300 font-mono text-[10px] font-bold flex items-center justify-center shrink-0 border border-amber-500/30 mt-0.5">
                          {idx + 1}
                        </span>
                        <div className="flex-1">
                          <h4 className="text-xs font-semibold text-white tracking-tight">
                            {finding.finding}
                          </h4>
                        </div>
                      </div>

                      {finding.supporting_evidence && (
                        <div className="text-[11px] text-white/70 pl-3 border-l-2 border-amber-500/50 italic bg-amber-500/[0.02] py-1 rounded-r">
                          Observed Evidence: &quot;{finding.supporting_evidence}&quot;
                        </div>
                      )}

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs pt-1">
                        <div className="space-y-1">
                          <span className="text-[10px] font-mono text-white/40 uppercase">
                            Why this matters:
                          </span>
                          <p className="text-white/60 text-[11px] leading-relaxed">
                            {finding.explanation}
                          </p>
                        </div>
                        <div className="space-y-1">
                          <span className="text-[10px] font-mono text-emerald-400/80 uppercase">
                            How to correct:
                          </span>
                          <p className="text-emerald-300/90 text-[11px] leading-relaxed">
                            {finding.specific_correction}
                          </p>
                        </div>
                      </div>

                      {finding.example_or_model_answer && (
                        <div className="mt-2 p-3 bg-emerald-500/[0.04] border border-emerald-500/20 rounded-lg">
                          <div className="text-[10px] font-mono text-emerald-400 font-semibold uppercase tracking-wider mb-1 flex items-center gap-1.5">
                            <Sparkles className="w-3 h-3 text-emerald-400" />
                            Exemplary Model Answer:
                          </div>
                          <p className="text-xs text-white/85 italic leading-relaxed">
                            &quot;{finding.example_or_model_answer}&quot;
                          </p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 8. Strengths & Areas for Growth */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Strengths */}
              <div className="p-5 bg-emerald-500/[0.03] border border-emerald-500/20 rounded-xl space-y-3">
                <p className="font-semibold text-emerald-400 text-xs md:text-sm flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  Verified Strengths
                </p>
                {lastAnswerResult.detected_strengths && lastAnswerResult.detected_strengths.length > 0 ? (
                  <ul className="space-y-2 text-xs text-white/70">
                    {lastAnswerResult.detected_strengths.map((s: string, i: number) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400/80 mt-1.5 shrink-0" />
                        <span className="leading-relaxed">{s}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-white/40 italic">
                    No direct strengths demonstrated in this response.
                  </p>
                )}
              </div>

              {/* Areas for Growth */}
              <div className="p-5 bg-amber-500/[0.03] border border-amber-500/20 rounded-xl space-y-3">
                <p className="font-semibold text-amber-400 text-xs md:text-sm flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  Areas for Growth
                </p>
                {lastAnswerResult.detected_weaknesses && lastAnswerResult.detected_weaknesses.length > 0 ? (
                  <ul className="space-y-2 text-xs text-white/70">
                    {lastAnswerResult.detected_weaknesses.map((w: string, i: number) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-400/80 mt-1.5 shrink-0" />
                        <span className="leading-relaxed">{w}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-white/40 italic">
                    No significant deficiencies observed.
                  </p>
                )}
              </div>
            </div>

            {/* 9. Actionable Recommendations */}
            {((lastAnswerResult.recommendations && lastAnswerResult.recommendations.length > 0) ||
              (lastAnswerResult.structured_evaluation?.recommendations &&
                lastAnswerResult.structured_evaluation.recommendations.length > 0)) && (
              <div className="p-5 bg-teal-500/[0.03] border border-teal-500/20 rounded-xl space-y-3">
                <p className="font-semibold text-teal-400 text-xs md:text-sm flex items-center gap-2">
                  <Lightbulb className="w-4 h-4 text-teal-400" />
                  Actionable Recommendations for Subsequent Questions
                </p>
                <ul className="space-y-2 text-xs text-white/75">
                  {(
                    lastAnswerResult.recommendations ??
                    lastAnswerResult.structured_evaluation?.recommendations ??
                    []
                  ).map((rec: string, i: number) => (
                    <li key={i} className="flex items-start gap-2.5">
                      <span className="w-4 h-4 rounded-full bg-teal-500/20 text-teal-300 flex items-center justify-center text-[10px] font-mono font-bold shrink-0 mt-0.5 border border-teal-500/30">
                        {i + 1}
                      </span>
                      <span className="leading-relaxed">{rec}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 10. Competency-Level Evidence & Rubric Verification */}
            {lastAnswerResult.structured_evaluation?.competency_evidence &&
              lastAnswerResult.structured_evaluation.competency_evidence.length > 0 && (
                <div className="p-5 bg-[#0a0a0f] rounded-xl border border-white/[0.07] space-y-3">
                  <p className="text-[10px] font-mono font-semibold text-white/50 uppercase tracking-widest flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-emerald-400" />
                    Target Competency Verification & Evidence Rubrics
                  </p>
                  <div className="space-y-2.5">
                    {lastAnswerResult.structured_evaluation.competency_evidence.map((ev, i) => {
                      const status = ev.status || (ev.evidence_type === "direct" ? "demonstrated" : ev.evidence_type === "inferred" ? "partially_demonstrated" : "not_assessed");
                      return (
                        <div
                          key={i}
                          className="p-3.5 bg-white/[0.02] rounded-lg border border-white/[0.05] space-y-2"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-semibold text-white">
                              {ev.competency_name || ev.competency_id}
                            </span>
                            <div className="flex items-center gap-2">
                              {ev.score !== null && ev.score !== undefined && (
                                <span className="text-[10px] font-mono text-white/70">
                                  {Math.round(ev.score * 100)}%
                                </span>
                              )}
                              <span
                                className={`text-[10px] px-2 py-0.5 rounded font-mono font-medium border uppercase tracking-wider ${
                                  status === "demonstrated"
                                    ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                                    : status === "partially_demonstrated"
                                    ? "bg-sky-500/15 text-sky-300 border-sky-500/30"
                                    : status === "needs_improvement"
                                    ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
                                    : "bg-zinc-800 text-white/40 border-white/10"
                                }`}
                              >
                                {status.replace(/_/g, " ")}
                              </span>
                            </div>
                          </div>
                          {ev.excerpt && (
                            <div className="text-[11px] text-white/80 pl-2.5 border-l-2 border-emerald-500/60 italic leading-relaxed">
                              &quot;{ev.excerpt}&quot;
                            </div>
                          )}
                          <p className="text-xs text-white/50 leading-relaxed">{ev.reasoning}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

            {/* 11. Multi-modal Telemetry (Speech & Visual signals if available) */}
            {(lastAnswerResult.speech_metrics || lastAnswerResult.visual_metrics) && (
              <div className="p-4 bg-[#0a0a0f] rounded-xl border border-white/[0.07] space-y-2">
                <div className="text-[10px] font-mono font-semibold text-white/50 uppercase tracking-widest flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-teal-400" />
                  Multi-Modal Speech & Visual Telemetry
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  {lastAnswerResult.speech_metrics?.wpm !== undefined && (
                    <div className="p-2.5 bg-white/[0.02] rounded-lg border border-white/[0.05]">
                      <div className="text-[10px] text-white/40 font-mono">Speaking Rate</div>
                      <div className="font-mono text-white text-sm mt-0.5">
                        {Math.round(lastAnswerResult.speech_metrics.wpm)} <span className="text-[10px] text-white/40">WPM</span>
                      </div>
                    </div>
                  )}
                  {lastAnswerResult.speech_metrics?.pause_ratio !== undefined && (
                    <div className="p-2.5 bg-white/[0.02] rounded-lg border border-white/[0.05]">
                      <div className="text-[10px] text-white/40 font-mono">Pause Ratio</div>
                      <div className="font-mono text-white text-sm mt-0.5">
                        {Math.round(lastAnswerResult.speech_metrics.pause_ratio * 100)}%
                      </div>
                    </div>
                  )}
                  {lastAnswerResult.visual_metrics?.face_presence_ratio !== undefined && (
                    <div className="p-2.5 bg-white/[0.02] rounded-lg border border-white/[0.05]">
                      <div className="text-[10px] text-white/40 font-mono">Face Presence</div>
                      <div className="font-mono text-white text-sm mt-0.5">
                        {Math.round(lastAnswerResult.visual_metrics.face_presence_ratio * 100)}%
                      </div>
                    </div>
                  )}
                  {lastAnswerResult.visual_metrics?.posture_shifts !== undefined && (
                    <div className="p-2.5 bg-white/[0.02] rounded-lg border border-white/[0.05]">
                      <div className="text-[10px] text-white/40 font-mono">Posture Shifts</div>
                      <div className="font-mono text-white text-sm mt-0.5">
                        {lastAnswerResult.visual_metrics.posture_shifts}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 12. Evaluation Limitations & Verification Safeguards (if present) */}
            {lastAnswerResult.structured_evaluation?.evaluation_limitations &&
              lastAnswerResult.structured_evaluation.evaluation_limitations.length > 0 && (
                <div className="p-4 bg-zinc-950/80 border border-white/[0.05] rounded-xl space-y-1 text-xs text-white/50">
                  <span className="font-semibold text-white/60 block text-[10px] font-mono uppercase tracking-wider">
                    Evaluation Limitations & Observability Notes:
                  </span>
                  <ul className="list-disc pl-4 space-y-0.5 text-white/40">
                    {lastAnswerResult.structured_evaluation.evaluation_limitations.map((lim, i) => (
                      <li key={i}>{lim}</li>
                    ))}
                  </ul>
                </div>
              )}

            {/* 13. Proceed & Retry Action CTA */}
            <div className="pt-5 border-t border-white/[0.07] flex flex-col sm:flex-row items-center justify-between gap-3">
              <span className="text-xs text-white/40 font-mono">
                {lastAnswerResult.is_revision
                  ? `Revision answer record ${lastAnswerResult.answer_id} evaluated`
                  : `Answer record ${lastAnswerResult.answer_id} finalized`}
              </span>
              <div className="flex items-center gap-3 w-full sm:w-auto">
                <button
                  type="button"
                  onClick={handleRetry}
                  disabled={isRetrying}
                  className="w-full sm:w-auto px-5 py-2.5 rounded-xl border border-white/20 bg-white/[0.04] hover:bg-white/[0.08] hover:border-white/30 text-white font-medium transition-all flex items-center justify-center gap-2 text-sm disabled:opacity-50"
                >
                  <RotateCcw className={`w-4 h-4 text-teal-400 ${isRetrying ? "animate-spin" : ""}`} />
                  <span>{isRetrying ? "Preparing Retry..." : "Retry Answer"}</span>
                </button>
                <button
                  onClick={() => {
                    if (lastAnswerResult.completion_status === "completed") {
                      setAppState("COMPLETED");
                    } else if (lastAnswerResult.next_question) {
                      setQuestionPhase("SPEAKING");
                      setCurrentQuestion(lastAnswerResult.next_question);
                      setAppState("READY");
                    }
                  }}
                  className="w-full sm:w-auto bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-black px-6 py-2.5 rounded-xl font-semibold transition-all shadow-[0_0_20px_rgba(16,185,129,0.25)] flex items-center justify-center gap-2 text-sm"
                >
                  <span>
                    {lastAnswerResult.completion_status === "completed"
                      ? "Finish Interview Session"
                      : "Proceed to Next Question"}
                  </span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* INTERVIEW COMPLETED VIEW                                       */}
        {/* ============================================================== */}
        {appState === "COMPLETED" && (
          <div className="p-8 md:p-12 border border-white/[0.07] rounded-2xl text-center space-y-6 bg-zinc-950/80 backdrop-blur-xl shadow-2xl relative overflow-hidden">
            <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400 shadow-[0_0_30px_rgba(16,185,129,0.2)]">
              <CheckCircle className="w-8 h-8" />
            </div>
            <div className="space-y-2">
              <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-white">Interview Completed</h2>
              <p className="text-white/50 max-w-md mx-auto text-xs md:text-sm leading-relaxed">
                Congratulations on completing the interview session. All responses, multi-modal evidence, and competency benchmarks have been securely evaluated.
              </p>
            </div>
            <button
              onClick={resetInterview}
              className="bg-white text-black hover:bg-white/90 px-8 py-3 rounded-xl font-semibold transition-all inline-flex items-center gap-2 text-sm shadow-lg hover:-translate-y-0.5 active:translate-y-0"
            >
              <RotateCcw className="w-4 h-4" />
              <span>Start New Interview</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
