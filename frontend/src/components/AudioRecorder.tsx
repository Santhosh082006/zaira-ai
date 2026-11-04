"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Mic, Square, Trash2, Loader2, Video, Check, Sparkles, AlertCircle, Lightbulb, CheckCircle2 } from "lucide-react";

export type RecorderState = "IDLE" | "RECORDING" | "RECORDED" | "PROCESSING" | "ERROR";

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
  isProcessing,
  disabled,
  autoStart = false,
}: AudioRecorderProps) {
  const [internalState, setInternalState] = useState<"IDLE" | "RECORDING" | "RECORDED" | "ERROR">("IDLE");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [recordingTime, setRecordingTime] = useState(0);
  const [mediaPreviewUrl, setMediaPreviewUrl] = useState<string | null>(null);
  const [hasCamera, setHasCamera] = useState<boolean>(false);

  // Live streaming transcription state
  const [finalTranscript, setFinalTranscript] = useState<string>("");
  const [interimTranscript, setInterimTranscript] = useState<string>("");
  const [speechRecognitionSupported, setSpeechRecognitionSupported] = useState<boolean>(true);

  // Derived effective state: if parent is processing, show PROCESSING mode
  const effectiveState: RecorderState = isProcessing ? "PROCESSING" : internalState;

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const currentBlobRef = useRef<Blob | null>(null);
  const recognitionRef = useRef<any>(null);

  // Clean up all resources (recorder, tracks, timers, blob URLs, speech recognition)
  const cleanup = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // Ignore abort errors
      }
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        // Ignore if already stopped
      }
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (mediaPreviewUrl) {
      URL.revokeObjectURL(mediaPreviewUrl);
    }
  }, [mediaPreviewUrl]);

  // Initialize media stream on mount and clean up on unmount
  useEffect(() => {
    let mounted = true;

    async function initMedia() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 1280, height: 720 },
          audio: true,
        });
        if (mounted) {
          streamRef.current = stream;
          setHasCamera(true);
          if (videoRef.current) {
            videoRef.current.srcObject = stream;
          }
        }
      } catch {
        // Fallback to audio-only if camera is unavailable or denied
        try {
          const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
          if (mounted) {
            streamRef.current = audioStream;
            setHasCamera(false);
          }
        } catch (audioErr) {
          if (mounted) {
            console.error("Hardware access denied:", audioErr);
            setErrorMsg("Microphone access is required to record your answer.");
            setInternalState("ERROR");
          }
        }
      }
    }

    initMedia();

    return () => {
      mounted = false;
      cleanup();
    };
  }, [cleanup]);

  // Check speech recognition support once on client
  useEffect(() => {
    if (typeof window !== "undefined") {
      const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (!SpeechRec) {
        setSpeechRecognitionSupported(false);
      }
    }
  }, []);

  const getSupportedMimeType = (withVideo: boolean): string => {
    const videoTypes = [
      "video/webm;codecs=vp9,opus",
      "video/webm;codecs=vp8,opus",
      "video/webm",
      "video/mp4",
    ];
    const audioTypes = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/mp4",
      "audio/ogg;codecs=opus",
      "audio/ogg",
    ];

    const types = withVideo ? videoTypes : audioTypes;
    for (const t of types) {
      if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(t)) {
        return t;
      }
    }
    return withVideo ? "video/webm" : "audio/webm";
  };

  const startRecording = async () => {
    try {
      onRecordingStart?.();
      setErrorMsg(null);
      setFinalTranscript("");
      setInterimTranscript("");

      // Ensure media stream exists
      if (!streamRef.current || !streamRef.current.active) {
        try {
          const mediaStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 1280, height: 720 },
            audio: true,
          });
          streamRef.current = mediaStream;
          setHasCamera(true);
        } catch {
          const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
          streamRef.current = audioStream;
          setHasCamera(false);
        }
      }

      const stream = streamRef.current;
      if (!stream) {
        setErrorMsg("Unable to access media stream.");
        setInternalState("ERROR");
        return;
      }

      const isVideoActive = hasCamera && stream.getVideoTracks().length > 0;
      const mimeType = getSupportedMimeType(isVideoActive);

      const recorderOptions: MediaRecorderOptions = {};
      if (mimeType) {
        recorderOptions.mimeType = mimeType;
      }

      let mediaRecorder: MediaRecorder;
      try {
        mediaRecorder = new MediaRecorder(stream, recorderOptions);
      } catch {
        mediaRecorder = new MediaRecorder(stream);
      }
      mediaRecorderRef.current = mediaRecorder;
      recordedChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          recordedChunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        const outputMime = mimeType || (isVideoActive ? "video/webm" : "audio/webm");
        const recordedBlob = new Blob(recordedChunksRef.current, { type: outputMime });
        if (recordedBlob.size === 0) {
          setErrorMsg("Recording failed: Captured media is empty.");
          setInternalState("ERROR");
          return;
        }

        currentBlobRef.current = recordedBlob;
        const url = URL.createObjectURL(recordedBlob);
        setMediaPreviewUrl(url);
        setInternalState("RECORDED");
      };

      // Start MediaRecorder with robust fallback
      try {
        if (mediaRecorder.state === "inactive") {
          mediaRecorder.start(250);
        }
      } catch {
        if (mediaRecorder.state === "inactive") {
          mediaRecorder.start();
        }
      }
      setInternalState("RECORDING");
      setRecordingTime(0);

      // Start timer
      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);

      // Start Live Speech Recognition in parallel
      if (typeof window !== "undefined") {
        const SpeechRec = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
        if (SpeechRec) {
          try {
            const recognition = new SpeechRec();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = "en-US";

            let accumulatedFinal = "";

            recognition.onresult = (event: any) => {
              let currentInterim = "";
              for (let i = event.resultIndex; i < event.results.length; ++i) {
                const transcriptChunk = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                  accumulatedFinal += (accumulatedFinal ? " " : "") + transcriptChunk.trim();
                } else {
                  currentInterim += transcriptChunk;
                }
              }

              setFinalTranscript(accumulatedFinal);
              setInterimTranscript(currentInterim);

              const fullLiveText = (accumulatedFinal + (currentInterim ? " " + currentInterim : "")).trim();
              if (fullLiveText) {
                onLiveTranscriptUpdate?.(fullLiveText, false);
              }
            };

            recognition.onerror = (event: any) => {
              console.warn("Speech recognition warning/error:", event.error);
            };

            recognition.onend = () => {
              // If still recording, restart recognition
              if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
                try {
                  recognition.start();
                } catch {
                  // Ignore restart errors
                }
              }
            };

            recognition.start();
            recognitionRef.current = recognition;
          } catch (recErr) {
            console.warn("Unable to start live speech recognition:", recErr);
          }
        }
      }
    } catch (err) {
      console.error("Recording start error:", err);
      setErrorMsg("Failed to start recording. Please check microphone/camera permissions.");
      setInternalState("ERROR");
    }
  };

  // Automatically activate recording when autoStart triggers (e.g. avatar finishes speaking)
  useEffect(() => {
    if (autoStart && internalState === "IDLE" && !isProcessing && !disabled) {
      const timer = setTimeout(() => {
        if (internalState === "IDLE" && !isProcessing && !disabled) {
          startRecording();
        }
      }, 350);
      return () => clearTimeout(timer);
    }
  }, [autoStart, internalState, isProcessing, disabled]);

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignore stop error
      }
      recognitionRef.current = null;
    }

    // Emit final transcript update
    const completeText = (finalTranscript + (interimTranscript ? " " + interimTranscript : "")).trim();
    if (completeText) {
      onLiveTranscriptUpdate?.(completeText, true);
    }
  };

  const handleReset = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // Ignore
      }
      recognitionRef.current = null;
    }
    if (mediaPreviewUrl) {
      URL.revokeObjectURL(mediaPreviewUrl);
      setMediaPreviewUrl(null);
    }
    currentBlobRef.current = null;
    recordedChunksRef.current = [];
    setRecordingTime(0);
    setFinalTranscript("");
    setInterimTranscript("");
    setInternalState("IDLE");
    setErrorMsg(null);

    // Reattach camera stream to video tag if active
    if (hasCamera && streamRef.current && videoRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  };

  const handleSubmit = () => {
    if (currentBlobRef.current) {
      onRecordingComplete(currentBlobRef.current);
    }
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, "0");
    const s = (seconds % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  const isControlsDisabled = disabled || effectiveState === "PROCESSING";

  // Calculate live word count & speaking rate
  const fullLiveText = (finalTranscript + (interimTranscript ? " " + interimTranscript : "")).trim();
  const liveWordCount = fullLiveText ? fullLiveText.split(/\s+/).length : 0;
  const liveWpm = recordingTime > 2 ? Math.round((liveWordCount / recordingTime) * 60) : 0;

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

      {/* ============================================================== */}
      {/* REAL-TIME STREAMING TRANSCRIPTION STAGE                        */}
      {/* ============================================================== */}
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

      {effectiveState === "PROCESSING" && (
        <div className="flex items-center justify-center gap-2.5 text-emerald-400 py-3 text-xs md:text-sm font-medium">
          <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
          <span>Evaluating multimodal signals and target competencies...</span>
        </div>
      )}
    </div>
  );
}
