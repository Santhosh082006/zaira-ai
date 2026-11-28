"use client";

import { useState, useRef, useEffect, useCallback, RefObject } from "react";

export type RecorderState = "IDLE" | "RECORDING" | "RECORDED" | "PROCESSING" | "ERROR";

export interface UseAudioRecorderOptions {
  onRecordingComplete: (blob: Blob) => void;
  onRecordingStart?: () => void;
  onLiveTranscriptUpdate?: (transcript: string, isFinal: boolean) => void;
  isProcessing?: boolean;
  disabled?: boolean;
  autoStart?: boolean;
  sharedMediaStream?: MediaStream | null;
}

export interface UseAudioRecorderReturn {
  internalState: "IDLE" | "RECORDING" | "RECORDED" | "ERROR";
  effectiveState: RecorderState;
  errorMsg: string | null;
  recordingTime: number;
  hasCamera: boolean;
  mediaPreviewUrl: string | null;
  finalTranscript: string;
  interimTranscript: string;
  speechRecognitionSupported: boolean;
  videoRef: RefObject<HTMLVideoElement | null>;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  handleReset: () => void;
  handleSubmit: () => void;
  formatTime: (seconds: number) => string;
  isControlsDisabled: boolean;
  liveWordCount: number;
  liveWpm: number;
}

export function useAudioRecorder({
  onRecordingComplete,
  onRecordingStart,
  onLiveTranscriptUpdate,
  isProcessing = false,
  disabled = false,
  autoStart = false,
  sharedMediaStream = null,
}: UseAudioRecorderOptions): UseAudioRecorderReturn {
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
  const ownsStreamRef = useRef(false);
  const mediaRequestRef = useRef<Promise<MediaStream> | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const currentBlobRef = useRef<Blob | null>(null);
  const recognitionRef = useRef<any>(null);

  // Clean up recorder resources. A stream handed off from preflight belongs to
  // the interview session and is released by its owner, not this question view.
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
    if (streamRef.current && ownsStreamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
    }
    streamRef.current = null;
    ownsStreamRef.current = false;
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  const acquireMedia = useCallback(async (): Promise<MediaStream> => {
    if (sharedMediaStream?.active) {
      streamRef.current = sharedMediaStream;
      ownsStreamRef.current = false;
      return sharedMediaStream;
    }
    if (streamRef.current?.active) return streamRef.current;
    if (mediaRequestRef.current) return mediaRequestRef.current;

    const request = (async () => {
      try {
        return await navigator.mediaDevices.getUserMedia({
          video: { width: 1280, height: 720 },
          audio: true,
        });
      } catch {
        return await navigator.mediaDevices.getUserMedia({ audio: true });
      }
    })();
    mediaRequestRef.current = request;
    try {
      const stream = await request;
      ownsStreamRef.current = true;
      return stream;
    } finally {
      if (mediaRequestRef.current === request) mediaRequestRef.current = null;
    }
  }, [sharedMediaStream]);

  // Adopt the already-authorized preflight stream, or acquire one stream once.
  useEffect(() => {
    let mounted = true;
    acquireMedia().then((stream) => {
      if (!mounted) {
        if (ownsStreamRef.current) stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      const cameraAvailable = stream.getVideoTracks().some((track) => track.readyState === "live" && track.enabled);
      setHasCamera(cameraAvailable);
      if (videoRef.current && cameraAvailable) videoRef.current.srcObject = stream;
    }).catch((mediaError: unknown) => {
      if (mounted) {
        console.error("Hardware access denied:", mediaError);
        setErrorMsg("Microphone access is required to record your answer.");
        setInternalState("ERROR");
      }
    });

    return () => {
      mounted = false;
      cleanup();
    };
  }, [acquireMedia, cleanup]);

  useEffect(() => {
    if (!mediaPreviewUrl) return;
    return () => URL.revokeObjectURL(mediaPreviewUrl);
  }, [mediaPreviewUrl]);

  // The recorded-playback element replaces the live camera element while the
  // user reviews an answer. Reattach the still-running session stream when they
  // return to IDLE (Rerecord), after React has mounted the live video element.
  useEffect(() => {
    if (effectiveState === "RECORDED" || !hasCamera) return;
    const stream = streamRef.current;
    if (stream?.active && videoRef.current) videoRef.current.srcObject = stream;
  }, [effectiveState, hasCamera]);

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

      // Share an in-flight initialization request with the mount effect so
      // auto-start cannot open a second camera/microphone stream concurrently.
      const stream = await acquireMedia();
      streamRef.current = stream;
      const isVideoActive = stream.getVideoTracks().some((track) => track.readyState === "live" && track.enabled);
      setHasCamera(isVideoActive);
      if (isVideoActive && videoRef.current) videoRef.current.srcObject = stream;
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

      // Start MediaRecorder with fallback
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

            let recognitionFailed = false;

            recognition.onerror = (event: any) => {
              if (event.error === "network" || event.error === "not-allowed" || event.error === "service-not-allowed") {
                recognitionFailed = true;
                setSpeechRecognitionSupported(false);
              }
              console.warn("Speech recognition notice:", event.error);
            };

            recognition.onend = () => {
              // If still recording and no fatal error occurred, restart recognition
              if (
                !recognitionFailed &&
                mediaRecorderRef.current &&
                mediaRecorderRef.current.state === "recording"
              ) {
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

  // Automatically activate recording when autoStart triggers
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

  const fullLiveText = (finalTranscript + (interimTranscript ? " " + interimTranscript : "")).trim();
  const liveWordCount = fullLiveText ? fullLiveText.split(/\s+/).length : 0;
  const liveWpm = recordingTime > 2 ? Math.round((liveWordCount / recordingTime) * 60) : 0;

  return {
    internalState,
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
  };
}
