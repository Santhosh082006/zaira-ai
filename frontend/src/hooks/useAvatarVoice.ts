"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Question, fetchQuestionAudio } from "../lib/interviewApi";
import { QuestionSpeaker } from "../lib/speechSynthesis";

export function useAvatarVoice(
  currentQuestion: Question | null,
  isReadyState: boolean
) {
  const [questionPhase, setQuestionPhase] = useState<"SPEAKING" | "READY_TO_ANSWER">("SPEAKING");
  const [speechFailed, setSpeechFailed] = useState<boolean>(false);
  const [activeWord, setActiveWord] = useState<string>("");
  const [questionAudioBlob, setQuestionAudioBlob] = useState<Blob | null>(null);

  const speakerRef = useRef<QuestionSpeaker | null>(null);
  const lastSpokenQuestionIdRef = useRef<string | null>(null);

  // Initialize browser speech synthesis speaker on mount
  useEffect(() => {
    speakerRef.current = new QuestionSpeaker();
    return () => {
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

    // Attempt to fetch cached neural audio via Edge-TTS
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
        setQuestionPhase("SPEAKING");
      },
      () => {
        setActiveWord("");
        setQuestionPhase("READY_TO_ANSWER");
      },
      (err: unknown) => {
        console.warn("Speech synthesis playback error / fallback:", err);
        setSpeechFailed(true);
        setActiveWord("");
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

    // Unlock browser AudioContext and HTMLAudioElement during user click gesture
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

    if (questionAudioBlob) {
      const freshBlob = questionAudioBlob.slice();
      setQuestionAudioBlob(freshBlob);
    } else {
      speakQuestion(currentQuestion);
    }
  }, [currentQuestion, questionAudioBlob, speakQuestion]);

  // Automatically speak new questions exactly once when entering READY state
  useEffect(() => {
    if (isReadyState && currentQuestion) {
      if (lastSpokenQuestionIdRef.current !== currentQuestion.id) {
        lastSpokenQuestionIdRef.current = currentQuestion.id;
        speakQuestion(currentQuestion);
      }
    }
  }, [isReadyState, currentQuestion, speakQuestion]);

  const resetVoiceState = useCallback(() => {
    if (speakerRef.current) {
      speakerRef.current.stop();
    }
    setActiveWord("");
    lastSpokenQuestionIdRef.current = null;
    setSpeechFailed(false);
    setQuestionPhase("SPEAKING");
    setQuestionAudioBlob(null);
  }, []);

  return {
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
  };
}
