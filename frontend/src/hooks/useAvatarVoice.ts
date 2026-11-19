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
  const [audioElement, setAudioElement] = useState<HTMLAudioElement | null>(null);

  const activeAudioRef = useRef<HTMLAudioElement | null>(null);
  const speakerRef = useRef<QuestionSpeaker | null>(null);
  const currentBlobUrlRef = useRef<string | null>(null);

  // Initialize browser speech synthesis speaker on mount
  useEffect(() => {
    speakerRef.current = new QuestionSpeaker();
    return () => {
      if (activeAudioRef.current) {
        activeAudioRef.current.pause();
        activeAudioRef.current = null;
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

  const stopSpeaking = useCallback(() => {
    if (activeAudioRef.current) {
      activeAudioRef.current.pause();
      activeAudioRef.current.currentTime = 0;
      activeAudioRef.current = null;
    }
    setAudioElement(null);
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

      setIsSpeaking(true);
      setQuestionPhase("SPEAKING");
      setSpeechFailed(false);
      options.onSpeechStart?.();

      try {
        // 1. Fetch Edge-TTS neural speech audio
        const blob = await fetchQuestionAudio(text);
        if (blob) {
          return new Promise<boolean>((resolve) => {
            const url = URL.createObjectURL(blob);
            currentBlobUrlRef.current = url;
            const audio = new Audio(url);
            activeAudioRef.current = audio;
            setAudioElement(audio);

            audio.onplay = () => {
              setIsSpeaking(true);
              setQuestionPhase("SPEAKING");
            };

            audio.onended = () => {
              if (currentBlobUrlRef.current) {
                URL.revokeObjectURL(currentBlobUrlRef.current);
                currentBlobUrlRef.current = null;
              }
              activeAudioRef.current = null;
              setAudioElement(null);
              setIsSpeaking(false);
              setQuestionPhase("READY_TO_ANSWER");
              options.onSpeechEnd?.();
              resolve(true);
            };

            audio.onerror = (err) => {
              console.warn("[AvatarVoice] Audio element playback error:", err);
              if (currentBlobUrlRef.current) {
                URL.revokeObjectURL(currentBlobUrlRef.current);
                currentBlobUrlRef.current = null;
              }
              activeAudioRef.current = null;
              setIsSpeaking(false);
              setQuestionPhase("READY_TO_ANSWER");
              setSpeechFailed(true);
              options.onSpeechEnd?.();
              resolve(false);
            };

            audio.play().catch((playErr) => {
              console.warn("[AvatarVoice] Audio autoplay prevented:", playErr);
              // Fall back to browser SpeechSynthesis
              if (speakerRef.current && speakerRef.current.isAvailable()) {
                speakerRef.current.speak(
                  text,
                  () => {
                    setIsSpeaking(true);
                    setQuestionPhase("SPEAKING");
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

        // 2. Fallback: Browser SpeechSynthesis
        if (speakerRef.current && speakerRef.current.isAvailable()) {
          return new Promise<boolean>((resolve) => {
            speakerRef.current?.speak(
              text,
              () => {
                setIsSpeaking(true);
                setQuestionPhase("SPEAKING");
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
              },
              (_charIndex, _charLength, word) => {
                setActiveWord(word);
              }
            );
          });
        }

        // No audio player available
        setIsSpeaking(false);
        setQuestionPhase("READY_TO_ANSWER");
        setSpeechFailed(true);
        options.onSpeechEnd?.();
        return false;
      } catch (err) {
        console.warn("[AvatarVoice] Speech articulation error:", err);
        setIsSpeaking(false);
        setQuestionPhase("READY_TO_ANSWER");
        setSpeechFailed(true);
        options.onSpeechEnd?.();
        return false;
      }
    },
    [stopSpeaking, options]
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
    audioElement,
    questionAudioBlob: null,
    speakText,
    speakQuestion,
    stopSpeaking,
    handleAvatarSpeechEnd,
    resetVoiceState,
  };
}
