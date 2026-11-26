"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Question, fetchQuestionAudio, fetchQuestionTimedAudio } from "../lib/interviewApi";
import { QuestionSpeaker } from "../lib/speechSynthesis";
import { WordTiming } from "../lib/visemeEngine";

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
  const [wordTimings, setWordTimings] = useState<WordTiming[]>([]);
  const [spokenText, setSpokenText] = useState<string>("");
  const [audioElementState, setAudioElementState] = useState<HTMLAudioElement | null>(null);
  const [speechGeneration, setSpeechGeneration] = useState<number>(0);

  const persistentAudioRef = useRef<HTMLAudioElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const speakerRef = useRef<QuestionSpeaker | null>(null);
  const currentBlobUrlRef = useRef<string | null>(null);
  const speechIdRef = useRef<number>(0);

  // Initialize persistent Audio element & Web Audio Analyser on mount
  useEffect(() => {
    speakerRef.current = new QuestionSpeaker();

    // Create a single persistent Audio element
    if (typeof window !== "undefined") {
      const audio = new Audio();
      audio.crossOrigin = "anonymous";
      persistentAudioRef.current = audio;
      setAudioElementState(audio);
    }

    return () => {
      if (persistentAudioRef.current) {
        persistentAudioRef.current.pause();
        persistentAudioRef.current.src = "";
        persistentAudioRef.current = null;
      }
      setAudioElementState(null);
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
    speechIdRef.current += 1;
    if (persistentAudioRef.current) {
      persistentAudioRef.current.onplay = null;
      persistentAudioRef.current.onended = null;
      persistentAudioRef.current.onerror = null;
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
    setWordTimings([]);
    setSpokenText("");
  }, []);

  // Authoritative single-channel speech articulation
  const speakText = useCallback(
    async (text: string): Promise<boolean> => {
      if (!text || !text.trim()) return false;

      // Stop any existing playback first to guarantee zero overlap across repeated questions
      stopSpeaking();
      const mySpeechId = ++speechIdRef.current;

      // Ensure AudioContext is ready and resumed
      ensureAudioGraph();
      if (audioContextRef.current && audioContextRef.current.state === "suspended") {
        audioContextRef.current.resume().catch(() => {});
      }

      setQuestionPhase("SPEAKING");
      setSpeechFailed(false);
      setSpokenText(text);
      setWordTimings([]);
      setActiveWord("");
      setSpeechGeneration((prev) => prev + 1);

      const playBrowserSpeechFallback = (resolve: (ok: boolean) => void) => {
        if (mySpeechId !== speechIdRef.current) {
          resolve(false);
          return;
        }
        if (speakerRef.current && speakerRef.current.isAvailable()) {
          speakerRef.current.speak(
            text,
            () => {
              if (mySpeechId !== speechIdRef.current) return;
              setIsSpeaking(true);
              setQuestionPhase("SPEAKING");
              options.onSpeechStart?.();
            },
            () => {
              if (mySpeechId !== speechIdRef.current) {
                resolve(false);
                return;
              }
              setIsSpeaking(false);
              setQuestionPhase("READY_TO_ANSWER");
              setActiveWord("");
              options.onSpeechEnd?.();
              resolve(true);
            },
            () => {
              if (mySpeechId !== speechIdRef.current) {
                resolve(false);
                return;
              }
              setIsSpeaking(false);
              setQuestionPhase("READY_TO_ANSWER");
              setActiveWord("");
              setSpeechFailed(true);
              options.onSpeechEnd?.();
              resolve(false);
            },
            (_charIdx, _charLen, word) => {
              if (mySpeechId !== speechIdRef.current) return;
              if (word) setActiveWord(word);
            }
          );
        } else {
          setIsSpeaking(false);
          setQuestionPhase("READY_TO_ANSWER");
          setSpeechFailed(true);
          options.onSpeechEnd?.();
          resolve(false);
        }
      };

      try {
        // 1. Fetch Edge-TTS neural speech audio + WordBoundary phoneme timings
        const timed = await fetchQuestionTimedAudio(text);
        if (mySpeechId !== speechIdRef.current) return false;

        const audioBlob = timed?.audioBlob ?? (await fetchQuestionAudio(text));
        if (mySpeechId !== speechIdRef.current) return false;

        if (timed?.wordTimings?.length) {
          setWordTimings(timed.wordTimings);
        }
        if (timed?.spokenText) {
          setSpokenText(timed.spokenText);
        }

        if (audioBlob && persistentAudioRef.current) {
          return new Promise<boolean>((resolve) => {
            const audio = persistentAudioRef.current!;
            const url = URL.createObjectURL(audioBlob);
            currentBlobUrlRef.current = url;

            audio.src = url;
            setAudioElementState(audio);

            // Only enter speaking state when audio genuinely begins playing
            audio.onplay = () => {
              if (mySpeechId !== speechIdRef.current) return;
              setIsSpeaking(true);
              setQuestionPhase("SPEAKING");
              options.onSpeechStart?.();
            };

            audio.onended = () => {
              if (currentBlobUrlRef.current === url) {
                URL.revokeObjectURL(url);
                currentBlobUrlRef.current = null;
              }
              if (mySpeechId !== speechIdRef.current) {
                resolve(false);
                return;
              }
              setIsSpeaking(false);
              setQuestionPhase("READY_TO_ANSWER");
              setActiveWord("");
              setWordTimings([]);
              options.onSpeechEnd?.();
              resolve(true);
            };

            audio.onerror = (err) => {
              console.warn("[AvatarVoice] Audio playback error:", err);
              if (currentBlobUrlRef.current === url) {
                URL.revokeObjectURL(url);
                currentBlobUrlRef.current = null;
              }
              if (mySpeechId !== speechIdRef.current) {
                resolve(false);
                return;
              }
              setIsSpeaking(false);
              setQuestionPhase("READY_TO_ANSWER");
              setActiveWord("");
              setWordTimings([]);
              setSpeechFailed(true);
              options.onSpeechEnd?.();
              resolve(false);
            };

            audio.play().catch((playErr) => {
              console.warn("[AvatarVoice] Audio play error, using browser speech:", playErr);
              playBrowserSpeechFallback(resolve);
            });
          });
        }

        // 2. Fallback to browser SpeechSynthesis if backend audio is null
        return new Promise<boolean>((resolve) => {
          playBrowserSpeechFallback(resolve);
        });
      } catch (err) {
        console.warn("[AvatarVoice] speakText error:", err);
        if (mySpeechId === speechIdRef.current) {
          setIsSpeaking(false);
          setQuestionPhase("READY_TO_ANSWER");
          setActiveWord("");
          setWordTimings([]);
          setSpeechFailed(true);
          options.onSpeechEnd?.();
        }
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
    setWordTimings([]);
    setIsSpeaking(false);
    setQuestionPhase("READY_TO_ANSWER");
  }, []);

  const resetVoiceState = useCallback(() => {
    stopSpeaking();
    setSpeechFailed(false);
    setActiveWord("");
    setWordTimings([]);
    setSpokenText("");
    setQuestionPhase("READY_TO_ANSWER");
  }, [stopSpeaking]);

  return {
    isSpeaking,
    questionPhase,
    setQuestionPhase,
    speechFailed,
    activeWord,
    wordTimings,
    spokenText,
    speechGeneration,
    analyserNode,
    audioElement: audioElementState,
    questionAudioBlob: null,
    speakText,
    speakQuestion,
    stopSpeaking,
    handleAvatarSpeechEnd,
    resetVoiceState,
  };
}
