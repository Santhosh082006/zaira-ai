"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Image from "next/image";
import { Volume2, VolumeX, Camera, RotateCcw, Sparkles, Mic } from "lucide-react";

export interface InterviewerAvatarProps {
  isSpeaking: boolean;
  isThinking?: boolean;
  onSkip?: () => void;
  onSpeechEnd?: () => void;
  statusLabel?: string;
  currentWord?: string;
  audioBlob?: Blob | null;
  mode?: "hero" | "compact";
  examinerName?: string;
  examinerRole?: string;
  questionId?: string;
  videoUrl?: string | null;
  liveVideoRef?: React.Ref<HTMLVideoElement>;
  isLiveAvatarConnected?: boolean;
  isLiveAvatarConfigured?: boolean;
  liveAvatarState?: string;
  statusMessage?: string;
  hasActiveStream?: boolean;
}

const DEFAULT_AVATAR = "/images/zaira-avatar.jpg";

export function InterviewerAvatar({
  isSpeaking,
  isThinking = false,
  onSkip,
  onSpeechEnd,
  audioBlob,
  mode = "hero",
  examinerName = "Zaira",
  examinerRole = "AI Interviewer (Age 20)",
  questionId,
  videoUrl,
  liveVideoRef,
  isLiveAvatarConnected = false,
  isLiveAvatarConfigured = false,
  liveAvatarState,
  statusMessage,
  hasActiveStream = false,
}: InterviewerAvatarProps) {
  // Custom avatar image or video (persisted in localStorage or state)
  const [avatarSrc, setAvatarSrc] = useState<string>(DEFAULT_AVATAR);
  const [isCustomAvatar, setIsCustomAvatar] = useState<boolean>(false);
  const [questionVideoSrc, setQuestionVideoSrc] = useState<string | null>(null);
  const [isVideoAvatar, setIsVideoAvatar] = useState<boolean>(false);
  
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Real-time audio energy (0.0 to 1.0)
  const [audioEnergy, setAudioEnergy] = useState<number>(0);

  // Audio references
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);

  const isSpeakingRef = useRef<boolean>(isSpeaking);
  isSpeakingRef.current = isSpeaking;

  // Check if a dedicated question video exists for this question
  useEffect(() => {
    if (videoUrl) {
      setQuestionVideoSrc(videoUrl);
      setIsVideoAvatar(true);
      return;
    }
    if (!questionId) {
      setQuestionVideoSrc(null);
      return;
    }

    const testPath = `/videos/questions/${questionId}.mp4`;
    fetch(testPath, { method: "HEAD" })
      .then((res) => {
        if (res.ok) {
          setQuestionVideoSrc(testPath);
          setIsVideoAvatar(true);
        } else {
          setQuestionVideoSrc(null);
          // If custom avatar is a video, keep video mode; else image mode
          setIsVideoAvatar(avatarSrc.startsWith("data:video") || avatarSrc.endsWith(".mp4") || avatarSrc.endsWith(".webm"));
        }
      })
      .catch(() => {
        setQuestionVideoSrc(null);
        setIsVideoAvatar(avatarSrc.startsWith("data:video") || avatarSrc.endsWith(".mp4") || avatarSrc.endsWith(".webm"));
      });
  }, [questionId, videoUrl, avatarSrc]);

  // Load custom avatar from localStorage if explicitly set for British Council examiner
  useEffect(() => {
    try {
      localStorage.removeItem("zaira_custom_avatar");
      const saved = localStorage.getItem("zaira_examiner_avatar_v1");
      if (saved) {
        setAvatarSrc(saved);
        setIsCustomAvatar(true);
        if (saved.startsWith("data:video") || saved.endsWith(".mp4") || saved.endsWith(".webm")) {
          setIsVideoAvatar(true);
        }
      }
    } catch {
      // ignore
    }
  }, []);

  const handleCustomAvatarUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type.startsWith("video/")) {
      const videoBlobUrl = URL.createObjectURL(file);
      setAvatarSrc(videoBlobUrl);
      setIsVideoAvatar(true);
      setIsCustomAvatar(true);
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      if (result) {
        setAvatarSrc(result);
        setIsVideoAvatar(false);
        setIsCustomAvatar(true);
        try {
          localStorage.setItem("zaira_examiner_avatar_v1", result);
        } catch {
          // ignore storage limit
        }
      }
    };
    reader.readAsDataURL(file);
    if (e.target) e.target.value = "";
  };

  const handleResetAvatar = () => {
    setAvatarSrc(DEFAULT_AVATAR);
    setIsCustomAvatar(false);
    setIsVideoAvatar(false);
    try {
      localStorage.removeItem("zaira_examiner_avatar_v1");
    } catch {
      // ignore
    }
  };

  // Video playback control
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !isVideoAvatar) return;

    if (isSpeaking) {
      video.currentTime = 0;
      video.play().catch((err) => console.warn("Video autoplay note:", err));
    } else {
      video.pause();
    }
  }, [isSpeaking, isVideoAvatar, questionVideoSrc, avatarSrc]);

  // Synchronized Audio Playback & Analysis
  useEffect(() => {
    if (!isSpeaking) {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      setAudioEnergy(0);
      return;
    }

    if (!audioBlob) return;

    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    audioRef.current = audio;

    // Connect Web Audio Analyser for live speech intensity
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
      analyser.fftSize = 128;
      analyser.smoothingTimeConstant = 0.25;
      analyserRef.current = analyser;

      source.connect(analyser);
      analyser.connect(ctx.destination);
    } catch (err) {
      console.warn("Web Audio Analyser fallback note:", err);
    }

    audio.onended = () => {
      URL.revokeObjectURL(audioUrl);
      if (audioRef.current === audio) {
        audioRef.current = null;
      }
      setAudioEnergy(0);
      onSpeechEnd?.();
    };

    audio.onerror = () => {
      URL.revokeObjectURL(audioUrl);
      if (audioRef.current === audio) {
        audioRef.current = null;
      }
      setAudioEnergy(0);
      onSpeechEnd?.();
    };

    audio.play().catch((err) => {
      console.warn("Audio autoplay note:", err);
      URL.revokeObjectURL(audioUrl);
      if (audioRef.current === audio) {
        audioRef.current = null;
      }
      setAudioEnergy(0);
      onSpeechEnd?.();
    });

    return () => {
      audio.pause();
      URL.revokeObjectURL(audioUrl);
      if (audioRef.current === audio) {
        audioRef.current = null;
      }
      setAudioEnergy(0);
    };
  }, [isSpeaking, audioBlob, onSpeechEnd]);

  // 60 FPS Real-Time Voice Waveform Animation Loop
  useEffect(() => {
    const freqData = new Uint8Array(64);
    let running = true;
    let fallbackPhase = 0;

    const loop = () => {
      if (!running) return;

      if (isSpeakingRef.current) {
        let energy = 0;
        if (audioRef.current && !audioRef.current.paused && analyserRef.current) {
          analyserRef.current.getByteFrequencyData(freqData);
          let sum = 0;
          for (let i = 2; i <= 24; i++) {
            sum += freqData[i];
          }
          energy = Math.min(1.0, (sum / (23 * 255)) * 1.6);
        } else {
          // Synthetic natural vocal modulation if Web Audio is suspended
          fallbackPhase += 0.16;
          const s = Math.sin(fallbackPhase) * 0.5 + 0.5;
          const wave = Math.sin(fallbackPhase * 0.4) * 0.3 + 0.7;
          energy = s * wave * 0.75;
        }
        setAudioEnergy((prev) => prev * 0.65 + energy * 0.35);
      } else {
        setAudioEnergy(0);
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
    setAudioEnergy(0);
    onSkip?.();
  }, [onSkip]);

  return (
    <div
      className={`tl-card overflow-hidden rounded-3xl relative bg-gradient-to-b from-[#0c0e18] via-[#07080f] to-[#040508] border transition-all duration-300 ${
        isSpeaking
          ? "border-teal-500/50 shadow-[0_0_35px_rgba(20,184,166,0.18)]"
          : isThinking
          ? "border-amber-400/40 shadow-[0_0_25px_rgba(251,191,36,0.14)]"
          : "border-white/10 shadow-[0_12px_48px_rgba(0,0,0,0.7)]"
      }`}
    >
      {/* Hidden file input for custom avatar photo or video upload */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*,video/mp4,video/webm"
        onChange={handleCustomAvatarUpload}
        className="hidden"
      />

      {/* Top Header Status & Avatar Customization */}
      <div className="absolute top-4 inset-x-4 z-20 flex items-center justify-between pointer-events-none">
        {/* Status Pill */}
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-black/60 backdrop-blur-md border border-white/10 text-xs font-medium text-white shadow-lg pointer-events-auto">
          {liveAvatarState === "CONNECTING" ? (
            <>
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
              <span className="text-amber-300 font-mono text-[11px]">
                Connecting LiveAvatar Lite WebRTC...
              </span>
            </>
          ) : liveAvatarState === "ERROR" ? (
            <>
              <span className="w-2 h-2 rounded-full bg-red-400" />
              <span className="text-red-300 font-mono text-[11px]" title={statusMessage}>
                LiveAvatar Offline (Fallback Active)
              </span>
            </>
          ) : isLiveAvatarConnected ? (
            <>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-emerald-300 font-mono text-[11px]">
                {examinerName} • {isSpeaking ? "Speaking" : "Attentive Listening"} (LiveAvatar WebRTC)
              </span>
            </>
          ) : isSpeaking ? (
            <>
              <span className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
              <span className="text-teal-300 font-mono text-[11px]">
                {examinerName} {isVideoAvatar ? "(Video Mode)" : "Speaking"}
              </span>
            </>
          ) : isThinking ? (
            <>
              <Sparkles className="w-3.5 h-3.5 text-amber-400 animate-spin" />
              <span className="text-amber-300 font-mono text-[11px]">Evaluating Response...</span>
            </>
          ) : (
            <>
              <Mic className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-zinc-300 font-mono text-[11px]">{examinerName} (Listening)</span>
            </>
          )}
        </div>

        {/* Change / Reset Photo Action Buttons */}
        <div className="flex items-center gap-1.5 pointer-events-auto">
          {isCustomAvatar && (
            <button
              onClick={handleResetAvatar}
              className="p-1.5 rounded-lg bg-black/60 hover:bg-black/90 text-zinc-300 hover:text-white border border-white/10 transition-all backdrop-blur-md shadow-sm"
              title="Reset to default British Council examiner"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-black/60 hover:bg-black/90 text-zinc-300 hover:text-white border border-white/10 text-xs transition-all backdrop-blur-md shadow-sm"
            title="Upload custom avatar video (.mp4) or portrait photo"
          >
            <Camera className="w-3.5 h-3.5 text-teal-400" />
            <span className="text-[11px] hidden sm:inline">Change Video / Photo</span>
          </button>
        </div>
      </div>

      {/* Viewport Framing for Crisp, Pristine Avatar Portrait or Video */}
      <div
        className={`relative w-full flex items-end justify-center overflow-hidden bg-black/40 ${
          mode === "compact"
            ? "h-[250px] sm:h-[280px]"
            : "h-[460px] sm:h-[500px] lg:h-[520px]"
        }`}
      >
        
        {/* Natural Ambient Aura Glowing with Real Speech Intensity */}
        <div
          className="absolute inset-0 pointer-events-none transition-opacity duration-300"
          style={{
            background: isSpeaking
              ? `radial-gradient(circle at 50% 40%, rgba(20, 184, 166, ${0.12 + audioEnergy * 0.2}) 0%, transparent 70%)`
              : isThinking
              ? "radial-gradient(circle at 50% 40%, rgba(251, 191, 36, 0.1) 0%, transparent 65%)"
              : "radial-gradient(circle at 50% 40%, rgba(16, 185, 129, 0.05) 0%, transparent 60%)",
          }}
        />

        {/* Media Frame: LiveAvatar WebRTC, Synchronized MP4 Video, or Photographic Portrait */}
        <div
          className={`relative w-full h-full max-w-[620px] flex items-end justify-center z-10 transition-transform duration-150 ${
            !isSpeaking && !isVideoAvatar && !isLiveAvatarConnected ? "avatar-idle-breathe" : ""
          }`}
          style={{
            transform: isSpeaking && !isVideoAvatar && !isLiveAvatarConnected
              ? `scale(${1 + audioEnergy * 0.015}) translateY(-${audioEnergy * 3}px)`
              : undefined,
          }}
        >
          <div className="relative w-full h-full flex items-end justify-center pointer-events-none select-none">
            {/* Live HeyGen WebRTC Video Element — ALWAYS mounted when configured so stream attachment never fails */}
            {isLiveAvatarConfigured && liveVideoRef && (
              <video
                ref={liveVideoRef}
                id="heygen-live-video"
                className={`w-full h-full object-contain object-bottom select-none transition-opacity duration-500 drop-shadow-[0_24px_48px_rgba(0,0,0,0.85)] ${
                  isLiveAvatarConnected ? "opacity-100 z-10" : "opacity-0 pointer-events-none z-0"
                }`}
                playsInline
                autoPlay
              />
            )}

            {/* Fallback photographic portrait or dedicated question video when WebRTC is not active */}
            {(!isLiveAvatarConnected || !isLiveAvatarConfigured) && (
              isVideoAvatar ? (
                <video
                  ref={videoRef}
                  src={questionVideoSrc || avatarSrc}
                  className="w-full h-full object-contain object-bottom pointer-events-none select-none drop-shadow-[0_24px_48px_rgba(0,0,0,0.85)]"
                  playsInline
                  autoPlay={isSpeaking}
                  onEnded={() => {
                    onSpeechEnd?.();
                  }}
                />
              ) : (
                <Image
                  src={avatarSrc}
                  alt="Zaira - AI Interviewer"
                  fill
                  sizes="(max-width: 768px) 100vw, (max-width: 1400px) 70vw, 800px"
                  priority
                  unoptimized
                  className="object-contain object-bottom pointer-events-none select-none drop-shadow-[0_24px_48px_rgba(0,0,0,0.85)]"
                />
              )
            )}
          </div>
        </div>

        {/* Elegant Bottom Shadow Vignette */}
        <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-[#040508] via-[#040508]/80 to-transparent pointer-events-none z-15" />

        {/* Bottom Floating Equalizer & Control Bar */}
        <div className="absolute bottom-4 inset-x-4 z-20 flex items-center justify-between pointer-events-none">
          {/* Live Soundwave Audio Visualizer */}
          <div className="inline-flex items-center gap-2.5 px-3.5 py-1.5 rounded-xl bg-black/70 backdrop-blur-md border border-white/10 shadow-lg pointer-events-auto">
            <Volume2 className={`w-3.5 h-3.5 ${isSpeaking ? "text-teal-400" : "text-zinc-500"}`} />
            
            {/* Dynamic Equalizer Frequency Bars */}
            <div className="flex items-end gap-1 h-3.5">
              {[0.4, 0.9, 0.6, 1.0, 0.5].map((factor, idx) => {
                const heightPercent = isSpeaking
                  ? Math.max(15, Math.min(100, (audioEnergy * factor + (idx % 2 === 0 ? 0.2 : 0.1)) * 100))
                  : 15;
                return (
                  <span
                    key={idx}
                    className={`w-1 rounded-full transition-all duration-75 ${
                      isSpeaking ? "bg-teal-400" : "bg-zinc-600"
                    }`}
                    style={{ height: `${heightPercent}%` }}
                  />
                );
              })}
            </div>

            <span className="text-[11px] font-mono text-zinc-300">
              {isSpeaking ? "Voice Active" : isThinking ? "Processing" : "Standby"}
            </span>
          </div>

          {/* Skip Audio Button */}
          {isSpeaking && onSkip && (
            <div className="pointer-events-auto">
              <button
                onClick={handleSkip}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-black/70 hover:bg-black/90 text-zinc-300 hover:text-white rounded-xl text-xs font-medium border border-white/10 transition-all backdrop-blur-md shadow-lg"
                aria-label="Skip question audio and proceed to answer"
              >
                <VolumeX className="w-3.5 h-3.5 text-zinc-400" />
                <span>Skip Audio</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
