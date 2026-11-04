import React from "react";
import { FileText, Mic, Eye } from "lucide-react";

interface TelemetryData {
  pitch_variation_hz?: number | null;
  speaking_rate_wpm?: number | null;
  pause_duration_sec?: number | null;
  total_pause_sec?: number | null;
  pause_count?: number | null;
  filler_word_count?: number | null;
  word_count?: number | null;
  face_presence_ratio?: number | null;
  face_detected?: boolean;
  head_movement_count?: number | null;
  head_movement_rate_per_min?: number | null;
  blink_count?: number | null;
  duration_seconds?: number | null;
}

interface TelemetrySectionProps {
  telemetry?: TelemetryData;
  transcript?: string;
  modalityStatus?: {
    audio?: string;
    visual?: string;
    transcript?: string;
  };
}

export default function TelemetrySection({
  telemetry,
  transcript,
  modalityStatus,
}: TelemetrySectionProps) {
  const pitchDisplay =
    telemetry?.pitch_variation_hz != null
      ? `${telemetry.pitch_variation_hz.toFixed(1)} Hz`
      : "Not measured";

  const wpmDisplay =
    telemetry?.speaking_rate_wpm != null
      ? `${Math.round(telemetry.speaking_rate_wpm)} WPM`
      : "Not measured";

  const pauseDisplay =
    telemetry?.pause_duration_sec != null
      ? `${telemetry.pause_duration_sec.toFixed(1)}s avg`
      : "Not measured";

  const facePresenceDisplay =
    telemetry?.face_presence_ratio != null && telemetry?.face_detected
      ? `${Math.round(telemetry.face_presence_ratio * 100)}% In Frame`
      : telemetry?.face_detected === false
      ? "No face detected"
      : "Not measured";

  const headMovementDisplay =
    telemetry?.head_movement_count != null
      ? `${telemetry.head_movement_count} Observed`
      : "Not measured";

  const hasTranscript = Boolean(transcript && transcript.trim().length > 0);

  return (
    <div className="w-full flex flex-col gap-5 text-white/80">
      <div className="uppercase tracking-widest text-[10px] font-mono font-semibold text-emerald-400/90 mb-1">
        Observed Signal Telemetry
      </div>

      {/* Spoken Transcript Box */}
      <div className="border border-white/[0.07] rounded-xl bg-zinc-950/70 backdrop-blur-xl p-5 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-white font-medium text-xs">
            <FileText className="w-3.5 h-3.5 text-emerald-400" />
            <span>Spoken Transcript Audit</span>
          </div>
          <span className="text-[10px] uppercase font-mono tracking-wider bg-white/5 border border-white/10 px-2 py-0.5 rounded text-white/60">
            {modalityStatus?.transcript === "available" ? "Whisper ASR (Transcribed)" : "Whisper ASR"}
          </span>
        </div>
        {hasTranscript ? (
          <p className="text-xs md:text-sm leading-relaxed text-white/80 italic border-l-2 border-emerald-500/50 pl-3">
            &quot;{transcript}&quot;
          </p>
        ) : (
          <p className="text-xs md:text-sm leading-relaxed text-zinc-500 italic border-l-2 border-zinc-700/50 pl-3">
            No spoken transcript captured from the recording.
          </p>
        )}
      </div>

      {/* Acoustic Signals Box */}
      <div className="border border-white/[0.07] rounded-xl bg-zinc-950/70 backdrop-blur-xl p-5 flex flex-col gap-3">
        <div className="flex items-center gap-2 text-white font-medium text-xs mb-1">
          <Mic className="w-3.5 h-3.5 text-teal-400" />
          <span>Acoustic DSP Metrics</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="bg-[#0a0a0f] p-3.5 rounded-lg border border-white/[0.05] flex flex-col gap-1">
            <span className="text-[10px] text-white/40 font-mono uppercase tracking-wider">Pitch Variance</span>
            <span className="font-mono text-lg font-semibold text-white">{pitchDisplay}</span>
          </div>
          <div className="bg-[#0a0a0f] p-3.5 rounded-lg border border-white/[0.05] flex flex-col gap-1">
            <span className="text-[10px] text-white/40 font-mono uppercase tracking-wider">Speaking Rate</span>
            <span className="font-mono text-lg font-semibold text-white">{wpmDisplay}</span>
          </div>
          <div className="bg-[#0a0a0f] p-3.5 rounded-lg border border-white/[0.05] flex flex-col gap-1">
            <span className="text-[10px] text-white/40 font-mono uppercase tracking-wider">Pause Duration</span>
            <span className="font-mono text-lg font-semibold text-white">{pauseDisplay}</span>
          </div>
        </div>
      </div>

      {/* Visual Signals Box */}
      <div className="border border-white/[0.07] rounded-xl bg-zinc-950/70 backdrop-blur-xl p-5 flex flex-col gap-3">
        <div className="flex items-center gap-2 text-white font-medium text-xs mb-1">
          <Eye className="w-3.5 h-3.5 text-emerald-400" />
          <span>Computer Vision Telemetry (Face & Camera Presence)</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="bg-[#0a0a0f] p-3.5 rounded-lg border border-white/[0.05] flex flex-col gap-1">
            <span className="text-[10px] text-white/40 font-mono uppercase tracking-wider">Camera Face Presence</span>
            <span className={`font-mono text-lg font-semibold ${telemetry?.face_detected ? "text-emerald-400" : "text-zinc-400"}`}>
              {facePresenceDisplay}
            </span>
          </div>
          <div className="bg-[#0a0a0f] p-3.5 rounded-lg border border-white/[0.05] flex flex-col gap-1">
            <span className="text-[10px] text-white/40 font-mono uppercase tracking-wider">Head Movement Count</span>
            <span className="font-mono text-lg font-semibold text-white">{headMovementDisplay}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
