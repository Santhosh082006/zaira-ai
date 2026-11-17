"use client";

import React from "react";
import {
  Mic,
  Square,
  Trash2,
  Loader2,
  Video,
  Check,
  Lightbulb,
  CheckCircle2,
  Sparkles,
  Activity,
  Brain,
  ShieldCheck,
} from "lucide-react";
import {
  useAudioRecorder,
  RecorderState,
} from "../hooks/useAudioRecorder";
import { EvalStreamingState } from "../hooks/useInterviewSession";

export type { RecorderState };

export interface LiveFeedbackData {
  word_count: number;
  concepts_covered: string[];
  concepts_missing: string[];
  pacing_status: string;
  coaching_hint: string;
}

interface AudioRecorderProps {
  onRecordingComplete: (blob: Blob) => void;
  onRecordingStart?: () => void;
  onLiveTranscriptUpdate?: (transcript: string, isFinal: boolean) => void;
  liveFeedback?: LiveFeedbackData | null;
  evalStreaming?: EvalStreamingState | null;
  isProcessing: boolean;
  disabled: boolean;
  questionId: string;
  autoStart?: boolean;
}

export function AudioRecorder({
  onRecordingComplete,
  onRecordingStart,
  onLiveTranscriptUpdate,
  liveFeedback,
  evalStreaming,
  isProcessing,
  disabled,
  autoStart = false,
}: AudioRecorderProps) {
  const {
    effectiveState,
    errorMsg,
    recordingTime,
    hasCamera,
    mediaPreviewUrl,
    finalTranscript,
    interimTranscript,
    speechRecognitionSupported,
    videoRef,
    startRecording,
    stopRecording,
    handleReset,
    handleSubmit,
    formatTime,
    isControlsDisabled,
    liveWordCount,
    liveWpm,
  } = useAudioRecorder({
    onRecordingComplete,
    onRecordingStart,
    onLiveTranscriptUpdate,
    isProcessing,
    disabled,
    autoStart,
  });

  return (
    <div className="tl-card p-5 md:p-6 text-white space-y-4 rounded-2xl border border-white/[0.08] shadow-2xl">
      {/* Live Camera / Audio Preview Window */}
      <div className="relative rounded-xl overflow-hidden bg-[#07080c] aspect-video border border-white/[0.08] shadow-inner flex items-center justify-center">
        {hasCamera ? (
          effectiveState === "RECORDED" && mediaPreviewUrl ? (
            <video
              src={mediaPreviewUrl}
              controls
              playsInline
              className="w-full h-full object-cover"
            />
          ) : (
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-cover transform scale-x-[-1]"
            />
          )
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center p-8 text-center text-zinc-400 bg-white/[0.02] space-y-3">
            <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
              <Mic className="w-7 h-7 text-emerald-400 animate-pulse" />
            </div>
            <div>
              <p className="text-sm font-semibold text-zinc-200">Microphone Audio Mode Active</p>
              <p className="text-xs text-zinc-500 mt-0.5">Camera preview unavailable or disabled on this device</p>
            </div>
            {effectiveState === "RECORDED" && mediaPreviewUrl && (
              <audio src={mediaPreviewUrl} controls className="w-full max-w-md mt-4" />
            )}
          </div>
        )}

        {/* HUD Status Overlay (Top-Left) */}
        <div className="absolute top-3 left-3 bg-[#050508]/85 backdrop-blur-md px-3 py-1.5 rounded-full border border-white/[0.08] flex items-center gap-2 shadow-lg z-20">
          {effectiveState === "RECORDING" ? (
            <>
              <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <span className="text-xs font-mono font-bold text-red-400 tracking-wider">
                REC {formatTime(recordingTime)}
              </span>
            </>
          ) : effectiveState === "RECORDED" ? (
            <>
              <div className="w-2 h-2 rounded-full bg-sky-400" />
              <span className="text-xs font-mono font-semibold text-sky-300 tracking-wider">
                RECORDED ({formatTime(recordingTime)})
              </span>
            </>
          ) : effectiveState === "PROCESSING" ? (
            <>
              <Loader2 className="w-3 h-3 text-emerald-400 animate-spin" />
              <span className="text-xs font-mono font-semibold text-emerald-300 tracking-wider">
                EVALUATING
              </span>
            </>
          ) : (
            <>
              <div className="w-2 h-2 rounded-full bg-emerald-400 tl-animate-pulse" />
              <span className="text-xs font-mono font-semibold text-zinc-300 tracking-wider">
                {hasCamera ? "CAMERA & MIC ACTIVE" : "MIC ACTIVE"}
              </span>
            </>
          )}
        </div>

        {/* Live Metrics HUD (Top-Right, while recording) */}
        {effectiveState === "RECORDING" && liveWordCount > 0 && (
          <div className="absolute top-3 right-3 bg-[#050508]/85 backdrop-blur-md px-3 py-1 rounded-full border border-white/[0.08] flex items-center gap-3 text-[11px] font-mono text-zinc-300 shadow-lg z-20">
            <span>{liveWordCount} words</span>
            <span className="text-white/20">•</span>
            <span className={liveWpm > 185 ? "text-amber-400" : liveWpm < 85 ? "text-sky-400" : "text-emerald-400"}>
              {liveWpm} WPM
            </span>
          </div>
        )}
      </div>

      {/* Real-time Streaming Transcription Stage */}
      {effectiveState === "RECORDING" && (
        <div className="p-4 rounded-xl border border-white/[0.08] bg-[#0a0a0f] space-y-2.5 animate-fadeIn">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[10px] font-mono uppercase tracking-widest text-emerald-400 font-semibold">
                Live Speech Recognition
              </span>
            </div>
            <span className="text-[10px] text-zinc-500 font-mono">
              {speechRecognitionSupported ? "Real-time streaming" : "Fallback mode active"}
            </span>
          </div>

          <div className="text-xs md:text-sm leading-relaxed min-h-[44px] max-h-28 overflow-y-auto pl-3 border-l-2 border-emerald-500/50">
            {finalTranscript && (
              <span className="text-zinc-100 font-normal">{finalTranscript} </span>
            )}
            {interimTranscript && (
              <span className="text-emerald-300/80 italic">{interimTranscript}</span>
            )}
            {!finalTranscript && !interimTranscript && (
              <span className="text-zinc-500 italic">
                {speechRecognitionSupported
                  ? "Speak your response into the microphone... Words will stream in real-time."
                  : "Streaming transcription preview is not supported by your browser. Your complete audio/video is being recorded for neural Whisper analysis."}
              </span>
            )}
            <span className="inline-block w-1.5 h-3.5 bg-emerald-400 animate-pulse ml-1 align-middle" />
          </div>

          {/* Real-Time Live Coaching Feedback Pill Tray */}
          {liveFeedback && (
            <div className="pt-2 border-t border-white/[0.06] space-y-2">
              {/* Concept Coverage Checklist */}
              {(liveFeedback.concepts_covered.length > 0 || liveFeedback.concepts_missing.length > 0) && (
                <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
                  {liveFeedback.concepts_covered.map((concept, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-medium"
                    >
                      <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                      <span>{concept}</span>
                    </span>
                  ))}
                  {liveFeedback.concepts_missing.slice(0, 2).map((concept, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-white/[0.03] text-zinc-400 border border-white/10 font-medium"
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400/70" />
                      <span>{concept}</span>
                    </span>
                  ))}
                </div>
              )}

              {/* Actionable Live Hint */}
              {liveFeedback.coaching_hint && (
                <div className="p-2.5 rounded-lg bg-emerald-950/20 border border-emerald-500/20 flex items-start gap-2 text-xs text-emerald-200/90 leading-relaxed">
                  <Lightbulb className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <span>{liveFeedback.coaching_hint}</span>
                    <span className="block text-[9px] font-mono text-emerald-400/50 uppercase tracking-widest mt-0.5">
                      Provisional Live Guidance
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Recording Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
        <div className="flex items-center gap-2.5">
          {effectiveState === "RECORDING" && <div className="w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse" />}
          <span className="text-xs md:text-sm text-zinc-300 font-medium">
            {effectiveState === "IDLE" && (hasCamera ? "Ready to record video & audio response" : "Ready to record audio response")}
            {effectiveState === "RECORDING" && `Recording live answer: ${formatTime(recordingTime)}`}
            {effectiveState === "RECORDED" && "Answer recorded. Review playback or submit for evaluation."}
            {effectiveState === "PROCESSING" && "Evaluating candidate answer and competency markers..."}
            {effectiveState === "ERROR" && "Recording error occurred"}
          </span>
        </div>

        <div className="flex items-center gap-2.5">
          {effectiveState === "IDLE" && (
            <button
              onClick={startRecording}
              disabled={isControlsDisabled}
              className="flex items-center gap-2 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 disabled:opacity-50 text-black px-5 py-2.5 rounded-xl font-semibold transition-all shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:scale-[1.01] active:scale-[0.99] text-xs md:text-sm"
            >
              <Video className="w-4 h-4 text-black" />
              <span>Record Answer</span>
            </button>
          )}

          {effectiveState === "RECORDING" && (
            <button
              onClick={stopRecording}
              className="flex items-center gap-2 bg-red-600 hover:bg-red-500 text-white px-5 py-2.5 rounded-xl font-semibold transition-all shadow-[0_0_20px_rgba(239,68,68,0.35)] animate-pulse text-xs md:text-sm"
            >
              <Square className="w-4 h-4" />
              <span>Stop Recording</span>
            </button>
          )}

          {(effectiveState === "RECORDED" || effectiveState === "ERROR") && (
            <button
              onClick={handleReset}
              disabled={isControlsDisabled}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs md:text-sm font-medium border border-white/10 hover:border-white/20 hover:bg-white/5 transition-all text-zinc-300"
            >
              <Trash2 className="w-4 h-4" />
              <span>Rerecord</span>
            </button>
          )}

          {effectiveState === "RECORDED" && (
            <button
              onClick={handleSubmit}
              disabled={isControlsDisabled}
              className="bg-gradient-to-r from-emerald-400 to-emerald-500 hover:from-emerald-300 hover:to-emerald-400 text-black px-6 py-2.5 rounded-xl font-semibold transition-all disabled:opacity-50 flex items-center gap-2 shadow-[0_0_24px_rgba(16,185,129,0.35)] hover:scale-[1.01] active:scale-[0.99] text-xs md:text-sm"
            >
              <Check className="w-4 h-4 stroke-[3]" />
              <span>Submit Answer</span>
            </button>
          )}
        </div>
      </div>

      {errorMsg && (
        <div className="text-xs text-red-300 bg-red-500/10 p-3 rounded-xl border border-red-500/20">
          {errorMsg}
        </div>
      )}

      {(effectiveState === "PROCESSING" || evalStreaming?.isEvaluating) && (
        <div className="p-4 rounded-xl border border-emerald-500/30 bg-[#080d14]/90 backdrop-blur-md space-y-3.5 animate-fadeIn">
          {/* Header & Stage Badge */}
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
              </span>
              <span className="font-mono font-semibold uppercase tracking-wider text-emerald-400 text-[11px] flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-emerald-400 animate-spin" />
                Live AI Evaluator Stream
              </span>
            </div>
            <span className="text-[10px] font-mono text-zinc-400 px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/10 capitalize">
              {evalStreaming?.stage === "transcribing"
                ? "Whisper Normalization"
                : evalStreaming?.stage === "telemetry"
                ? "Multimodal Acoustics"
                : evalStreaming?.stage === "evaluating_rubric"
                ? "Rubric Alignment"
                : evalStreaming?.stage === "reasoning"
                ? "Neural Reasoning"
                : evalStreaming?.stage === "selecting_next_question"
                ? "Adaptive Trajectory"
                : "Active Inference"}
            </span>
          </div>

          {/* Dynamic Progress Bar */}
          <div className="space-y-1">
            <div className="w-full bg-zinc-900 rounded-full h-1.5 overflow-hidden border border-white/5">
              <div
                className="bg-gradient-to-r from-emerald-500 via-teal-400 to-emerald-300 h-full rounded-full transition-all duration-300 ease-out shadow-[0_0_12px_rgba(16,185,129,0.5)]"
                style={{ width: `${Math.min(Math.max(evalStreaming?.progress || 20, 15), 100)}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-[10px] text-zinc-500 font-mono">
              <span>{evalStreaming?.message || "Evaluating candidate answer and competency markers..."}</span>
              <span>{Math.min(Math.max(evalStreaming?.progress || 20, 15), 100)}%</span>
            </div>
          </div>

          {/* Real-time Streaming Reasoning Console */}
          <div className="p-3 rounded-lg bg-black/60 border border-emerald-500/20 font-mono text-xs max-h-32 overflow-y-auto leading-relaxed shadow-inner">
            <div className="flex items-center gap-2 text-[10px] text-emerald-400/70 pb-1.5 mb-1.5 border-b border-emerald-500/15">
              <Brain className="w-3 h-3 text-emerald-400" />
              <span>EVALUATOR REASONING TRACE</span>
            </div>
            {evalStreaming?.thoughtTrace ? (
              <div className="text-zinc-200 whitespace-pre-wrap break-words text-[11px]">
                {evalStreaming.thoughtTrace}
                <span className="inline-block w-1.5 h-3.5 bg-emerald-400 animate-pulse ml-1 align-middle" />
              </div>
            ) : (
              <div className="flex items-center gap-2 text-zinc-500 italic text-[11px]">
                <Loader2 className="w-3 h-3 animate-spin text-emerald-400/60" />
                <span>
                  {evalStreaming?.stage === "transcribing"
                    ? "Transcribing audio frames and computing acoustic pitch cadence..."
                    : evalStreaming?.stage === "telemetry"
                    ? "Measuring gaze presence, speech rate (WPM), and pause control..."
                    : "Synthesizing rubric criteria and generating constructive feedback..."}
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
