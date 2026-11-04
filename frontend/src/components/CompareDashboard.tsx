"use client";

import { useState } from "react";
import { UploadCloud, CheckCircle2, SplitSquareHorizontal, RotateCcw } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import axios from "axios";
import CategoryCards from "./CategoryCards";
import TelemetrySection from "./TelemetrySection";

export default function CompareDashboard() {
  const [fileA, setFileA] = useState<File | null>(null);
  const [fileB, setFileB] = useState<File | null>(null);

  const [isUploading, setIsUploading] = useState(false);

  // State for A
  const [statusA, setStatusA] = useState("");
  const [progressA, setProgressA] = useState(0);
  const [completeA, setCompleteA] = useState(false);

  // State for B
  const [statusB, setStatusB] = useState("");
  const [progressB, setProgressB] = useState(0);
  const [completeB, setCompleteB] = useState(false);

  const startComparison = async () => {
    if (!fileA || !fileB) return;
    setIsUploading(true);
    setCompleteA(false);
    setCompleteB(false);
    setProgressA(0);
    setProgressB(0);
    setStatusA("Uploading recording A...");
    setStatusB("Uploading recording B...");

    const uploadAndListen = async (file: File, setStatus: any, setProgress: any, setComplete: any) => {
      const formData = new FormData();
      formData.append("file", file);

      try {
        const res = await axios.post("http://localhost:8000/api/analyze", formData, {
          onUploadProgress: (p) => {
            if (p.total) setProgress(Math.floor(((p.loaded * 100) / p.total) * 0.1));
          },
        });
        const sid = res.data.session_id;

        const ws = new WebSocket(`ws://localhost:8000/api/ws/status/${sid}`);
        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          setStatus(data.status);
          setProgress(data.progress);
          if (data.progress === 100) {
            setComplete(true);
            ws.close();
          }
        };
      } catch {
        setStatus("Analysis failed.");
      }
    };

    // Run both simultaneously
    uploadAndListen(fileA, setStatusA, setProgressA, setCompleteA);
    uploadAndListen(fileB, setStatusB, setProgressB, setCompleteB);
  };

  const showResults = completeA && completeB;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="w-full flex flex-col gap-8 max-w-5xl mx-auto"
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
          Side-by-Side Comparison
        </h1>
        <p className="text-xs md:text-sm text-white/50 max-w-2xl leading-relaxed">
          Analyze two video recordings concurrently to benchmark speaking pace, body language, narrative coherence, and overall communication efficacy.
        </p>
      </header>

      <AnimatePresence mode="wait">
        {!isUploading && !showResults && (
          <motion.div key="upload" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="flex flex-col md:flex-row items-stretch gap-6 relative">
              {/* Person A */}
              <div className="flex-1 p-8 rounded-2xl border border-dashed border-white/15 hover:border-emerald-500/50 transition-all bg-zinc-950/60 backdrop-blur-xl flex flex-col items-center justify-center text-center cursor-pointer relative group">
                <input
                  type="file"
                  accept="video/*"
                  onChange={(e) => e.target.files && setFileA(e.target.files[0])}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-20"
                />
                <div className="w-12 h-12 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-center mb-3 group-hover:scale-105 group-hover:border-emerald-500/40 transition-all">
                  <UploadCloud className="w-5 h-5 text-emerald-400/80" />
                </div>
                <span className="text-[10px] font-mono uppercase tracking-widest text-white/40 mb-1">Performer A</span>
                <h3 className="text-base font-semibold text-white mb-1 truncate max-w-[220px]">
                  {fileA ? fileA.name : "Select Candidate Video"}
                </h3>
                <p className="text-xs text-white/40">MP4, WEBM, or MOV · Max 200MB</p>
                {fileA && (
                  <div className="mt-3 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-[11px] font-medium">
                    <CheckCircle2 className="w-3 h-3" />
                    <span>Selected</span>
                  </div>
                )}
              </div>

              {/* VS Badge */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10 hidden md:flex items-center justify-center w-11 h-11 rounded-full bg-[#0a0a0f] border border-white/15 text-emerald-400 font-mono font-bold text-xs shadow-2xl">
                VS
              </div>

              {/* Person B */}
              <div className="flex-1 p-8 rounded-2xl border border-dashed border-white/15 hover:border-emerald-500/50 transition-all bg-zinc-950/60 backdrop-blur-xl flex flex-col items-center justify-center text-center cursor-pointer relative group">
                <input
                  type="file"
                  accept="video/*"
                  onChange={(e) => e.target.files && setFileB(e.target.files[0])}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-20"
                />
                <div className="w-12 h-12 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-center mb-3 group-hover:scale-105 group-hover:border-emerald-500/40 transition-all">
                  <UploadCloud className="w-5 h-5 text-emerald-400/80" />
                </div>
                <span className="text-[10px] font-mono uppercase tracking-widest text-white/40 mb-1">Performer B</span>
                <h3 className="text-base font-semibold text-white mb-1 truncate max-w-[220px]">
                  {fileB ? fileB.name : "Select Candidate Video"}
                </h3>
                <p className="text-xs text-white/40">MP4, WEBM, or MOV · Max 200MB</p>
                {fileB && (
                  <div className="mt-3 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-[11px] font-medium">
                    <CheckCircle2 className="w-3 h-3" />
                    <span>Selected</span>
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-center mt-10">
              <button
                disabled={!fileA || !fileB}
                onClick={startComparison}
                className={`relative px-8 py-3.5 rounded-xl font-semibold text-black bg-gradient-to-r from-emerald-500 to-teal-500 shadow-[0_0_25px_rgba(16,185,129,0.25)] transition-all ${
                  !fileA || !fileB
                    ? "opacity-40 cursor-not-allowed grayscale"
                    : "hover:from-emerald-400 hover:to-teal-400 hover:-translate-y-0.5 active:translate-y-0"
                }`}
              >
                Launch Comparative Analysis
              </button>
            </div>
          </motion.div>
        )}

        {isUploading && !showResults && (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="grid grid-cols-1 md:grid-cols-2 gap-6"
          >
            <div className="p-8 rounded-2xl border border-white/[0.07] bg-zinc-950/70 backdrop-blur-xl flex flex-col items-center text-center">
              <span className="text-[10px] font-mono uppercase tracking-widest text-white/40 mb-2">Performer A</span>
              <h3 className="text-sm font-semibold text-white mb-6 truncate max-w-[240px]">{fileA?.name || "Person A"}</h3>
              <div className="relative w-24 h-24 mb-6">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="4" />
                  <circle
                    cx="50"
                    cy="50"
                    r="45"
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="4"
                    strokeDasharray={`${2 * Math.PI * 45}`}
                    strokeDashoffset={`${2 * Math.PI * 45 * (1 - progressA / 100)}`}
                    className="transition-all duration-500 ease-out"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-xl font-mono font-bold text-white">{progressA}%</span>
                </div>
              </div>
              <p className="text-xs text-white/50">{statusA}</p>
            </div>

            <div className="p-8 rounded-2xl border border-white/[0.07] bg-zinc-950/70 backdrop-blur-xl flex flex-col items-center text-center">
              <span className="text-[10px] font-mono uppercase tracking-widest text-white/40 mb-2">Performer B</span>
              <h3 className="text-sm font-semibold text-white mb-6 truncate max-w-[240px]">{fileB?.name || "Person B"}</h3>
              <div className="relative w-24 h-24 mb-6">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="4" />
                  <circle
                    cx="50"
                    cy="50"
                    r="45"
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="4"
                    strokeDasharray={`${2 * Math.PI * 45}`}
                    strokeDashoffset={`${2 * Math.PI * 45 * (1 - progressB / 100)}`}
                    className="transition-all duration-500 ease-out"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-xl font-mono font-bold text-white">{progressB}%</span>
                </div>
              </div>
              <p className="text-xs text-white/50">{statusB}</p>
            </div>
          </motion.div>
        )}

        {showResults && (
          <motion.div key="results" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-8">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 relative">
              {/* VS Divider Line for Results */}
              <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-px bg-white/[0.07] hidden md:block" />

              {/* Person A Results */}
              <div className="flex flex-col gap-6 md:pr-4">
                <div className="text-center">
                  <span className="text-[10px] font-mono uppercase tracking-widest text-emerald-400/90 font-semibold">Candidate 01</span>
                  <h3 className="text-xl font-bold text-white tracking-tight mt-0.5">Person A</h3>
                </div>
                <div className="p-6 rounded-2xl border border-white/[0.07] bg-zinc-950/70 backdrop-blur-xl flex flex-col items-center justify-center text-center">
                  <span className="text-[10px] font-mono text-white/40 uppercase tracking-widest mb-1">Overall Performance</span>
                  <div className="text-5xl font-mono font-bold text-white mb-2">85</div>
                  <span className="text-emerald-400 bg-emerald-500/15 border border-emerald-500/30 px-3 py-0.5 rounded-full text-xs font-medium">
                    Exemplary Delivery
                  </span>
                </div>
                <CategoryCards />
              </div>

              {/* Person B Results */}
              <div className="flex flex-col gap-6 md:pl-4">
                <div className="text-center">
                  <span className="text-[10px] font-mono uppercase tracking-widest text-teal-400/90 font-semibold">Candidate 02</span>
                  <h3 className="text-xl font-bold text-white tracking-tight mt-0.5">Person B</h3>
                </div>
                <div className="p-6 rounded-2xl border border-white/[0.07] bg-zinc-950/70 backdrop-blur-xl flex flex-col items-center justify-center text-center">
                  <span className="text-[10px] font-mono text-white/40 uppercase tracking-widest mb-1">Overall Performance</span>
                  <div className="text-5xl font-mono font-bold text-white mb-2">72</div>
                  <span className="text-amber-400 bg-amber-500/15 border border-amber-500/30 px-3 py-0.5 rounded-full text-xs font-medium">
                    Competent Delivery
                  </span>
                </div>
                <CategoryCards />
              </div>
            </div>

            <div className="flex justify-center mt-6">
              <button
                onClick={() => {
                  setIsUploading(false);
                  setFileA(null);
                  setFileB(null);
                }}
                className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl font-medium text-xs md:text-sm text-white/80 border border-white/10 hover:border-white/20 bg-white/[0.03] hover:bg-white/[0.08] transition-all"
              >
                <RotateCcw className="w-3.5 h-3.5 text-white/60" />
                <span>Compare New Recordings</span>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
