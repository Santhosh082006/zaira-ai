"use client";

import { useState, useRef } from "react";
import {
  Briefcase,
  Users,
  Code,
  Languages,
  Sparkles,
  ArrowRight,
  CheckCircle,
  Volume2,
  CheckCircle2,
  AlertCircle,
  FileText,
  Building2,
  UploadCloud,
  FileCheck,
  Eye,
  EyeOff,
  Trash2,
  Loader2,
} from "lucide-react";
import { parseResumeFile } from "@/lib/interviewApi";

export type InterviewTypeOption = "job" | "hr" | "technical" | "english" | "custom";
export type InterviewLevelOption = "beginner" | "intermediate" | "advanced";

export const TECHNICAL_DOMAINS = [
  "Java",
  "Python",
  "DSA",
  "DBMS",
  "Web Development",
  "AI/ML",
  "Other",
];

export const ASSESSMENT_GOAL_OPTIONS = [
  { id: "COMMUNICATION", label: "Communication", desc: "Clarity, concise explanations, logical structure" },
  { id: "ENGLISH", label: "English", desc: "Spoken fluency, vocabulary breadth, grammatical precision" },
  { id: "PERFORMANCE", label: "Performance", desc: "Eye contact, confidence, controlled pacing" },
  { id: "THINKING", label: "Thinking", desc: "Problem solving, reasoning, critical depth" },
  { id: "TECHNICAL", label: "Technical", desc: "Technical accuracy, depth, architectural understanding" },
];

export interface InterviewConfigProps {
  interviewType: InterviewTypeOption;
  setInterviewType: (type: InterviewTypeOption) => void;
  technicalDomain: string;
  setTechnicalDomain: (domain: string) => void;
  customGoal: string;
  setCustomGoal: (goal: string) => void;
  resumeText: string;
  setResumeText: (text: string) => void;
  jobDescription: string;
  setJobDescription: (text: string) => void;
  interviewLevel: InterviewLevelOption;
  setInterviewLevel: (level: InterviewLevelOption) => void;
  assessmentGoals: string[];
  toggleGoal: (goalId: string) => void;
  onStart: () => void;
  isLiveAvatarConfigured?: boolean;
}

export function InterviewConfig({
  interviewType,
  setInterviewType,
  technicalDomain,
  setTechnicalDomain,
  customGoal,
  setCustomGoal,
  resumeText,
  setResumeText,
  jobDescription,
  setJobDescription,
  interviewLevel,
  setInterviewLevel,
  assessmentGoals,
  toggleGoal,
  onStart,
  isLiveAvatarConfigured = false,
}: InterviewConfigProps) {
  // Resume / JD Tab state
  const [activeDocTab, setActiveDocTab] = useState<"resume" | "job">("resume");
  const [showDocGrounding, setShowDocGrounding] = useState<boolean>(false);

  // Resume file upload state
  const [resumeFileName, setResumeFileName] = useState<string | null>(null);
  const [resumeMeta, setResumeMeta] = useState<{ pages: number; words: number; chars: number } | null>(null);
  const [isParsingResume, setIsParsingResume] = useState<boolean>(false);
  const [resumeUploadError, setResumeUploadError] = useState<string | null>(null);
  const [showExtractedResumeText, setShowExtractedResumeText] = useState<boolean>(false);
  const [resumeMode, setResumeMode] = useState<"upload" | "paste">("upload");
  const [isResumeDragging, setIsResumeDragging] = useState<boolean>(false);

  // Job description file upload state
  const [jdFileName, setJdFileName] = useState<string | null>(null);
  const [jdMeta, setJdMeta] = useState<{ pages: number; words: number; chars: number } | null>(null);
  const [isParsingJd, setIsParsingJd] = useState<boolean>(false);
  const [jdUploadError, setJdUploadError] = useState<string | null>(null);
  const [showExtractedJdText, setShowExtractedJdText] = useState<boolean>(false);
  const [jdMode, setJdMode] = useState<"upload" | "paste">("upload");
  const [isJdDragging, setIsJdDragging] = useState<boolean>(false);

  const resumeFileInputRef = useRef<HTMLInputElement | null>(null);
  const jdFileInputRef = useRef<HTMLInputElement | null>(null);

  const processResumeFile = async (file: File) => {
    setIsParsingResume(true);
    setResumeUploadError(null);
    try {
      const res = await parseResumeFile(file);
      if (res.success && res.text) {
        setResumeText(res.text);
        setResumeFileName(res.filename);
        setResumeMeta({ pages: res.page_count, words: res.word_count, chars: res.char_count });
      } else {
        setResumeUploadError(res.error || "Failed to extract text from document.");
      }
    } catch (err: unknown) {
      setResumeUploadError(err instanceof Error ? err.message : "Error uploading and parsing resume.");
    } finally {
      setIsParsingResume(false);
    }
  };

  const processJdFile = async (file: File) => {
    setIsParsingJd(true);
    setJdUploadError(null);
    try {
      const res = await parseResumeFile(file);
      if (res.success && res.text) {
        setJobDescription(res.text);
        setJdFileName(res.filename);
        setJdMeta({ pages: res.page_count, words: res.word_count, chars: res.char_count });
      } else {
        setJdUploadError(res.error || "Failed to extract text from document.");
      }
    } catch (err: unknown) {
      setJdUploadError(err instanceof Error ? err.message : "Error uploading and parsing job description.");
    } finally {
      setIsParsingJd(false);
    }
  };

  return (
    <div className="p-6 md:p-8 border border-white/[0.07] rounded-3xl space-y-8 bg-zinc-950/80 backdrop-blur-2xl shadow-2xl relative overflow-hidden">
      {/* Step A: Interview Category */}
      <div className="space-y-4">
        <div className="flex items-center gap-2.5">
          <span className="w-6 h-6 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono font-bold flex items-center justify-center">
            A
          </span>
          <h2 className="text-base font-semibold tracking-tight text-white">Select Interview Category</h2>
          <span className="text-xs text-white/40">• Adaptive prompt configuration</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {/* 1. Job / Placement */}
          <button
            type="button"
            onClick={() => setInterviewType("job")}
            className={`text-left p-4 rounded-2xl border transition-all flex flex-col justify-between ${
              interviewType === "job"
                ? "border-emerald-500/70 bg-emerald-500/[0.08] shadow-[0_0_20px_rgba(16,185,129,0.12)]"
                : "border-white/[0.07] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.05]"
            }`}
          >
            <div className="flex items-center gap-2.5 mb-2">
              <div className={`p-2 rounded-xl ${interviewType === "job" ? "bg-emerald-500/20 text-emerald-400" : "bg-white/5 text-white/50"}`}>
                <Briefcase className="w-4 h-4" />
              </div>
              <span className="font-semibold text-sm text-white">Job / Career</span>
            </div>
            <p className="text-xs text-white/50 leading-relaxed">
              Comprehensive career interview covering background, experience, and structured problem solving.
            </p>
          </button>

          {/* 2. HR Interview */}
          <button
            type="button"
            onClick={() => setInterviewType("hr")}
            className={`text-left p-4 rounded-2xl border transition-all flex flex-col justify-between ${
              interviewType === "hr"
                ? "border-emerald-500/70 bg-emerald-500/[0.08] shadow-[0_0_20px_rgba(16,185,129,0.12)]"
                : "border-white/[0.07] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.05]"
            }`}
          >
            <div className="flex items-center gap-2.5 mb-2">
              <div className={`p-2 rounded-xl ${interviewType === "hr" ? "bg-emerald-500/20 text-emerald-400" : "bg-white/5 text-white/50"}`}>
                <Users className="w-4 h-4" />
              </div>
              <span className="font-semibold text-sm text-white">HR & Behavioral</span>
            </div>
            <p className="text-xs text-white/50 leading-relaxed">
              Focuses on teamwork, leadership, situational conflict resolution, and behavioral culture fit.
            </p>
          </button>

          {/* 3. Technical Interview */}
          <button
            type="button"
            onClick={() => setInterviewType("technical")}
            className={`text-left p-4 rounded-2xl border transition-all flex flex-col justify-between ${
              interviewType === "technical"
                ? "border-emerald-500/70 bg-emerald-500/[0.08] shadow-[0_0_20px_rgba(16,185,129,0.12)]"
                : "border-white/[0.07] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.05]"
            }`}
          >
            <div className="flex items-center gap-2.5 mb-2">
              <div className={`p-2 rounded-xl ${interviewType === "technical" ? "bg-emerald-500/20 text-emerald-400" : "bg-white/5 text-white/50"}`}>
                <Code className="w-4 h-4" />
              </div>
              <span className="font-semibold text-sm text-white">Technical Domain</span>
            </div>
            <p className="text-xs text-white/50 leading-relaxed">
              In-depth domain examination testing architectural patterns, data structures, and implementation.
            </p>
          </button>

          {/* 4. English Communication */}
          <button
            type="button"
            onClick={() => setInterviewType("english")}
            className={`text-left p-4 rounded-2xl border transition-all flex flex-col justify-between ${
              interviewType === "english"
                ? "border-emerald-500/70 bg-emerald-500/[0.08] shadow-[0_0_20px_rgba(16,185,129,0.12)]"
                : "border-white/[0.07] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.05]"
            }`}
          >
            <div className="flex items-center gap-2.5 mb-2">
              <div className={`p-2 rounded-xl ${interviewType === "english" ? "bg-emerald-500/20 text-emerald-400" : "bg-white/5 text-white/50"}`}>
                <Languages className="w-4 h-4" />
              </div>
              <span className="font-semibold text-sm text-white">English Fluency</span>
            </div>
            <p className="text-xs text-white/50 leading-relaxed">
              Assesses conversational articulation, vocabulary breadth, pronunciation, and spoken pace.
            </p>
          </button>

          {/* 5. Custom Persona / Scenario */}
          <button
            type="button"
            onClick={() => setInterviewType("custom")}
            className={`text-left p-4 rounded-2xl border transition-all flex flex-col justify-between ${
              interviewType === "custom"
                ? "border-emerald-500/70 bg-emerald-500/[0.08] shadow-[0_0_20px_rgba(16,185,129,0.12)]"
                : "border-white/[0.07] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.05]"
            }`}
          >
            <div className="flex items-center gap-2.5 mb-2">
              <div className={`p-2 rounded-xl ${interviewType === "custom" ? "bg-emerald-500/20 text-emerald-400" : "bg-white/5 text-white/50"}`}>
                <Sparkles className="w-4 h-4" />
              </div>
              <span className="font-semibold text-sm text-white">Custom Goal</span>
            </div>
            <p className="text-xs text-white/50 leading-relaxed">
              Tailor prompts directly to a unique target role, industry context, or custom preparation goal.
            </p>
          </button>
        </div>

        {/* Technical Domain Selector */}
        {interviewType === "technical" && (
          <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.08] space-y-2.5 animate-fadeIn">
            <label className="block text-xs font-medium text-white/70">
              Select Primary Technical Domain
            </label>
            <div className="flex flex-wrap gap-2">
              {TECHNICAL_DOMAINS.map((domain) => (
                <button
                  key={domain}
                  type="button"
                  onClick={() => setTechnicalDomain(domain)}
                  className={`px-3.5 py-1.5 rounded-xl text-xs font-medium transition-all ${
                    technicalDomain === domain
                      ? "bg-emerald-500 text-black font-semibold shadow-md"
                      : "bg-white/5 text-white/70 hover:bg-white/10 hover:text-white border border-white/5"
                  }`}
                >
                  {domain}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Custom Goal Input */}
        {interviewType === "custom" && (
          <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.08] space-y-2 animate-fadeIn">
            <label className="block text-xs font-medium text-white/70">
              Describe Target Goal or Specific Role Scenario
            </label>
            <input
              type="text"
              value={customGoal}
              onChange={(e) => setCustomGoal(e.target.value)}
              placeholder="e.g. Senior Backend Engineer at FinTech startup; System design & Kafka pipelines"
              className="w-full px-4 py-2.5 rounded-xl bg-black/40 border border-white/10 text-white placeholder-white/30 text-xs focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>
        )}
      </div>

      {/* Step B: Experience Level */}
      <div className="space-y-4">
        <div className="flex items-center gap-2.5">
          <span className="w-6 h-6 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono font-bold flex items-center justify-center">
            B
          </span>
          <h2 className="text-base font-semibold tracking-tight text-white">Experience Level Calibration</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { id: "beginner", title: "Beginner", desc: "Foundational questions & gentle pacing" },
            { id: "intermediate", title: "Intermediate", desc: "Standard professional depth (Default)" },
            { id: "advanced", title: "Advanced", desc: "Complex trade-offs & senior evaluations" },
          ].map((lvl) => (
            <button
              key={lvl.id}
              type="button"
              onClick={() => setInterviewLevel(lvl.id as InterviewLevelOption)}
              className={`text-left p-4 rounded-2xl border transition-all ${
                interviewLevel === lvl.id
                  ? "border-emerald-500/70 bg-emerald-500/[0.08] shadow-[0_0_20px_rgba(16,185,129,0.12)]"
                  : "border-white/[0.07] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.05]"
              }`}
            >
              <div className="font-semibold text-sm text-white mb-1">{lvl.title}</div>
              <p className="text-xs text-white/50 leading-relaxed">{lvl.desc}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Step C: Assessment Goals */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="w-6 h-6 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono font-bold flex items-center justify-center">
              C
            </span>
            <h2 className="text-base font-semibold tracking-tight text-white">Select Competency Objectives</h2>
          </div>
          <span className="text-[11px] font-mono text-white/40 uppercase">Multi-select enabled</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {ASSESSMENT_GOAL_OPTIONS.map((goal) => {
            const isChecked = assessmentGoals.includes(goal.id);
            return (
              <button
                key={goal.id}
                type="button"
                onClick={() => toggleGoal(goal.id)}
                className={`text-left p-4 rounded-2xl border transition-all flex items-start justify-between gap-2 ${
                  isChecked
                    ? "border-emerald-500/60 bg-emerald-500/[0.06] text-white"
                    : "border-white/[0.07] bg-white/[0.02] text-white/70 hover:border-white/20 hover:bg-white/[0.05]"
                }`}
              >
                <div>
                  <div className="font-semibold text-sm mb-1 text-white">{goal.label}</div>
                  <p className="text-xs text-white/50 leading-relaxed">{goal.desc}</p>
                </div>
                <div
                  className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 mt-0.5 transition-colors ${
                    isChecked ? "bg-emerald-500 border-emerald-400" : "border-white/20 bg-black/40"
                  }`}
                >
                  {isChecked && <CheckCircle className="w-3.5 h-3.5 text-black stroke-[3]" />}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Optional: Resume & Job Description Grounding */}
      <div className="p-5 md:p-6 rounded-2xl border border-white/[0.08] bg-white/[0.02] space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="w-6 h-6 rounded-md bg-teal-500/10 border border-teal-500/30 text-teal-300 text-xs font-mono font-bold flex items-center justify-center">
              +
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-white">Resume & Job Description Grounding (Optional)</h3>
                {(resumeText || jobDescription) && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 flex items-center gap-1">
                    <Sparkles className="w-2.5 h-2.5" />
                    <span>Personalized Grounding Active</span>
                  </span>
                )}
              </div>
              <p className="text-xs text-zinc-400">Paste your resume and target role requirements to generate hyper-personalized questions.</p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setShowDocGrounding(!showDocGrounding)}
            className="px-4 py-2 rounded-xl text-xs font-medium border border-white/10 bg-white/[0.04] hover:bg-white/[0.08] text-zinc-200 hover:text-white transition-all inline-flex items-center gap-2"
          >
            <FileText className="w-3.5 h-3.5 text-teal-400" />
            <span>{showDocGrounding ? "Hide Inputs" : (resumeText || jobDescription) ? "Edit Profile Context" : "Add Resume / Job Description"}</span>
          </button>
        </div>

        {showDocGrounding && (
          <div className="pt-3 border-t border-white/[0.06] space-y-3 animate-fadeIn">
            <div className="flex items-center gap-2 border-b border-white/[0.06] pb-2">
              <button
                type="button"
                onClick={() => setActiveDocTab("resume")}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
                  activeDocTab === "resume"
                    ? "bg-teal-500/20 border border-teal-500/40 text-teal-200"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Candidate Resume / Profile</span>
                {resumeText && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 ml-1" />}
              </button>

              <button
                type="button"
                onClick={() => setActiveDocTab("job")}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
                  activeDocTab === "job"
                    ? "bg-teal-500/20 border border-teal-500/40 text-teal-200"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                <Building2 className="w-3.5 h-3.5" />
                <span>Target Job Description</span>
                {jobDescription && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 ml-1" />}
              </button>
            </div>

            {activeDocTab === "resume" ? (
              <div className="space-y-3">
                {/* Hidden file input */}
                <input
                  ref={resumeFileInputRef}
                  type="file"
                  accept=".pdf,.docx,.doc,.txt,.md"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) processResumeFile(f);
                    if (e.target) e.target.value = "";
                  }}
                  className="hidden"
                />

                {/* Sub-mode switch: Upload File vs Paste Text */}
                <div className="flex items-center justify-between">
                  <div className="inline-flex rounded-lg bg-black/40 p-1 border border-white/10 text-[11px]">
                    <button
                      type="button"
                      onClick={() => setResumeMode("upload")}
                      className={`px-3 py-1 rounded-md transition-all font-medium flex items-center gap-1.5 ${
                        resumeMode === "upload"
                          ? "bg-teal-500/20 text-teal-300 border border-teal-500/30"
                          : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      <UploadCloud className="w-3 h-3" />
                      <span>Upload Document (PDF / DOCX)</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setResumeMode("paste")}
                      className={`px-3 py-1 rounded-md transition-all font-medium flex items-center gap-1.5 ${
                        resumeMode === "paste"
                          ? "bg-teal-500/20 text-teal-300 border border-teal-500/30"
                          : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      <FileText className="w-3 h-3" />
                      <span>Paste Text Directly</span>
                    </button>
                  </div>

                  {resumeText && (
                    <span className="text-[11px] font-mono text-emerald-400/90 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>Profile Loaded ({resumeText.length} chars)</span>
                    </span>
                  )}
                </div>

                {resumeUploadError && (
                  <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-200 text-xs flex items-center justify-between gap-2 animate-fadeIn">
                    <div className="flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                      <span>{resumeUploadError}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setResumeMode("paste")}
                      className="underline text-[11px] text-red-300 hover:text-white shrink-0"
                    >
                      Switch to Paste
                    </button>
                  </div>
                )}

                {resumeMode === "upload" ? (
                  isParsingResume ? (
                    <div className="p-8 rounded-2xl border border-teal-500/30 bg-teal-500/[0.04] flex flex-col items-center justify-center text-center space-y-2.5 animate-pulse">
                      <Loader2 className="w-6 h-6 text-teal-400 animate-spin" />
                      <div className="text-sm font-medium text-white">Extracting Resume Content...</div>
                      <p className="text-xs text-zinc-400 max-w-sm">
                        Parsing PDF structure, experience history, and core skills to personalize your interview questions.
                      </p>
                    </div>
                  ) : resumeFileName && resumeText ? (
                    <div className="space-y-3">
                      <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/[0.05] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 flex items-center justify-center shrink-0">
                            <FileCheck className="w-5 h-5" />
                          </div>
                          <div>
                            <div className="text-sm font-semibold text-white flex items-center gap-2">
                              <span>{resumeFileName}</span>
                              <span className="px-2 py-0.5 rounded-full text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono">
                                Ready
                              </span>
                            </div>
                            <div className="flex flex-wrap items-center gap-2 text-[11px] text-zinc-400 font-mono mt-0.5">
                              {resumeMeta?.pages ? <span>{resumeMeta.pages} page{resumeMeta.pages > 1 ? "s" : ""}</span> : null}
                              {resumeMeta?.words ? <span>• {resumeMeta.words} words</span> : null}
                              <span>• {resumeText.length} characters extracted</span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            type="button"
                            onClick={() => setShowExtractedResumeText(!showExtractedResumeText)}
                            className="px-3 py-1.5 rounded-lg text-xs font-medium border border-white/10 bg-white/[0.04] hover:bg-white/[0.08] text-zinc-200 hover:text-white transition-all flex items-center gap-1.5"
                          >
                            {showExtractedResumeText ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                            <span>{showExtractedResumeText ? "Hide Text" : "View / Edit"}</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => resumeFileInputRef.current?.click()}
                            className="px-3 py-1.5 rounded-lg text-xs font-medium border border-teal-500/30 bg-teal-500/10 hover:bg-teal-500/20 text-teal-300 transition-all flex items-center gap-1.5"
                          >
                            <UploadCloud className="w-3.5 h-3.5" />
                            <span>Replace</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setResumeFileName(null);
                              setResumeText("");
                              setResumeMeta(null);
                            }}
                            className="p-1.5 rounded-lg text-zinc-400 hover:text-red-400 hover:bg-red-500/10 transition-all"
                            title="Remove resume"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      {showExtractedResumeText && (
                        <div className="space-y-1.5 animate-fadeIn">
                          <div className="flex items-center justify-between text-xs text-zinc-400">
                            <span>Extracted Resume Text (Editable)</span>
                            <span className="font-mono text-[10px]">{resumeText.length} characters</span>
                          </div>
                          <textarea
                            value={resumeText}
                            onChange={(e) => setResumeText(e.target.value)}
                            rows={5}
                            className="w-full p-3.5 rounded-xl bg-black/40 border border-white/10 text-white placeholder-white/30 text-xs focus:outline-none focus:border-teal-500/60 transition-colors leading-relaxed font-mono"
                          />
                        </div>
                      )}
                    </div>
                  ) : (
                    <div
                      onDragOver={(e) => {
                        e.preventDefault();
                        setIsResumeDragging(true);
                      }}
                      onDragLeave={() => setIsResumeDragging(false)}
                      onDrop={(e) => {
                        e.preventDefault();
                        setIsResumeDragging(false);
                        const file = e.dataTransfer.files?.[0];
                        if (file) processResumeFile(file);
                      }}
                      onClick={() => resumeFileInputRef.current?.click()}
                      className={`p-6 sm:p-8 rounded-2xl border-2 border-dashed transition-all cursor-pointer flex flex-col items-center justify-center text-center space-y-2.5 ${
                        isResumeDragging
                          ? "border-teal-400 bg-teal-500/10"
                          : "border-white/15 bg-black/30 hover:border-teal-500/50 hover:bg-white/[0.02]"
                      }`}
                    >
                      <div className="w-12 h-12 rounded-2xl bg-teal-500/10 border border-teal-500/30 text-teal-300 flex items-center justify-center">
                        <UploadCloud className="w-6 h-6" />
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-white">
                          Drop your resume file here, or <span className="text-teal-400 underline">browse files</span>
                        </div>
                        <p className="text-xs text-zinc-400 mt-1">
                          Supports Adobe PDF (.pdf), Microsoft Word (.docx), or plain text (.txt)
                        </p>
                      </div>
                      <div className="inline-flex items-center gap-2 text-[10px] font-mono text-zinc-500 bg-white/5 px-2.5 py-1 rounded-full">
                        <span>Zero configuration</span>
                        <span>•</span>
                        <span>Instant semantic extraction</span>
                      </div>
                    </div>
                  )
                ) : (
                  <div className="space-y-1.5 animate-fadeIn">
                    <div className="flex items-center justify-between text-xs text-zinc-400">
                      <span>Paste Resume, Skills, Key Projects, or LinkedIn Summary</span>
                      <span className="font-mono text-[10px]">{resumeText.length} characters</span>
                    </div>
                    <textarea
                      value={resumeText}
                      onChange={(e) => setResumeText(e.target.value)}
                      placeholder="e.g. 4+ years building distributed Python microservices with FastAPI, Redis, PostgreSQL, and Kafka. Led cloud migration to AWS EKS with Terraform. Built real-time analytics engine..."
                      rows={5}
                      className="w-full p-3.5 rounded-xl bg-black/40 border border-white/10 text-white placeholder-white/30 text-xs focus:outline-none focus:border-teal-500/60 transition-colors leading-relaxed"
                    />
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                {/* Hidden file input for JD */}
                <input
                  ref={jdFileInputRef}
                  type="file"
                  accept=".pdf,.docx,.doc,.txt,.md"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) processJdFile(f);
                    if (e.target) e.target.value = "";
                  }}
                  className="hidden"
                />

                {/* Sub-mode switch for Job Description */}
                <div className="flex items-center justify-between">
                  <div className="inline-flex rounded-lg bg-black/40 p-1 border border-white/10 text-[11px]">
                    <button
                      type="button"
                      onClick={() => setJdMode("upload")}
                      className={`px-3 py-1 rounded-md transition-all font-medium flex items-center gap-1.5 ${
                        jdMode === "upload"
                          ? "bg-teal-500/20 text-teal-300 border border-teal-500/30"
                          : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      <UploadCloud className="w-3 h-3" />
                      <span>Upload JD (PDF / DOCX)</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setJdMode("paste")}
                      className={`px-3 py-1 rounded-md transition-all font-medium flex items-center gap-1.5 ${
                        jdMode === "paste"
                          ? "bg-teal-500/20 text-teal-300 border border-teal-500/30"
                          : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      <Building2 className="w-3 h-3" />
                      <span>Paste JD Directly</span>
                    </button>
                  </div>

                  {jobDescription && (
                    <span className="text-[11px] font-mono text-emerald-400/90 flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>JD Loaded ({jobDescription.length} chars)</span>
                    </span>
                  )}
                </div>

                {jdUploadError && (
                  <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-200 text-xs flex items-center justify-between gap-2 animate-fadeIn">
                    <div className="flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                      <span>{jdUploadError}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setJdMode("paste")}
                      className="underline text-[11px] text-red-300 hover:text-white shrink-0"
                    >
                      Switch to Paste
                    </button>
                  </div>
                )}

                {jdMode === "upload" ? (
                  isParsingJd ? (
                    <div className="p-8 rounded-2xl border border-teal-500/30 bg-teal-500/[0.04] flex flex-col items-center justify-center text-center space-y-2.5 animate-pulse">
                      <Loader2 className="w-6 h-6 text-teal-400 animate-spin" />
                      <div className="text-sm font-medium text-white">Extracting Job Description...</div>
                      <p className="text-xs text-zinc-400 max-w-sm">
                        Extracting required qualifications, technical stacks, and behavioral expectations.
                      </p>
                    </div>
                  ) : jdFileName && jobDescription ? (
                    <div className="space-y-3">
                      <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/[0.05] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 flex items-center justify-center shrink-0">
                            <FileCheck className="w-5 h-5" />
                          </div>
                          <div>
                            <div className="text-sm font-semibold text-white flex items-center gap-2">
                              <span>{jdFileName}</span>
                              <span className="px-2 py-0.5 rounded-full text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono">
                                Ready
                              </span>
                            </div>
                            <div className="flex flex-wrap items-center gap-2 text-[11px] text-zinc-400 font-mono mt-0.5">
                              {jdMeta?.pages ? <span>{jdMeta.pages} page{jdMeta.pages > 1 ? "s" : ""}</span> : null}
                              {jdMeta?.words ? <span>• {jdMeta.words} words</span> : null}
                              <span>• {jobDescription.length} characters extracted</span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <button
                            type="button"
                            onClick={() => setShowExtractedJdText(!showExtractedJdText)}
                            className="px-3 py-1.5 rounded-lg text-xs font-medium border border-white/10 bg-white/[0.04] hover:bg-white/[0.08] text-zinc-200 hover:text-white transition-all flex items-center gap-1.5"
                          >
                            {showExtractedJdText ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                            <span>{showExtractedJdText ? "Hide Text" : "View / Edit"}</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => jdFileInputRef.current?.click()}
                            className="px-3 py-1.5 rounded-lg text-xs font-medium border border-teal-500/30 bg-teal-500/10 hover:bg-teal-500/20 text-teal-300 transition-all flex items-center gap-1.5"
                          >
                            <UploadCloud className="w-3.5 h-3.5" />
                            <span>Replace</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setJdFileName(null);
                              setJobDescription("");
                              setJdMeta(null);
                            }}
                            className="p-1.5 rounded-lg text-zinc-400 hover:text-red-400 hover:bg-red-500/10 transition-all"
                            title="Remove JD"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      {showExtractedJdText && (
                        <div className="space-y-1.5 animate-fadeIn">
                          <div className="flex items-center justify-between text-xs text-zinc-400">
                            <span>Extracted Job Description Text (Editable)</span>
                            <span className="font-mono text-[10px]">{jobDescription.length} characters</span>
                          </div>
                          <textarea
                            value={jobDescription}
                            onChange={(e) => setJobDescription(e.target.value)}
                            rows={5}
                            className="w-full p-3.5 rounded-xl bg-black/40 border border-white/10 text-white placeholder-white/30 text-xs focus:outline-none focus:border-teal-500/60 transition-colors leading-relaxed font-mono"
                          />
                        </div>
                      )}
                    </div>
                  ) : (
                    <div
                      onDragOver={(e) => {
                        e.preventDefault();
                        setIsJdDragging(true);
                      }}
                      onDragLeave={() => setIsJdDragging(false)}
                      onDrop={(e) => {
                        e.preventDefault();
                        setIsJdDragging(false);
                        const file = e.dataTransfer.files?.[0];
                        if (file) processJdFile(file);
                      }}
                      onClick={() => jdFileInputRef.current?.click()}
                      className={`p-6 sm:p-8 rounded-2xl border-2 border-dashed transition-all cursor-pointer flex flex-col items-center justify-center text-center space-y-2.5 ${
                        isJdDragging
                          ? "border-teal-400 bg-teal-500/10"
                          : "border-white/15 bg-black/30 hover:border-teal-500/50 hover:bg-white/[0.02]"
                      }`}
                    >
                      <div className="w-12 h-12 rounded-2xl bg-teal-500/10 border border-teal-500/30 text-teal-300 flex items-center justify-center">
                        <UploadCloud className="w-6 h-6" />
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-white">
                          Drop target Job Description here, or <span className="text-teal-400 underline">browse files</span>
                        </div>
                        <p className="text-xs text-zinc-400 mt-1">
                          Supports Adobe PDF (.pdf), Microsoft Word (.docx), or plain text (.txt)
                        </p>
                      </div>
                    </div>
                  )
                ) : (
                  <div className="space-y-1.5 animate-fadeIn">
                    <div className="flex items-center justify-between text-xs text-zinc-400">
                      <span>Paste Target Job Description, Qualifications & Responsibilities</span>
                      <span className="font-mono text-[10px]">{jobDescription.length} characters</span>
                    </div>
                    <textarea
                      value={jobDescription}
                      onChange={(e) => setJobDescription(e.target.value)}
                      placeholder="e.g. We are seeking a Senior Backend Engineer to design high-throughput transaction processing systems. Requirements: Python or Go, concurrency, distributed databases, Kubernetes, CI/CD..."
                      rows={5}
                      className="w-full p-3.5 rounded-xl bg-black/40 border border-white/10 text-white placeholder-white/30 text-xs focus:outline-none focus:border-teal-500/60 transition-colors leading-relaxed"
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Initialize first; the device check follows in its own step. */}
      <div className="pt-6 border-t border-white/[0.07] flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="text-xs text-white/50 leading-relaxed flex flex-wrap items-center gap-2">
          {isLiveAvatarConfigured ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 font-mono text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              LiveAvatar Lite WebRTC Active (Real-Time Lip-Sync)
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/[0.04] border border-white/10 text-zinc-300 font-mono text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-teal-400" />
              Zaira Neural Speech (Add HEYGEN_API_KEY in .env for LiveAvatar Lite WebRTC)
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={onStart}
          className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-3.5 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-black font-semibold rounded-2xl shadow-[0_0_25px_rgba(16,185,129,0.25)] transition-all transform hover:-translate-y-0.5 active:translate-y-0"
        >
          <span>Initialize Session</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
