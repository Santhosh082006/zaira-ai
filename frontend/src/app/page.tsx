"use client";

import { useState, useRef } from "react";
import { UploadCloud, CheckCircle2, Video, FileVideo, BrainCircuit, SplitSquareHorizontal, Sparkles, AlertCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import axios from "axios";
import CategoryCards from "../components/CategoryCards";
import TelemetrySection from "../components/TelemetrySection";
import LiveCamera from "../components/LiveCamera";
import CompareDashboard from "../components/CompareDashboard";
import InterviewDashboard from "../components/InterviewDashboard";

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState("interview");
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [statusText, setStatusText] = useState("");
  const [progress, setProgress] = useState(0);
  const [analysisComplete, setAnalysisComplete] = useState(false);
  const [analysisData, setAnalysisData] = useState<any>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const fetchAnalysisResult = async (sid: string) => {
    try {
      const res = await axios.get(`http://localhost:8000/api/analysis/${sid}`);
      if (res.data) {
        if (res.data.status === "completed") {
          setAnalysisData(res.data);
          setAnalysisComplete(true);
          setIsUploading(false);
        } else if (res.data.status === "failed") {
          setStatusText(`Analysis failed: ${res.data.error || "Unknown pipeline error"}`);
          setIsUploading(false);
        }
      }
    } catch (err) {
      console.error("Failed to load analysis results", err);
      setStatusText("Failed to retrieve analysis results from server.");
      setIsUploading(false);
    }
  };

  const startAnalysis = async () => {
    if (!file) return;
    setIsUploading(true);
    setAnalysisComplete(false);
    setAnalysisData(null);
    setProgress(0);
    setStatusText("Uploading footage to secure analysis pipeline...");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await axios.post("http://localhost:8000/api/analyze", formData, {
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            // Cap upload progress at 10% so the rest is used for AI processing telemetry
            setProgress(Math.floor(percentCompleted * 0.1));
          }
        }
      });
      const sid = res.data.session_id;
      listenToSession(sid);
    } catch (err) {
      console.error(err);
      setStatusText("Analysis failed. Please check server connection.");
    }
  };

  const listenToSession = (sid: string) => {
    setIsUploading(true);
    setAnalysisComplete(false);
    setAnalysisData(null);
    setProgress(0);
    setSessionId(sid);
    
    const ws = new WebSocket(`ws://localhost:8000/api/ws/status/${sid}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setStatusText(data.status);
      setProgress(data.progress);

      if (data.progress === 100) {
        fetchAnalysisResult(sid);
        ws.close();
      } else if (data.status && data.status.startsWith("Error:")) {
        setIsUploading(false);
        setStatusText(data.status);
        ws.close();
      }
    };
  };

  return (
    <div className="flex flex-col md:flex-row min-h-screen bg-[#050508] text-zinc-100">
      {/* MOBILE / RESPONSIVE TOP NAVIGATION */}
      <div className="md:hidden flex flex-col p-4 border-b border-white/[0.08] sticky top-0 z-50 bg-[#07080c]/90 backdrop-blur-xl">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-[0_0_12px_rgba(16,185,129,0.3)]">
              <BrainCircuit className="text-black w-4 h-4" />
            </div>
            <span className="font-bold text-base tracking-tight text-white">Zaira <span className="text-emerald-400 text-xs font-semibold">AI</span></span>
          </div>
          <span className="text-[10px] uppercase font-mono tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Active
          </span>
        </div>
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
          <button 
            onClick={() => setActiveTab("interview")}
            className={`px-3 py-1.5 rounded-lg whitespace-nowrap transition-all font-medium ${
              activeTab === "interview" 
                ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30" 
                : "text-zinc-400 hover:text-white"
            }`}
          >
            AI Interview
          </button>
          <button 
            onClick={() => setActiveTab("upload")}
            className={`px-3 py-1.5 rounded-lg whitespace-nowrap transition-all font-medium ${
              activeTab === "upload" 
                ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30" 
                : "text-zinc-400 hover:text-white"
            }`}
          >
            Analyze Existing Video
          </button>
          <button 
            onClick={() => setActiveTab("live")}
            className={`px-3 py-1.5 rounded-lg whitespace-nowrap transition-all font-medium ${
              activeTab === "live" 
                ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30" 
                : "text-zinc-400 hover:text-white"
            }`}
          >
            Live Studio
          </button>
          <button 
            onClick={() => setActiveTab("compare")}
            className={`px-3 py-1.5 rounded-lg whitespace-nowrap transition-all font-medium ${
              activeTab === "compare" 
                ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30" 
                : "text-zinc-400 hover:text-white"
            }`}
          >
            Compare & Assess
          </button>
        </div>
      </div>

      {/* DESKTOP SIDEBAR */}
      <aside className="w-[280px] bg-[#07080c] border-r border-white/[0.07] p-6 flex flex-col justify-between hidden md:flex shrink-0">
        <div>
          {/* Brand Logo & Subtitle */}
          <div className="flex items-center gap-3 mb-8 pb-4 border-b border-white/[0.06]">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-[0_0_16px_rgba(16,185,129,0.35)] shrink-0">
              <BrainCircuit className="text-black w-4.5 h-4.5" />
            </div>
            <div>
              <div className="font-bold text-base tracking-tight text-white leading-tight">
                Zaira <span className="text-emerald-400 text-xs font-semibold ml-0.5">AI</span>
              </div>
              <div className="text-[10px] text-zinc-500 font-medium tracking-wider uppercase">
                AI Communication & Interview Assistance
              </div>
            </div>
          </div>

          <nav className="space-y-6">
            {/* WORKFLOW 1: INTERVIEW & PERFORMANCE */}
            <div>
              <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-2.5 px-3">
                Interview & Performance
              </div>
              <div className="space-y-1">
                <button 
                  onClick={() => setActiveTab("interview")}
                  className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl transition-all text-left ${
                    activeTab === "interview" 
                      ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/25 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] font-medium" 
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]"
                  }`}
                >
                  <BrainCircuit className={`w-4 h-4 shrink-0 ${activeTab === "interview" ? "text-emerald-400" : "text-zinc-500"}`} />
                  <span className="text-sm">AI Interview</span>
                </button>
                <button 
                  onClick={() => setActiveTab("upload")}
                  className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl transition-all text-left ${
                    activeTab === "upload" 
                      ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/25 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] font-medium" 
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]"
                  }`}
                >
                  <FileVideo className={`w-4 h-4 shrink-0 ${activeTab === "upload" ? "text-emerald-400" : "text-zinc-500"}`} />
                  <span className="text-sm">Analyze Existing Video</span>
                </button>
                <button 
                  onClick={() => setActiveTab("live")}
                  className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl transition-all text-left ${
                    activeTab === "live" 
                      ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/25 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] font-medium" 
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]"
                  }`}
                >
                  <Video className={`w-4 h-4 shrink-0 ${activeTab === "live" ? "text-emerald-400" : "text-zinc-500"}`} />
                  <span className="text-sm">Live Studio</span>
                </button>
              </div>
            </div>

            {/* WORKFLOW 2: COMPARE & ASSESS */}
            <div>
              <div className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest mb-2.5 px-3">
                Compare & Assess
              </div>
              <div className="space-y-1">
                <button 
                  onClick={() => setActiveTab("compare")}
                  className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl transition-all text-left ${
                    activeTab === "compare" 
                      ? "bg-emerald-500/10 text-emerald-300 border border-emerald-500/25 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] font-medium" 
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]"
                  }`}
                >
                  <SplitSquareHorizontal className={`w-4 h-4 shrink-0 ${activeTab === "compare" ? "text-emerald-400" : "text-zinc-500"}`} />
                  <span className="text-sm">Compare & Assess</span>
                </button>
              </div>
            </div>
          </nav>
        </div>

        {/* Sidebar Footer */}
        <div className="pt-4 border-t border-white/[0.06] flex items-center justify-between text-[11px] text-zinc-500">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 tl-animate-pulse" />
            <span>Telemetry Active</span>
          </div>
          <span className="font-mono text-[10px] text-zinc-600">v2.6</span>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      {activeTab === "interview" ? (
        <InterviewDashboard />
      ) : (
        <main className="flex-1 p-6 md:p-10 relative overflow-y-auto">
          <div className="max-w-4xl mx-auto relative z-10">
            
            {activeTab === "upload" && (
              <>
                <header className="mb-8">
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/[0.03] border border-white/[0.07] text-[11px] font-medium text-zinc-400 uppercase tracking-wider mb-2">
                    <FileVideo className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Video Ingestion & Multimodal Audit</span>
                  </div>
                  <h1 className="text-3xl md:text-4xl font-bold tracking-tight text-white mb-2">
                    Analyze Communication Footage
                  </h1>
                  <p className="text-zinc-400 text-sm md:text-base leading-relaxed">
                    Upload recorded speaking footage to receive comprehensive multimodal feedback across verbal structure, acoustic delivery, and computer-vision presence signals.
                  </p>
                </header>

                <AnimatePresence mode="wait">
                  {!isUploading && !analysisComplete && (
                    <motion.div 
                      key="upload-zone"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      className="tl-card border-dashed border-2 border-white/[0.12] hover:border-emerald-500/40 transition-all p-12 md:p-16 flex flex-col items-center justify-center text-center cursor-pointer relative group"
                    >
                      <input 
                        type="file" 
                        accept="video/*" 
                        onChange={handleFileChange}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                      />
                      <div className="w-16 h-16 rounded-2xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-center mb-5 group-hover:border-emerald-500/30 group-hover:scale-105 transition-all">
                        <UploadCloud className="w-7 h-7 text-zinc-400 group-hover:text-emerald-400 transition-colors" />
                      </div>
                      <h3 className="text-lg md:text-xl font-semibold text-white mb-1.5">
                        {file ? file.name : "Select or drag recording file"}
                      </h3>
                      <p className="text-xs md:text-sm text-zinc-500 mb-6 font-mono">
                        Supported: MP4, WEBM, MOV · Maximum 200MB
                      </p>

                      {file && (
                        <button 
                          onClick={(e) => {
                            e.preventDefault();
                            startAnalysis();
                          }}
                          className="relative z-20 px-8 py-3 rounded-xl font-semibold text-black bg-gradient-to-r from-emerald-400 to-emerald-500 hover:from-emerald-300 hover:to-emerald-400 shadow-[0_0_24px_rgba(16,185,129,0.3)] hover:scale-[1.01] active:scale-[0.99] transition-all text-sm flex items-center gap-2"
                        >
                          <Sparkles className="w-4 h-4 text-black" />
                          <span>Begin Multimodal Analysis</span>
                        </button>
                      )}
                    </motion.div>
                  )}

                  {isUploading && !analysisComplete && (
                    <motion.div 
                      key="loading-zone"
                      initial={{ opacity: 0, scale: 0.98 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 1.02 }}
                      className="tl-card p-12 flex flex-col items-center text-center space-y-6"
                    >
                      <div className="relative w-28 h-28">
                        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                          <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="5" />
                          <circle 
                            cx="50" cy="50" r="42" 
                            fill="none" 
                            stroke="#10b981" 
                            strokeWidth="5" 
                            strokeDasharray={`${2 * Math.PI * 42}`}
                            strokeDashoffset={`${2 * Math.PI * 42 * (1 - progress / 100)}`}
                            strokeLinecap="round"
                            className="transition-all duration-300 ease-out drop-shadow-[0_0_10px_rgba(16,185,129,0.5)]"
                          />
                        </svg>
                        <div className="absolute inset-0 flex items-center justify-center">
                          <span className="text-2xl font-mono font-bold text-white">{progress}%</span>
                        </div>
                      </div>
                      
                      <div className="space-y-1.5">
                        <h2 className="text-xl font-bold tracking-tight text-white">
                          {statusText || "Processing signals..."}
                        </h2>
                        <p className="text-xs text-zinc-400 max-w-sm mx-auto">
                          Analyzing facial micro-expressions, speech pacing, acoustic pitch variance, and narrative structure.
                        </p>
                      </div>
                    </motion.div>
                  )}

                  {analysisComplete && analysisData && (
                    <motion.div 
                      key="results-zone"
                      initial={{ opacity: 0, y: 16 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="w-full flex flex-col gap-6"
                    >
                      {/* HERO SCORE */}
                      <div className="tl-card p-8 md:p-10 flex flex-col items-center justify-center text-center relative overflow-hidden">
                        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[240px] h-[240px] bg-emerald-500/10 blur-[80px] rounded-full pointer-events-none" />
                        <span className="text-zinc-400 font-semibold tracking-wider text-xs uppercase mb-4">
                          Overall Performance Score
                        </span>
                        <div className="relative w-40 h-40 flex items-center justify-center mb-3">
                          <svg className="absolute inset-0 w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                            <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="5" />
                            <circle 
                              cx="50" cy="50" r="42" 
                              fill="none" 
                              stroke="#10b981" 
                              strokeWidth="5" 
                              strokeDasharray={`${2 * Math.PI * 42}`}
                              strokeDashoffset={`${2 * Math.PI * 42 * (1 - (typeof analysisData.overall_score === "number" ? analysisData.overall_score : 0) / 100)}`}
                              strokeLinecap="round"
                              className="transition-all duration-1000 ease-out drop-shadow-[0_0_12px_rgba(16,185,129,0.5)]"
                            />
                          </svg>
                          <div className="flex flex-col items-center">
                            <span className="text-5xl font-mono font-extrabold text-white tracking-tight">
                              {typeof analysisData.overall_score === "number" ? analysisData.overall_score : "N/A"}
                            </span>
                            <span className="text-xs font-semibold text-emerald-400 mt-1 uppercase tracking-wider">
                              {typeof analysisData.overall_score === "number"
                                ? (analysisData.overall_score >= 85
                                    ? "Outstanding Delivery"
                                    : analysisData.overall_score >= 75
                                    ? "Strong Delivery"
                                    : analysisData.overall_score >= 60
                                    ? "Competent Delivery"
                                    : "Developing Delivery")
                                : "Insufficient Evidence"}
                            </span>
                          </div>
                        </div>
                        <p className="text-xs text-zinc-400 max-w-md mx-auto">
                          {analysisData.assessment_text || "Evidence-backed multimodal performance audit completed."}
                        </p>
                      </div>

                      {/* STRENGTHS & GROWTH TARGETS */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Strengths */}
                        <div className="tl-card p-6 border-emerald-500/20 bg-emerald-500/[0.02]">
                          <h3 className="text-emerald-400 font-semibold text-sm mb-3 flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                            <span>Verified Strengths</span>
                          </h3>
                          <ul className="space-y-2 text-xs text-zinc-300">
                            {analysisData.strengths && analysisData.strengths.length > 0 ? (
                              analysisData.strengths.map((str: string, idx: number) => (
                                <li key={idx} className="flex items-start gap-2">
                                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5 shrink-0" />
                                  <span>{str}</span>
                                </li>
                              ))
                            ) : (
                              <li className="text-zinc-500 italic">No specific strengths measured.</li>
                            )}
                          </ul>
                        </div>

                        {/* Areas for Growth */}
                        <div className="tl-card p-6 border-amber-500/20 bg-amber-500/[0.02]">
                          <h3 className="text-amber-400 font-semibold text-sm mb-3 flex items-center gap-2">
                            <AlertCircle className="w-4 h-4 text-amber-400" />
                            <span>Priority Growth Targets</span>
                          </h3>
                          <ul className="space-y-2 text-xs text-zinc-300">
                            {analysisData.growth_targets && analysisData.growth_targets.length > 0 ? (
                              analysisData.growth_targets.map((tgt: string, idx: number) => (
                                <li key={idx} className="flex items-start gap-2">
                                  <div className="w-1.5 h-1.5 rounded-full bg-amber-400 mt-1.5 shrink-0" />
                                  <span>{tgt}</span>
                                </li>
                              ))
                            ) : (
                              <li className="text-zinc-500 italic">No specific growth targets measured.</li>
                            )}
                          </ul>
                        </div>
                      </div>

                      {/* CATEGORY BREAKDOWN CARDS */}
                      <div>
                        <CategoryCards categories={analysisData.categories} />
                      </div>

                      {/* TELEMETRY & OBSERVABLES */}
                      <div>
                        <TelemetrySection 
                          telemetry={analysisData.telemetry} 
                          transcript={analysisData.transcript} 
                          modalityStatus={analysisData.modality_status} 
                        />
                      </div>

                      <div className="flex justify-center pt-2 pb-6">
                        <button 
                          onClick={() => {
                            setIsUploading(false);
                            setAnalysisComplete(false);
                            setAnalysisData(null);
                            setFile(null);
                          }}
                          className="px-6 py-2.5 rounded-xl font-medium text-xs text-zinc-300 border border-white/[0.1] hover:bg-white/[0.04] transition-all"
                        >
                          Analyze Another Video
                        </button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </>
            )}

            {activeTab === "live" && (
              <>
                {!isUploading && !analysisComplete ? (
                  <LiveCamera 
                    onAnalysisStart={(sid) => {
                      setActiveTab("upload");
                      listenToSession(sid);
                    }} 
                  />
                ) : null}
              </>
            )}

            {activeTab === "compare" && <CompareDashboard />}
          </div>
        </main>
      )}
    </div>
  );
}
