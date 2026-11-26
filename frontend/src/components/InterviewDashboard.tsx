"use client";

import React from "react";
import { AlertCircle, Sparkles, Volume2, ArrowRight } from "lucide-react";
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

  const [questionPhase, setQuestionPhase] = React.useState<"SPEAKING" | "READY_TO_ANSWER">("SPEAKING");

  // Acoustic guard delay: wait 500ms after audio ends so room echo/speakers are quiet before mic opens
  const handleSpeechConcluded = React.useCallback(() => {
    setTimeout(() => {
      setQuestionPhase("READY_TO_ANSWER");
    }, 500);
  }, []);

  const liveAvatar = useLiveAvatar({
    onSpeechStart: () => setQuestionPhase("SPEAKING"),
    onSpeechEnd: handleSpeechConcluded,
  });

  const avatarVoice = useAvatarVoice(undefined, false, {
    onSpeechStart: () => setQuestionPhase("SPEAKING"),
    onSpeechEnd: handleSpeechConcluded,
  });

  // Single authoritative source of truth: is the avatar speaking right now?
  const isAvatarSpeaking = Boolean(
    (liveAvatar.isConfigured && liveAvatar.hasActiveStream && liveAvatar.state === "SPEAKING") ||
    avatarVoice.isSpeaking
  );

  const lastSpokenQuestionIdRef = React.useRef<string | null>(null);
  const isFirstQuestionRef = React.useRef<boolean>(true);
  const hasSpokenCompletionRef = React.useRef<boolean>(false);

  // Authoritative speech pipeline: speaks directly via single-channel Neural Voice
  const articulatePrompt = React.useCallback(
    async (promptText: string) => {
      // 1. Immediately halt any previous speech to eliminate overlapping voice
      if (liveAvatar.isConfigured) {
        liveAvatar.interrupt();
      }
      avatarVoice.stopSpeaking();

      // 2. Authoritative speech articulation via Edge-TTS & Web Audio Analyser
      console.log("[Audio Pipeline] Articulating via Neural Voice & 3D WebGL Avatar...");
      await avatarVoice.speakText(promptText);
    },
    [liveAvatar, avatarVoice]
  );

  // When a new question arrives in READY state, articulate it exactly once
  React.useEffect(() => {
    if (appState === "READY" && currentQuestion) {
      if (lastSpokenQuestionIdRef.current !== currentQuestion.id) {
        lastSpokenQuestionIdRef.current = currentQuestion.id;
        setQuestionPhase("SPEAKING");

        let spokenPrompt = currentQuestion.question_text;
        if (isFirstQuestionRef.current) {
          isFirstQuestionRef.current = false;
          spokenPrompt = `Hello, and welcome! I am Zaira, your AI interviewer today. To get started: ${currentQuestion.question_text}`;
        }

        articulatePrompt(spokenPrompt);
      }
    }
  }, [appState, currentQuestion, articulatePrompt]);

  // Articulate concluding remarks when interview completes
  React.useEffect(() => {
    if (appState === "COMPLETED" && !hasSpokenCompletionRef.current) {
      hasSpokenCompletionRef.current = true;
      const closingMsg =
        "Thank you so much for your time and thoughtful responses today. That concludes our interview session. Your detailed performance evaluation and rubric feedback are now ready for your review.";
      articulatePrompt(closingMsg);
    }
  }, [appState, articulatePrompt]);

  const handleStopSpeaking = React.useCallback(() => {
    if (liveAvatar.isConfigured) {
      liveAvatar.interrupt();
    }
    avatarVoice.stopSpeaking();
    setQuestionPhase("READY_TO_ANSWER");
  }, [liveAvatar, avatarVoice]);

  const handleReplayQuestion = React.useCallback(() => {
    if (!currentQuestion) return;
    setQuestionPhase("SPEAKING");
    articulatePrompt(currentQuestion.question_text);
  }, [currentQuestion, articulatePrompt]);

  const handleStart = () => {
    setQuestionPhase("SPEAKING");
    startSession();
  };

  const handleReset = () => {
    lastSpokenQuestionIdRef.current = null;
    isFirstQuestionRef.current = true;
    hasSpokenCompletionRef.current = false;
    if (liveAvatar.isConfigured) {
      liveAvatar.disconnect();
    }
    avatarVoice.stopSpeaking();
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
    <div className="min-h-screen bg-[#030407] text-white">
      {/* Global Session Error Banner */}
      {errorMsg && (
        <div className="bg-red-500/10 border-b border-red-500/20 px-4 py-3 text-red-400 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2 max-w-4xl mx-auto w-full">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        </div>
      )}

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 py-8 space-y-6">
        {/* ============================================================== */}
        {/* VIEW 1: CONFIGURATION / ONBOARDING SCREEN                       */}
        {/* ============================================================== */}
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
              <div className="absolute inset-0 rounded-full border-2 border-teal-500/20 animate-ping pointer-events-none" />
              <div className="w-14 h-14 rounded-full border-2 border-teal-500/30 border-t-teal-400 animate-spin flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-teal-400" />
              </div>
            </div>
            <div className="space-y-1.5 max-w-md">
              <h2 className="text-lg font-semibold text-white tracking-tight">
                Initializing Interview Session
              </h2>
              <p className="text-xs text-white/50 leading-relaxed">
                Formulating your calibrated opening question...
              </p>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* ACTIVE INTERVIEW WORKFLOW                                       */}
        {/* ============================================================== */}
        {(appState === "READY" || appState === "PROCESSING") && currentQuestion && (
          <div className="space-y-6">
            {questionPhase === "SPEAKING" ? (
              /* ============================================================== */
              /* STAGE 1: EXAMINER SPEAKS FIRST                                 */
              /* ============================================================== */
              <div className="max-w-4xl mx-auto space-y-5 animate-fadeIn">
                {/* Active Examiner Speaking Banner */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl bg-teal-500/[0.08] border border-teal-500/30 shadow-lg">
                  <div className="flex items-center gap-3">
                    <span
                      className={`w-3 h-3 rounded-full shrink-0 ${
                        isAvatarSpeaking ? "bg-emerald-400 animate-pulse" : "bg-teal-400"
                      }`}
                    />
                    <div>
                      <div className="text-xs font-mono font-bold text-teal-300 uppercase tracking-wider flex items-center gap-2">
                        <span>
                          {liveAvatar.state === "CONNECTING"
                            ? "Connecting Video Stream"
                            : isAvatarSpeaking
                            ? "Interviewer Speaking"
                            : "Interviewer Ready"}
                        </span>
                        <span className="text-white/30">•</span>
                        <span className="text-white/70 font-normal">Zaira</span>
                      </div>
                      <p className="text-xs text-zinc-300 mt-0.5">
                        Please listen attentively. When Zaira finishes, your microphone will open for your response.
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
                  isSpeaking={isAvatarSpeaking}
                  isListening={false}
                  isThinking={false}
                  analyserNode={avatarVoice.analyserNode}
                  audioElement={avatarVoice.audioElement}
                  wordTimings={avatarVoice.wordTimings}
                  spokenText={avatarVoice.spokenText}
                  speechGeneration={avatarVoice.speechGeneration}
                  currentWord={avatarVoice.activeWord}
                  onSkip={handleStopSpeaking}
                  onSpeechEnd={handleSpeechConcluded}
                  questionId={currentQuestion.id}
                  liveVideoRef={liveAvatar.attachVideo}
                  isLiveAvatarConnected={liveAvatar.state === "CONNECTED" || liveAvatar.state === "SPEAKING"}
                  isLiveAvatarConfigured={liveAvatar.isConfigured}
                  liveAvatarState={liveAvatar.state}
                  statusMessage={liveAvatar.statusMessage}
                  hasActiveStream={liveAvatar.hasActiveStream}
                  onReconnect={() => liveAvatar.connect()}
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
                      <span>Replay Question Voice</span>
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

                  {/* Right Column (4 cols): Attentive Examiner */}
                  <div className="lg:col-span-4 space-y-4">
                    <InterviewerAvatar
                      mode="compact"
                      isSpeaking={isAvatarSpeaking}
                      isListening={appState !== "PROCESSING"}
                      isThinking={appState === "PROCESSING"}
                      analyserNode={avatarVoice.analyserNode}
                      audioElement={avatarVoice.audioElement}
                      wordTimings={avatarVoice.wordTimings}
                      spokenText={avatarVoice.spokenText}
                      speechGeneration={avatarVoice.speechGeneration}
                      currentWord={avatarVoice.activeWord}
                      onSkip={handleStopSpeaking}
                      onSpeechEnd={handleSpeechConcluded}
                      questionId={currentQuestion.id}
                      liveVideoRef={liveAvatar.attachVideo}
                      isLiveAvatarConnected={liveAvatar.state === "CONNECTED" || liveAvatar.state === "SPEAKING"}
                      isLiveAvatarConfigured={liveAvatar.isConfigured}
                      liveAvatarState={liveAvatar.state}
                      statusMessage={liveAvatar.statusMessage}
                      hasActiveStream={liveAvatar.hasActiveStream}
                      onReconnect={() => liveAvatar.connect()}
                    />

                    {/* Examiner Protocol Card */}
                    <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.08] space-y-2 text-xs">
                      <div className="font-semibold text-white flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-teal-400" />
                        <span>Adaptive Rubric Evaluation</span>
                      </div>
                      <p className="text-zinc-400 leading-relaxed text-[11px]">
                        Speak clearly and structure your explanation logically. Zaira evaluates factual depth, practical context, and clarity.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ============================================================== */}
        {/* VIEW 3: STRUCTURED RUBRIC RESULT MODAL / PANEL                  */}
        {/* ============================================================== */}
        {appState === "ANSWER_RESULT" && lastAnswerResult && (
          <EvaluationPanel
            lastAnswerResult={lastAnswerResult}
            currentQuestion={currentQuestion}
            handleRetry={handleRetryAction}
            isRetrying={isRetrying}
            onProceed={handleProceed}
          />
        )}

        {/* ============================================================== */}
        {/* VIEW 4: FINAL INTERVIEW COMPLETED REPORT CARD                   */}
        {/* ============================================================== */}
        {appState === "COMPLETED" && (
          <InterviewCompleted
            sessionId={sessionId}
            onReset={handleReset}
          />
        )}
      </main>
    </div>
  );
}
