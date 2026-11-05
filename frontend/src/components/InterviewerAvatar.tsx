"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Image from "next/image";
import { VolumeX } from "lucide-react";

export interface InterviewerAvatarProps {
  isSpeaking: boolean;
  isThinking?: boolean;
  onSkip?: () => void;
  onSpeechEnd?: () => void;
  statusLabel?: string;
  currentWord?: string;
  audioBlob?: Blob | null;
}

// 5 Anatomical Viseme Frames generated from Zaira's exact portrait:
// 0: Resting closed mouth (original photo)
// 1: Slight open (consonants / soft sound, dy=5px, teeth edge visible)
// 2: Medium open (normal speech / talking vowels, dy=10px, upper teeth & oral depth)
// 3: Wide open (emphasis / open vowels 'aa', 'ah', dy=16px, full teeth & oral cavity)
// 4: Round vowel ('oo', 'oh', 'w', dy=9px, oval aperture)
const VISEME_FRAMES = [
  "/images/zaira-viseme-0.png",
  "/images/zaira-viseme-1.png",
  "/images/zaira-viseme-2.png",
  "/images/zaira-viseme-3.png",
  "/images/zaira-viseme-4.png",
];

export function InterviewerAvatar({
  isSpeaking,
  isThinking = false,
  onSkip,
  onSpeechEnd,
  audioBlob,
}: InterviewerAvatarProps) {
  // Currently active viseme frame (0 = closed resting mouth)
  const [activeViseme, setActiveViseme] = useState<number>(0);

  // Audio references
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);

  // Audio-driven speech tracking refs
  const isSpeakingRef = useRef<boolean>(isSpeaking);
  isSpeakingRef.current = isSpeaking;

  const currentEnergyRef = useRef<number>(0);
  const syllabicPhaseRef = useRef<number>(0);

  // Pre-load all viseme frames so frame switching is instantaneous (0ms flicker)
  useEffect(() => {
    VISEME_FRAMES.forEach((src) => {
      const img = new window.Image();
      img.src = src;
    });
  }, []);

  // Handle Synchronized Audio Playback
  useEffect(() => {
    if (!isSpeaking) {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      currentEnergyRef.current = 0;
      setActiveViseme(0);
      return;
    }

    if (!audioBlob) return;

    let isCancelled = false;
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    audioRef.current = audio;

    // Connect Web Audio Analyser for real-time speech intensity
    try {
      const AudioCtxClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;

      if (!audioCtxRef.current || audioCtxRef.current.state === "closed") {
        audioCtxRef.current = new AudioCtxClass();
      }

      const ctx = audioCtxRef.current;
      if (ctx.state === "suspended") {
        ctx.resume().catch(() => {});
      }

      const source = ctx.createMediaElementSource(audio);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.2;
      analyserRef.current = analyser;

      source.connect(analyser);
      analyser.connect(ctx.destination);
    } catch (err) {
      console.warn("Analyser setup note, continuing with direct playback:", err);
    }

    audio.onended = () => {
      URL.revokeObjectURL(audioUrl);
      if (audioRef.current === audio) {
        audioRef.current = null;
      }
      currentEnergyRef.current = 0;
      setActiveViseme(0);
      onSpeechEnd?.();
    };

    audio.onerror = (err) => {
      console.warn("Audio error:", err);
      URL.revokeObjectURL(audioUrl);
      if (audioRef.current === audio) {
        audioRef.current = null;
      }
      currentEnergyRef.current = 0;
      setActiveViseme(0);
      onSpeechEnd?.();
    };

    audio.play().catch((err) => {
      console.warn("Audio autoplay blocked/interrupted:", err);
      URL.revokeObjectURL(audioUrl);
      if (audioRef.current === audio) {
        audioRef.current = null;
      }
      currentEnergyRef.current = 0;
      setActiveViseme(0);
      onSpeechEnd?.();
    });

    return () => {
      isCancelled = true;
      audio.pause();
      URL.revokeObjectURL(audioUrl);
      if (audioRef.current === audio) {
        audioRef.current = null;
      }
      currentEnergyRef.current = 0;
      setActiveViseme(0);
    };
  }, [isSpeaking, audioBlob, onSpeechEnd]);

  // 60 FPS Real-Time Audio-Driven 2D Lip-Sync Loop
  useEffect(() => {
    const freqData = new Uint8Array(128);
    let running = true;
    let lastTime = performance.now();

    const loop = (now: number) => {
      if (!running) return;

      const delta = Math.min((now - lastTime) / 1000, 0.05);
      lastTime = now;

      if (isSpeakingRef.current) {
        let rawEnergy = 0;
        let lowFreq = 0;
        let midFreq = 0;

        if (audioRef.current && !audioRef.current.paused && analyserRef.current) {
          analyserRef.current.getByteFrequencyData(freqData);

          // Human speech formants:
          // Low formant (150Hz - 600Hz): bins 2 to 7
          // Mid speech formant (600Hz - 2400Hz): bins 8 to 28
          let lowSum = 0;
          let midSum = 0;

          for (let i = 2; i <= 7; i++) {
            lowSum += freqData[i];
          }
          for (let i = 8; i <= 28; i++) {
            midSum += freqData[i];
          }

          lowFreq = lowSum / (6 * 255);
          midFreq = midSum / (21 * 255);
          rawEnergy = Math.max(lowFreq * 0.9, midFreq * 1.1);
        } else {
          // Robust real-time syllabic cadence whenever speech audio/TTS is active
          syllabicPhaseRef.current += delta * 13.0;
          const s = Math.sin(syllabicPhaseRef.current) * 0.5 + 0.5;
          const cadence = Math.sin(syllabicPhaseRef.current * 0.45) * 0.3 + 0.7;
          rawEnergy = s > 0.12 ? s * cadence * 0.75 : 0;
          midFreq = rawEnergy;
          lowFreq = rawEnergy * 0.8;
        }

        // Fast attack, natural decay envelope
        const attack = 0.55;
        const decay = 0.35;
        const target = rawEnergy > 0.04 ? rawEnergy : 0;
        
        if (target > currentEnergyRef.current) {
          currentEnergyRef.current = currentEnergyRef.current * (1 - attack) + target * attack;
        } else {
          currentEnergyRef.current = currentEnergyRef.current * (1 - decay) + target * decay;
        }

        const energy = currentEnergyRef.current;

        // Select exact anatomical viseme based on speech intensity and vowels
        if (energy < 0.045) {
          // Pause / Silence: Return immediately to resting closed mouth
          setActiveViseme(0);
        } else if (energy < 0.16) {
          // Consonants / soft syllable: Slight open (viseme 1)
          setActiveViseme(1);
        } else if (energy < 0.32) {
          // Normal vowel / standard speech: Medium open (viseme 2)
          // If low frequencies dominate (rounded vowels like 'oh', 'oo'), use viseme 4
          if (lowFreq > midFreq * 1.25) {
            setActiveViseme(4);
          } else {
            setActiveViseme(2);
          }
        } else {
          // Stressed syllable / wide vowel ('aa', 'ah'): Wide open (viseme 3)
          setActiveViseme(3);
        }
      } else {
        // Not speaking: strictly closed resting mouth
        currentEnergyRef.current = 0;
        setActiveViseme(0);
      }

      animFrameRef.current = requestAnimationFrame(loop);
    };

    animFrameRef.current = requestAnimationFrame(loop);

    return () => {
      running = false;
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, []);

  // Handle manual skip
  const handleSkip = useCallback(() => {
    if (audioRef.current) {
      try {
        audioRef.current.pause();
      } catch {
        // ignore
      }
      audioRef.current = null;
    }
    currentEnergyRef.current = 0;
    setActiveViseme(0);
    onSkip?.();
  }, [onSkip]);

  return (
    <div
      className={`tl-card overflow-hidden rounded-3xl relative bg-gradient-to-b from-[#0c0e18] via-[#07080f] to-[#040508] border transition-colors duration-300 ${
        isSpeaking
          ? "border-orange-500/50 shadow-[0_0_35px_rgba(249,115,22,0.18)]"
          : isThinking
          ? "border-amber-400/40 shadow-[0_0_25px_rgba(251,191,36,0.14)]"
          : "border-white/10 shadow-[0_12px_48px_rgba(0,0,0,0.7)]"
      }`}
    >
      {/* Fixed Viewport Framing — Completely prevents floating-head and expanding scale jumps */}
      <div className="relative w-full h-[460px] sm:h-[500px] lg:h-[520px] flex items-end justify-center overflow-hidden bg-black/40">
        
        {/* Dynamic 2D Lip-Synced Avatar Stage */}
        <div className="relative w-full h-full max-w-[620px] flex items-end justify-center z-10">
          {VISEME_FRAMES.map((src, index) => (
            <div
              key={src}
              className={`absolute inset-0 w-full h-full flex items-end justify-center pointer-events-none select-none transition-opacity duration-75 ${
                activeViseme === index ? "opacity-100 z-10" : "opacity-0 z-0"
              }`}
            >
              <Image
                src={src}
                alt="Zaira - AI Interviewer"
                fill
                sizes="(max-width: 768px) 100vw, (max-width: 1400px) 70vw, 800px"
                priority={index === 0}
                unoptimized
                className="object-contain object-bottom pointer-events-none select-none drop-shadow-[0_24px_48px_rgba(0,0,0,0.85)]"
              />
            </div>
          ))}
        </div>

        {/* Studio Lighting Background Glow */}
        <div
          className={`absolute inset-0 pointer-events-none transition-opacity duration-500 ${
            isSpeaking
              ? "opacity-100 bg-[radial-gradient(ellipse_at_center,_rgba(249,115,22,0.12)_0%,_transparent_70%)]"
              : isThinking
              ? "opacity-100 bg-[radial-gradient(ellipse_at_center,_rgba(251,191,36,0.08)_0%,_transparent_70%)]"
              : "opacity-30 bg-[radial-gradient(ellipse_at_center,_rgba(16,185,129,0.05)_0%,_transparent_65%)]"
          }`}
        />

        {/* Bottom subtle gradient vignette */}
        <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-[#040508]/80 to-transparent pointer-events-none z-10" />

        {/* Minimal Skip Audio CTA while speech is actively playing */}
        {isSpeaking && onSkip && (
          <div className="absolute bottom-3 right-3 z-20">
            <button
              onClick={handleSkip}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-black/70 hover:bg-black/90 text-zinc-300 hover:text-white rounded-lg text-xs font-medium border border-white/10 transition-all backdrop-blur-md shadow-sm"
              aria-label="Skip question audio and proceed to answer"
            >
              <VolumeX className="w-3.5 h-3.5 text-zinc-400" />
              <span>Skip Audio</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
