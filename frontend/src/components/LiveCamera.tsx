"use client";

import { useEffect, useRef, useState } from "react";
import { Video, StopCircle, RefreshCcw, CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";
import axios from "axios";

export default function LiveCamera({ onAnalysisStart }: { onAnalysisStart: (sessionId: string) => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recordedChunks, setRecordedChunks] = useState<Blob[]>([]);
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);

  useEffect(() => {
    // Request camera permission on mount
    async function setupCamera() {
      try {
        const mediaStream = await navigator.mediaDevices.getUserMedia({ 
          video: { width: 1280, height: 720 }, 
          audio: true 
        });
        setStream(mediaStream);
        setHasPermission(true);
        if (videoRef.current) {
          videoRef.current.srcObject = mediaStream;
        }
      } catch (err) {
        console.error("Camera access denied:", err);
        setHasPermission(false);
      }
    }
    setupCamera();

    // Cleanup on unmount
    return () => {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const startRecording = () => {
    if (!stream) return;
    const recorder = new MediaRecorder(stream, { mimeType: "video/webm" });
    mediaRecorderRef.current = recorder;

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        setRecordedChunks((prev) => [...prev, event.data]);
      }
    };

    recorder.start();
    setIsRecording(true);
  };

  const stopRecordingAndAnalyze = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.onstop = async () => {
        // Stop the camera tracks so the indicator turns off
        if (stream) {
          stream.getTracks().forEach((track) => track.stop());
        }

        // Wait a tiny bit for the final chunk to append
        setTimeout(async () => {
          const blob = new Blob(recordedChunks, { type: "video/webm" });
          const formData = new FormData();
          // FastAPI endpoint expects a file
          formData.append("file", blob, "live_recording.webm");

          try {
            const res = await axios.post("http://localhost:8000/api/analyze", formData);
            onAnalysisStart(res.data.session_id);
          } catch (err) {
            console.error("Failed to upload recording", err);
          }
        }, 100);
      };

      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  if (hasPermission === false) {
    return (
      <div className="p-12 md:p-16 flex flex-col items-center justify-center text-center border border-dashed border-red-500/30 rounded-2xl bg-zinc-950/70 backdrop-blur-xl">
        <div className="w-14 h-14 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-5">
          <Video className="w-6 h-6 text-red-400" />
        </div>
        <h3 className="text-lg font-bold text-white mb-2">Camera Access Restricted</h3>
        <p className="text-xs md:text-sm text-white/50 max-w-md leading-relaxed">
          Please permit browser camera and microphone permissions to capture live communication takes in the studio.
        </p>
      </div>
    );
  }

  return (
    <motion.div 
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="w-full flex flex-col gap-6 max-w-4xl mx-auto"
    >
      <header className="border-b border-white/[0.07] pb-5">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-[10px] font-mono tracking-widest text-emerald-400/90 uppercase font-semibold">
            Zaira AI
          </span>
          <span className="text-white/20 text-xs">•</span>
          <span className="text-[10px] font-mono tracking-wider text-white/50 uppercase">
            AI Communication & Interview Assistance
          </span>
        </div>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-white mb-2">
          Live Studio
        </h1>
        <p className="text-xs md:text-sm text-white/50 max-w-xl leading-relaxed">
          Record yourself directly in the browser for high-speed multi-modal analysis across delivery, presence, and speech metrics.
        </p>
      </header>

      <div className="relative rounded-2xl overflow-hidden bg-black aspect-video border border-white/[0.08] shadow-2xl">
        <video 
          ref={videoRef} 
          autoPlay 
          playsInline 
          muted 
          className="w-full h-full object-cover transform scale-x-[-1]" // Mirror camera naturally
        />
        
        {/* HUD OVERLAY */}
        <div className="absolute top-4 left-4 bg-black/60 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 flex items-center gap-2 shadow-lg">
          {isRecording ? (
            <>
              <div className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
              <span className="text-[11px] font-mono font-bold text-red-400 tracking-wider">REC</span>
            </>
          ) : (
            <>
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
              <span className="text-[11px] font-mono font-bold text-emerald-400 tracking-wider">STUDIO READY</span>
            </>
          )}
        </div>

        {/* CONTROLS */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-4">
          {!isRecording ? (
            <button 
              onClick={startRecording}
              className="bg-red-500 hover:bg-red-600 text-white w-14 h-14 rounded-full flex items-center justify-center shadow-[0_0_20px_rgba(239,68,68,0.4)] transition-all hover:scale-105 active:scale-95"
              aria-label="Start Recording"
            >
              <div className="w-5 h-5 bg-white rounded-full" />
            </button>
          ) : (
            <button 
              onClick={stopRecordingAndAnalyze}
              className="bg-white/10 hover:bg-white/20 backdrop-blur-md border border-white/20 text-white px-6 py-2.5 rounded-full flex items-center gap-2 font-semibold text-xs md:text-sm transition-all hover:scale-105 active:scale-95 shadow-xl"
            >
              <StopCircle className="w-4 h-4 text-red-400" />
              <span>Finish & Analyze</span>
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
}
