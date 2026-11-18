"use client";

import React, { useRef } from "react";
import Image from "next/image";
import { VolumeX, Radio, Sparkles, RefreshCw } from "lucide-react";
import { LiveAvatarDiagnostics } from "../hooks/useLiveAvatar";

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
  diagnostics?: LiveAvatarDiagnostics;
  onReconnect?: () => void;
}

const DEFAULT_AVATAR = "/images/zaira-avatar.jpg";

export function InterviewerAvatar({
  isSpeaking,
  isThinking = false,
  onSkip,
  mode = "hero",
  examinerName = "Zaira",
  liveVideoRef,
  isLiveAvatarConnected = false,
  isLiveAvatarConfigured = false,
  liveAvatarState,
  hasActiveStream = false,
  onReconnect,
}: InterviewerAvatarProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Live video stream is genuinely active and ready to display
  const isVideoLiveReady =
    Boolean(isLiveAvatarConfigured && hasActiveStream && (isLiveAvatarConnected || liveAvatarState === "CONNECTED" || liveAvatarState === "SPEAKING"));

  const isConnecting = liveAvatarState === "CONNECTING";
  const isOffline = !isLiveAvatarConfigured || liveAvatarState === "ERROR" || liveAvatarState === "UNCONFIGURED" || (!isConnecting && !isVideoLiveReady);

  return (
    <div
      ref={containerRef}
      className={`relative rounded-3xl overflow-hidden border border-white/[0.08] bg-gradient-to-b from-[#090b10] via-[#06070a] to-[#040508] shadow-2xl transition-all duration-300 select-none ${
        mode === "compact" ? "p-3 sm:p-4" : "p-4 sm:p-6"
      }`}
    >
      {/* Top Header Status Badge */}
      <div className="absolute top-4 inset-x-4 z-20 flex items-center justify-between pointer-events-none">
        {/* Status Pill */}
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-black/75 backdrop-blur-md border border-white/10 text-xs font-medium text-white shadow-lg pointer-events-auto">
          {isConnecting ? (
            <>
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
              <span className="text-amber-300 font-mono text-[11px]">
                Connecting Video Stream...
              </span>
            </>
          ) : isVideoLiveReady ? (
            <>
              <span className={`w-2 h-2 rounded-full ${isSpeaking ? "bg-emerald-400 animate-pulse" : "bg-teal-400"}`} />
              <span className="text-emerald-300 font-mono text-[11px] flex items-center gap-1.5">
                <Radio className={`w-3 h-3 ${isSpeaking ? "text-emerald-400 animate-pulse" : "text-teal-400"}`} />
                <span>{examinerName} • {isSpeaking ? "Speaking" : "Listening"}</span>
              </span>
            </>
          ) : isThinking ? (
            <>
              <Sparkles className="w-3.5 h-3.5 text-amber-400 animate-spin" />
              <span className="text-amber-300 font-mono text-[11px]">Evaluating Response...</span>
            </>
          ) : isSpeaking ? (
            <>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-emerald-300 font-mono text-[11px]">
                {examinerName} • Speaking
              </span>
            </>
          ) : (
            <>
              <span className="w-2 h-2 rounded-full bg-zinc-400" />
              <span className="text-zinc-300 font-mono text-[11px]">{examinerName} • Listening</span>
            </>
          )}
        </div>

        {/* Retry Video option if live stream is offline */}
        {isOffline && isLiveAvatarConfigured && onReconnect && (
          <button
            onClick={onReconnect}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-black/60 hover:bg-black/90 text-zinc-400 hover:text-white border border-white/10 text-[11px] font-mono transition-all backdrop-blur-md pointer-events-auto shadow-sm"
            title="Retry connecting live avatar video stream"
          >
            <RefreshCw className="w-3 h-3 text-teal-400" />
            <span className="hidden sm:inline">Retry Video</span>
          </button>
        )}
      </div>

      {/* Viewport Framing for Avatar Portrait or Video */}
      <div
        className={`relative w-full flex items-end justify-center overflow-hidden bg-black/40 rounded-2xl ${
          mode === "compact"
            ? "h-[250px] sm:h-[280px]"
            : "h-[440px] sm:h-[480px] lg:h-[500px]"
        }`}
      >
        {/* Subtle Ambient Aura */}
        <div
          className="absolute inset-0 pointer-events-none transition-opacity duration-500"
          style={{
            background: isSpeaking
              ? "radial-gradient(circle at 50% 40%, rgba(20, 184, 166, 0.16) 0%, transparent 70%)"
              : isThinking
              ? "radial-gradient(circle at 50% 40%, rgba(251, 191, 36, 0.12) 0%, transparent 65%)"
              : "radial-gradient(circle at 50% 40%, rgba(16, 185, 129, 0.05) 0%, transparent 60%)",
          }}
        />

        {/* Media Frame Container */}
        <div className="relative w-full h-full max-w-[620px] flex items-end justify-center z-10">
          <div className="relative w-full h-full flex items-end justify-center select-none">
            {/* Live HeyGen WebRTC Video Element */}
            {isLiveAvatarConfigured && liveVideoRef && (
              <video
                ref={liveVideoRef}
                id="heygen-live-video"
                className={`w-full h-full object-contain object-bottom select-none transition-opacity duration-700 drop-shadow-[0_24px_48px_rgba(0,0,0,0.85)] ${
                  isVideoLiveReady ? "opacity-100 z-10" : "opacity-0 pointer-events-none z-0"
                }`}
                playsInline
                autoPlay
                muted={false}
              />
            )}

            {/* Connecting stage placeholder with sleek loading shimmer */}
            {isConnecting && !isVideoLiveReady && (
              <div className="w-full h-full flex flex-col items-center justify-center space-y-4 p-8 text-center animate-fadeIn z-5">
                <div className="relative w-16 h-16 flex items-center justify-center">
                  <div className="absolute inset-0 rounded-full border-2 border-teal-500/20 animate-ping" />
                  <div className="w-14 h-14 rounded-full border-2 border-teal-500/30 border-t-teal-400 animate-spin flex items-center justify-center">
                    <Radio className="w-5 h-5 text-teal-400 animate-pulse" />
                  </div>
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-medium text-white font-mono">Initializing Interviewer Stream</p>
                  <p className="text-xs text-zinc-400">Establishing real-time video connection with Zaira...</p>
                </div>
              </div>
            )}

            {/* Fallback photographic portrait when live video is not active */}
            {!isVideoLiveReady && !isConnecting && (
              <Image
                src={DEFAULT_AVATAR}
                alt="Zaira - AI Interviewer"
                fill
                sizes="(max-width: 768px) 100vw, (max-width: 1400px) 70vw, 800px"
                priority
                unoptimized
                className="object-contain object-bottom pointer-events-none select-none drop-shadow-[0_24px_48px_rgba(0,0,0,0.85)] z-0 transition-opacity duration-500"
              />
            )}
          </div>
        </div>

        {/* Elegant Bottom Shadow Vignette */}
        <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-[#040508] via-[#040508]/80 to-transparent pointer-events-none z-15" />

        {/* Skip Audio Button (Bottom-Right, only while speaking) */}
        {isSpeaking && onSkip && (
          <div className="absolute bottom-4 right-4 z-20 pointer-events-auto">
            <button
              onClick={onSkip}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-black/75 hover:bg-black/95 text-zinc-300 hover:text-white rounded-xl text-xs font-medium border border-white/10 transition-all backdrop-blur-md shadow-lg font-mono"
              aria-label="Skip question audio and proceed to answer"
            >
              <VolumeX className="w-3.5 h-3.5 text-zinc-400" />
              <span>Skip Speech</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
