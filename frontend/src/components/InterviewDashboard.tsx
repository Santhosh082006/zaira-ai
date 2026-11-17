"use client";

import React from "react";
import { AlertCircle, Sparkles, Volume2, VolumeX, X, ArrowRight } from "lucide-react";
import { AudioRecorder } from "./AudioRecorder";
import { InterviewerAvatar } from "./InterviewerAvatar";
import { InterviewConfig } from "./interview/InterviewConfig";
import { EvaluationPanel } from "./interview/EvaluationPanel";
import { InterviewCompleted } from "./interview/InterviewCompleted";
import { useInterviewSession } from "../hooks/useInterviewSession";
import { useAvatarVoice } from "../hooks/useAvatarVoice";
import { useLiveAvatar } from "../hooks/useLiveAvatar";

export default function InterviewDashboard() {
  const {
    appState,
    sessionId,
    currentQuestion,
    errorMsg,
    lastAnswerResult,
    isRetrying,
    liveFeedback,
    evalStreaming,
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
    startSession,
    submitAudioAnswer,
    retryAnalysis,
    retryQuestion,
    proceedToNext,
    sendLiveTranscript,
    resetSession,
    retryCurrentQuestion,
  } = useInterviewSession();

  const handleLiveSpeechStart = React.useCallback(() => {
    setQuestionPhase("SPEAKING");
  }, []);

  const handleLiveSpeechEnd = React.useCallback(() => {
    setQuestionPhase("READY_TO_ANSWER");
  }, []);

  const liveAvatar = useLiveAvatar({
    onSpeechStart: handleLiveSpeechStart,
    onSpeechEnd: handleLiveSpeechEnd,
  });

  const {
    questionPhase,
    setQuestionPhase,
    speechFailed,
    activeWord,
    questionAudioBlob,
    speakQuestion,
    stopSpeaking,
    replayQuestion,
    handleAvatarSpeechEnd,
    resetVoiceState,
  } = useAvatarVoice(currentQuestion, appState === "READY" && !liveAvatar.isConfigured);

  const lastSpokenQuestionIdRef = React.useRef<string | null>(null);
  const isFirstQuestionRef = React.useRef<boolean>(true);
  const hasSpokenCompletionRef = React.useRef<boolean>(false);

  // When a new question arrives and LiveAvatar Lite is configured, articulate it via WebRTC
  React.useEffect(() => {
    if (appState === "READY" && currentQuestion) {
      if (lastSpokenQuestionIdRef.current !== currentQuestion.id) {
        lastSpokenQuestionIdRef.current = currentQuestion.id;
        setQuestionPhase("SPEAKING");

        // Format spoken prompt with professional warm greeting on opening question
        let spokenPrompt = currentQuestion.question_text;
        if (isFirstQuestionRef.current) {
          isFirstQuestionRef.current = false;
          spokenPrompt = `Hello, and welcome! I am Zaira, your AI interviewer today. To get started: ${currentQuestion.question_text}`;
        }

        if (liveAvatar.isConfigured) {
          liveAvatar
            .speakText(spokenPrompt)
            .then((ok) => {
              if (!ok) {
                console.warn("LiveAvatar speech returned false, falling back to neural TTS");
                speakQuestion(currentQuestion);
              }
            })
            .catch((err) => {
              console.warn("LiveAvatar speech error, falling back to neural TTS:", err);
              speakQuestion(currentQuestion);
            });
        }
      }
    }
  }, [appState, currentQuestion, liveAvatar.isConfigured, liveAvatar.speakText, speakQuestion, setQuestionPhase]);

  // Articulate concluding remarks when interview completes
  React.useEffect(() => {
    if (appState === "COMPLETED" && !hasSpokenCompletionRef.current) {
      hasSpokenCompletionRef.current = true;
      const closingMsg =
        "Thank you so much for your time and thoughtful responses today. That concludes our interview session. Your detailed performance evaluation and rubric feedback are now ready for your review.";
      if (liveAvatar.isConfigured) {
        liveAvatar.speakText(closingMsg).catch((err) => {
          console.warn("Closing speech notice:", err);
        });
      }
    }
  }, [appState, liveAvatar.isConfigured, liveAvatar.speakText]);

  const handleStopSpeaking = React.useCallback(() => {
    if (liveAvatar.isConfigured) {
      liveAvatar.interrupt();
    }
    stopSpeaking();
    setQuestionPhase("READY_TO_ANSWER");
  }, [liveAvatar, stopSpeaking, setQuestionPhase]);

  const handleReplayQuestion = React.useCallback(() => {
    if (!currentQuestion) return;
    setQuestionPhase("SPEAKING");
    if (liveAvatar.isConfigured) {
      liveAvatar.speakText(currentQuestion.question_text).catch(() => {
        replayQuestion();
      });
    } else {
      replayQuestion();
    }
  }, [currentQuestion, liveAvatar, replayQuestion, setQuestionPhase]);

  const handleStart = () => {
    setQuestionPhase("SPEAKING");
    if (liveAvatar.isConfigured) {
      liveAvatar.connect().catch((err) => {
        console.warn("LiveAvatar session connection notice:", err);
      });
    }
    startSession();
  };

  const handleReset = () => {
    lastSpokenQuestionIdRef.current = null;
    isFirstQuestionRef.current = true;
    hasSpokenCompletionRef.current = false;
    if (liveAvatar.isConfigured) {
      liveAvatar.disconnect();
    }
    resetVoiceState();
    resetSession();
  };

  const handleAudioSubmit = (mediaBlob: Blob) => {
    submitAudioAnswer(mediaBlob, handleStopSpeaking);
  };

  const handleProceed = () => {
    proceedToNext(() => {
      setQuestionPhase("SPEAKING");
    });
  };

  const handleRetryAction = () => {
    retryQuestion(() => {
      setQuestionPhase("READY_TO_ANSWER");
    });
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
              onClick={handleReset}
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
                    onClick={retryCurrentQuestion}
                    className="px-4 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-xs font-medium transition-colors text-white"
                  >
                    Retry Current Question
                  </button>
                )}
                <button
                  onClick={handleReset}
                  className="px-4 py-1.5 bg-red-500/20 hover:bg-red-500/30 rounded-lg text-xs font-medium transition-colors text-white"
                >
                  Start New Interview
                </button>
              </div>
            )}
            {appState === "EVAL_ERROR" && (
              <div className="flex justify-end gap-3 pt-2 border-t border-red-500/20">
                <button
                  onClick={retryAnalysis}
                  className="px-4 py-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/30 rounded-lg text-xs font-medium transition-colors text-emerald-300"
                >
                  Retry Evaluation
                </button>
                <button
                  onClick={retryCurrentQuestion}
                  className="px-4 py-1.5 bg-white/10 hover:bg-white/20 rounded-lg text-xs font-medium transition-colors text-white"
                >
                  Record New Answer
                </button>
              </div>
            )}
          </div>
        )}

        {/* Configuration Flow */}
        {appState === "CONFIG" && (
          <InterviewConfig
            interviewType={interviewType}
            setInterviewType={setInterviewType}
            technicalDomain={technicalDomain}
            setTechnicalDomain={setTechnicalDomain}
            customGoal={customGoal}
            setCustomGoal={setCustomGoal}
            resumeText={resumeText}
            setResumeText={setResumeText}
            jobDescription={jobDescription}
            setJobDescription={setJobDescription}
            interviewLevel={interviewLevel}
            setInterviewLevel={setInterviewLevel}
            assessmentGoals={assessmentGoals}
            toggleGoal={toggleGoal}
            onStart={handleStart}
            isLiveAvatarConfigured={liveAvatar.isConfigured}
          />
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
        {/* BRITISH COUNCIL IELTS SPEAKING MODULE WORKFLOW                  */}
        {/* ============================================================== */}
        {(appState === "READY" || appState === "PROCESSING") && currentQuestion && (
          <div className="space-y-6">
            {questionPhase === "SPEAKING" ? (
              /* ============================================================== */
              /* STAGE 1: BRITISH COUNCIL EXAMINER SPEAKS FIRST                 */
              /* ============================================================== */
              <div className="max-w-4xl mx-auto space-y-5 animate-fadeIn">
                {/* Active Examiner Speaking Banner */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl bg-teal-500/[0.08] border border-teal-500/30 shadow-lg">
                  <div className="flex items-center gap-3">
                    <span className="w-3 h-3 rounded-full bg-teal-400 animate-pulse shrink-0" />
                    <div>
                      <div className="text-xs font-mono font-bold text-teal-300 uppercase tracking-wider flex items-center gap-2">
                        <span>Interviewer Speaking</span>
                        <span className="text-white/30">•</span>
                        <span className="text-white/70 font-normal">Zaira</span>
                      </div>
                      <p className="text-xs text-zinc-300 mt-0.5">
                        Please listen attentively. As soon as Zaira concludes, your answer recording will begin.
                      </p>
                    </div>
                  </div>

                  <button
                    onClick={handleStopSpeaking}
                    className="px-4 py-2.5 rounded-xl text-xs font-semibold bg-teal-500 hover:bg-teal-400 text-black transition-all flex items-center justify-center gap-2 shadow-lg hover:scale-105 active:scale-95 shrink-0 font-mono"
                  >
                    <span>I&apos;m Ready to Answer</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Hero Examiner Stage */}
                <InterviewerAvatar
                  mode="hero"
                  isSpeaking={liveAvatar.isConfigured ? liveAvatar.state === "SPEAKING" : true}
                  isThinking={false}
                  onSkip={handleStopSpeaking}
                  onSpeechEnd={liveAvatar.isConfigured ? handleLiveSpeechEnd : handleAvatarSpeechEnd}
                  audioBlob={liveAvatar.isConfigured ? null : questionAudioBlob}
                  currentWord={liveAvatar.isConfigured ? undefined : activeWord}
                  questionId={currentQuestion.id}
                  liveVideoRef={liveAvatar.attachVideo}
                  isLiveAvatarConnected={liveAvatar.state === "CONNECTED" || liveAvatar.state === "SPEAKING"}
                  isLiveAvatarConfigured={liveAvatar.isConfigured}
                  liveAvatarState={liveAvatar.state}
                  statusMessage={liveAvatar.statusMessage}
                  hasActiveStream={liveAvatar.hasActiveStream}
                />

                {/* Spoken Question Text Subtitle Card */}
                <div className="p-6 md:p-7 rounded-2xl bg-zinc-950/80 border border-white/10 backdrop-blur-xl text-center space-y-2 shadow-xl">
                  <div className="flex items-center justify-center gap-2 text-[11px] font-mono uppercase tracking-widest text-teal-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-teal-400" />
                    <span>Interview Question Prompt</span>
                  </div>
                  <h2 className="text-lg md:text-xl font-medium leading-relaxed text-white max-w-2xl mx-auto">
                    &ldquo;{currentQuestion.question_text}&rdquo;
                  </h2>
                  {speechFailed && (
                    <p className="text-xs text-amber-400/90 pt-1">
                      Note: Audio playback was blocked by browser. You can read the question prompt above and click &apos;I&apos;m Ready to Answer&apos;.
                    </p>
                  )}
                </div>
              </div>
            ) : (
              /* ============================================================== */
              /* STAGE 2: QUESTION IN TEXT FORMAT & CANDIDATE RECORDING STARTS   */
              /* ============================================================== */
              <div className="space-y-6 animate-fadeIn">
                {/* Large Text Format Question Banner */}
                <div className="p-6 md:p-8 rounded-3xl bg-zinc-950/90 border border-teal-500/30 shadow-[0_0_40px_rgba(20,184,166,0.12)] space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/[0.08] pb-4">
                    <div className="flex items-center gap-2.5">
                      <span className="px-3 py-1 rounded-lg bg-red-500/15 border border-red-500/30 text-red-400 text-xs font-mono font-semibold flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
                        <span>Candidate Response Stage</span>
                      </span>
                      <span className="text-xs text-white/30">•</span>
                      <span className="text-xs font-mono text-zinc-400 uppercase tracking-wider">
                        {interviewType} Interview
                      </span>
                      {technicalDomain && interviewType === "technical" && (
                        <>
                          <span className="text-white/30">•</span>
                          <span className="text-xs font-mono text-teal-400">{technicalDomain}</span>
                        </>
                      )}
                    </div>

                    <button
                      onClick={handleReplayQuestion}
                      className="self-start sm:self-auto flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-medium bg-white/[0.05] hover:bg-white/[0.1] text-zinc-200 hover:text-white border border-white/10 transition-all"
                      aria-label="Replay examiner question"
                    >
                      <Volume2 className="w-3.5 h-3.5 text-teal-400" />
                      <span>Replay Examiner Voice</span>
                    </button>
                  </div>

                  <div>
                    <span className="text-[11px] font-mono uppercase tracking-widest text-teal-400/90 font-medium">
                      Question Prompt:
                    </span>
                    <h2 className="text-xl md:text-2xl font-semibold leading-relaxed text-white mt-1">
                      {currentQuestion.question_text}
                    </h2>
                  </div>
                </div>

                {/* Main Split Grid: Left Candidate Recording Console (8 cols), Right Attentive Examiner (4 cols) */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                  {/* Left Column (8 cols): Candidate Live Webcam & Mic Recording */}
                  <div className="lg:col-span-8 space-y-4">
                    <AudioRecorder
                      key={currentQuestion.id}
                      questionId={currentQuestion.id}
                      autoStart={true}
                      onRecordingStart={handleStopSpeaking}
                      onRecordingComplete={handleAudioSubmit}
                      onLiveTranscriptUpdate={sendLiveTranscript}
                      liveFeedback={liveFeedback}
                      evalStreaming={evalStreaming}
                      isProcessing={appState === "PROCESSING"}
                      disabled={appState === "PROCESSING"}
                    />
                  </div>

                  {/* Right Column (4 cols): Attentive British Council Examiner */}
                  <div className="lg:col-span-4 space-y-4">
                    <InterviewerAvatar
                      mode="compact"
                      isSpeaking={liveAvatar.isConfigured ? liveAvatar.state === "SPEAKING" : false}
                      isThinking={appState === "PROCESSING"}
                      onSkip={handleStopSpeaking}
                      audioBlob={null}
                      questionId={currentQuestion.id}
                      liveVideoRef={liveAvatar.attachVideo}
                      isLiveAvatarConnected={liveAvatar.state === "CONNECTED" || liveAvatar.state === "SPEAKING"}
                      isLiveAvatarConfigured={liveAvatar.isConfigured}
                      liveAvatarState={liveAvatar.state}
                      statusMessage={liveAvatar.statusMessage}
                      hasActiveStream={liveAvatar.hasActiveStream}
                    />

                    {/* Examiner Protocol Card */}
                    <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.08] space-y-2 text-xs">
                      <div className="font-semibold text-white flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-teal-400" />
                        <span>Evaluation In Progress</span>
                      </div>
                      <p className="text-zinc-400 leading-relaxed text-[11px]">
                        Zaira is listening to your answer. Your speech will be evaluated on technical depth, fluency, lexical precision, and logical structure.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Answer Result View — Evaluation Report */}
        {appState === "ANSWER_RESULT" && lastAnswerResult && (
          <EvaluationPanel
            lastAnswerResult={lastAnswerResult}
            currentQuestion={currentQuestion}
            handleRetry={handleRetryAction}
            isRetrying={isRetrying}
            onProceed={handleProceed}
          />
        )}

        {/* Interview Completed View */}
        {appState === "COMPLETED" && (
          <InterviewCompleted sessionId={sessionId} onReset={handleReset} />
        )}
      </div>
    </div>
  );
}
