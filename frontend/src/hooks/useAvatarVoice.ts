"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Question, fetchQuestionAudio } from "../lib/interviewApi";
import { QuestionSpeaker } from "../lib/speechSynthesis";

interface UseAvatarVoiceOptions {
  onSpeechStart?: () => void;
  onSpeechEnd?: () => void;
}

export function useAvatarVoice(
  _currentQuestion?: Question | null,
  _autoSpeak: boolean = false,
  options: UseAvatarVoiceOptions = {}
) {
  const [isSpeaking, setIsSpeaking] = useState<boolean>(false);
  const [questionPhase, setQuestionPhase] = useState<"SPEAKING" | "READY_TO_ANSWER">("READY_TO_ANSWER");
  const [speechFailed, setSpeechFailed] = useState<boolean>(false);
  const [activeWord, setActiveWord] = useState<string>("");
  const [analyserNode, setAnalyserNode] = useState<AnalyserNode | null>(null);

  const persistentAudioRef = useRef<HTMLAudioElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const speakerRef = useRef<QuestionSpeaker | null>(null);
  const currentBlobUrlRef = useRef<string | null>(null);

  // Initialize persistent Audio element & Web Audio Analyser on mount
  useEffect(() => {
    speakerRef.current = new QuestionSpeaker();

    // Create a single persistent Audio element
    if (typeof window !== "undefined") {
      const audio = new Audio();
      audio.crossOrigin = "anonymous";
      persistentAudioRef.current = audio;
    }

    return () => {
      if (persistentAudioRef.current) {
        persistentAudioRef.current.pause();
        persistentAudioRef.current.src = "";
        persistentAudioRef.current = null;
      }
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        audioContextRef.current.close().catch(() => {});
        audioContextRef.current = null;
      }
      if (currentBlobUrlRef.current) {
        URL.revokeObjectURL(currentBlobUrlRef.current);
        currentBlobUrlRef.current = null;
      }
      if (speakerRef.current) {
        speakerRef.current.stop();
        speakerRef.current = null;
      }
    };
  }, []);

  // Lazily connect persistent Audio element to Web Audio AnalyserNode (called on user gesture)
  const ensureAudioGraph = useCallback((): AnalyserNode | null => {
    if (analyserRef.current) return analyserRef.current;
    if (typeof window === "undefined" || !persistentAudioRef.current) return null;

    try {
      const AudioCtxClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtxClass) return null;

      const ctx = new AudioCtxClass();
      audioContextRef.current = ctx;

      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.4;
      analyserRef.current = analyser;

      const source = ctx.createMediaElementSource(persistentAudioRef.current);
      source.connect(analyser);
      analyser.connect(ctx.destination);

      setAnalyserNode(analyser);
      return analyser;
    } catch (err) {
      console.warn("[AvatarVoice] Web Audio graph setup notice:", err);
      return null;
    }
  }, []);

  const stopSpeaking = useCallback(() => {
    if (persistentAudioRef.current) {
      persistentAudioRef.current.pause();
      persistentAudioRef.current.currentTime = 0;
    }
    if (currentBlobUrlRef.current) {
      URL.revokeObjectURL(currentBlobUrlRef.current);
      currentBlobUrlRef.current = null;
    }
    if (speakerRef.current) {
      speakerRef.current.stop();
    }
    setIsSpeaking(false);
    setQuestionPhase("READY_TO_ANSWER");
    setActiveWord("");
  }, []);

  // Authoritative single-channel speech articulation
  const speakText = useCallback(
    async (text: string): Promise<boolean> => {
      if (!text || !text.trim()) return false;

      // Stop any existing playback first to guarantee zero overlap
      stopSpeaking();

      // Ensure AudioContext is ready and resumed
      ensureAudioGraph();
      if (audioContextRef.current && audioContextRef.current.state === "suspended") {
        audioContextRef.current.resume().catch(() => {});
      }

      setQuestionPhase("SPEAKING");
      setSpeechFailed(false);

      try {
        // 1. Fetch Edge-TTS neural speech audio
        const blob = await fetchQuestionAudio(text);
        if (blob && persistentAudioRef.current) {
          return new Promise<boolean>((resolve) => {
            const audio = persistentAudioRef.current!;
            const url = URL.createObjectURL(blob);
            currentBlobUrlRef.current = url;

            audio.src = url;

            // Only enter speaking state when audio genuinely begins playing
            audio.onplay = () => {
              setIsSpeaking(true);
              setQuestionPhase("SPEAKING");
              options.onSpeechStart?.();
            };

            audio.onended = () => {
              if (currentBlobUrlRef.current) {
                URL.revokeObjectURL(currentBlobUrlRef.current);
                currentBlobUrlRef.current = null;
              }
              setIsSpeaking(false);
              setQuestionPhase("READY_TO_ANSWER");
              options.onSpeechEnd?.();
              resolve(true);
            };

            audio.onerror = (err) => {
              console.warn("[AvatarVoice] Audio playback error:", err);
              if (currentBlobUrlRef.current) {
                URL.revokeObjectURL(currentBlobUrlRef.current);
                currentBlobUrlRef.current = null;
              }
              setIsSpeaking(false);
              setQuestionPhase("READY_TO_ANSWER");
              setSpeechFailed(true);
              options.onSpeechEnd?.();
              resolve(false);
            };

            audio.play().catch((playErr) => {
              console.warn("[AvatarVoice] Audio play error, using browser speech:", playErr);
              // Fall back to browser SpeechSynthesis if autoplay policy intercepts
              if (speakerRef.current && speakerRef.current.isAvailable()) {
                speakerRef.current.speak(
                  text,
                  () => {
                    setIsSpeaking(true);
                    setQuestionPhase("SPEAKING");
                    options.onSpeechStart?.();
                  },
                  () => {
                    setIsSpeaking(false);
                    setQuestionPhase("READY_TO_ANSWER");
                    options.onSpeechEnd?.();
                    resolve(true);
                  },
                  () => {
                    setIsSpeaking(false);
                    setQuestionPhase("READY_TO_ANSWER");
                    setSpeechFailed(true);
                    options.onSpeechEnd?.();
                    resolve(false);
                  }
                );
              } else {
                setIsSpeaking(false);
                setQuestionPhase("READY_TO_ANSWER");
                setSpeechFailed(true);
                options.onSpeechEnd?.();
                resolve(false);
              }
            });
          });
        }

        // 2. Fallback to browser SpeechSynthesis if backend audio is null
        if (speakerRef.current && speakerRef.current.isAvailable()) {
          return new Promise<boolean>((resolve) => {
            speakerRef.current!.speak(
              text,
              () => {
                setIsSpeaking(true);
                setQuestionPhase("SPEAKING");
                options.onSpeechStart?.();
              },
              () => {
                setIsSpeaking(false);
                setQuestionPhase("READY_TO_ANSWER");
                options.onSpeechEnd?.();
                resolve(true);
              },
              () => {
                setIsSpeaking(false);
                setQuestionPhase("READY_TO_ANSWER");
                setSpeechFailed(true);
                options.onSpeechEnd?.();
                resolve(false);
              }
            );
          });
        }

        setIsSpeaking(false);
        setQuestionPhase("READY_TO_ANSWER");
        setSpeechFailed(true);
        options.onSpeechEnd?.();
        return false;
      } catch (err) {
        console.warn("[AvatarVoice] speakText error:", err);
        setIsSpeaking(false);
        setQuestionPhase("READY_TO_ANSWER");
        setSpeechFailed(true);
        options.onSpeechEnd?.();
        return false;
      }
    },
    [stopSpeaking, ensureAudioGraph, options]
  );

  const speakQuestion = useCallback(
    async (question: Question): Promise<boolean> => {
      return speakText(question.question_text);
    },
    [speakText]
  );

  const handleAvatarSpeechEnd = useCallback(() => {
    setActiveWord("");
    setIsSpeaking(false);
    setQuestionPhase("READY_TO_ANSWER");
  }, []);

  const resetVoiceState = useCallback(() => {
    stopSpeaking();
    setSpeechFailed(false);
    setActiveWord("");
    setQuestionPhase("READY_TO_ANSWER");
  }, [stopSpeaking]);

  return {
    isSpeaking,
    questionPhase,
    setQuestionPhase,
    speechFailed,
    activeWord,
    analyserNode,
    audioElement: persistentAudioRef.current,
    questionAudioBlob: null,
    speakText,
    speakQuestion,
    stopSpeaking,
    handleAvatarSpeechEnd,
    resetVoiceState,
  };
}
