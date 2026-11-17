"use client";

import React, { useState, useEffect } from "react";
import {
  CheckCircle2,
  AlertCircle,
  Printer,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Award,
  Clock,
  Mic,
  Eye,
  BarChart3,
  Lightbulb,
  Check,
  FileText,
  Loader2,
} from "lucide-react";
import { fetchInterviewReport, InterviewReport } from "../../lib/interviewApi";

export interface InterviewCompletedProps {
  sessionId?: string | null;
  onReset: () => void;
}

export function InterviewCompleted({ sessionId, onReset }: InterviewCompletedProps) {
  const [report, setReport] = useState<InterviewReport | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedQuestion, setExpandedQuestion] = useState<number | null>(0);

  useEffect(() => {
    let isMounted = true;
    async function loadReport() {
      if (!sessionId) {
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        setError(null);
        const data = await fetchInterviewReport(sessionId);
        if (isMounted) {
          setReport(data);
        }
      } catch (err: unknown) {
        console.warn("Could not load cumulative report from server:", err);
        if (isMounted) {
          setError("Failed to load detailed report. Displaying summary session data.");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }
    loadReport();
    return () => {
      isMounted = false;
    };
  }, [sessionId]);

  const handlePrint = () => {
    if (typeof window !== "undefined") {
      window.print();
    }
  };

  const formatSeconds = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.round(sec % 60);
    return `${m}m ${s}s`;
  };

  const getScoreColor = (score: number) => {
    if (score >= 85) return "text-emerald-400 border-emerald-500/30 bg-emerald-500/10";
    if (score >= 70) return "text-teal-300 border-teal-500/30 bg-teal-500/10";
    if (score >= 55) return "text-amber-300 border-amber-500/30 bg-amber-500/10";
    return "text-rose-400 border-rose-500/30 bg-rose-500/10";
  };

  const getProgressBarColor = (score: number) => {
    if (score >= 85) return "bg-gradient-to-r from-emerald-500 to-teal-400";
    if (score >= 70) return "bg-gradient-to-r from-teal-500 to-cyan-400";
    if (score >= 55) return "bg-gradient-to-r from-amber-500 to-yellow-400";
    return "bg-gradient-to-r from-rose-500 to-amber-500";
  };

  if (loading) {
    return (
      <div className="p-16 border border-white/[0.08] rounded-3xl bg-zinc-950/80 backdrop-blur-2xl text-center space-y-5 flex flex-col items-center justify-center">
        <div className="w-16 h-16 rounded-full border-2 border-emerald-500/20 border-t-emerald-400 animate-spin flex items-center justify-center">
          <Sparkles className="w-6 h-6 text-emerald-400" />
        </div>
        <div className="space-y-1">
          <h2 className="text-xl font-semibold text-white">Synthesizing Final Performance Report</h2>
          <p className="text-xs text-zinc-400 max-w-sm">
            Aggregating multimodal telemetry, rubric criteria, and competency benchmarks across all interview answers...
          </p>
        </div>
      </div>
    );
  }

  // Fallback if no report could be loaded
  if (!report) {
    return (
      <div className="p-8 md:p-12 border border-white/[0.08] rounded-3xl text-center space-y-6 bg-zinc-950/80 backdrop-blur-2xl shadow-2xl">
        <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400 shadow-[0_0_30px_rgba(16,185,129,0.2)]">
          <CheckCircle2 className="w-8 h-8" />
        </div>
        <div className="space-y-2">
          <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-white">Interview Completed</h2>
          <p className="text-white/50 max-w-md mx-auto text-xs md:text-sm leading-relaxed">
            All responses, speech telemetry, and competency markers have been processed.
          </p>
          {error && <p className="text-xs text-amber-400/80">{error}</p>}
        </div>
        <button
          onClick={onReset}
          className="bg-white text-black hover:bg-white/90 px-8 py-3 rounded-xl font-semibold transition-all inline-flex items-center gap-2 text-sm shadow-lg hover:-translate-y-0.5 active:translate-y-0"
        >
          <RotateCcw className="w-4 h-4" />
          <span>Start New Interview</span>
        </button>
      </div>
    );
  }

  const {
    overall_score,
    performance_level,
    summary_assessment,
    aggregate_telemetry,
    competency_breakdown,
    strengths,
    growth_targets,
    questions_audit,
    interview_type,
    interview_level,
    technical_domain,
  } = report;

  return (
    <div className="space-y-8 animate-fadeIn text-white max-w-5xl mx-auto print:text-black print:max-w-none print:m-0">
      {/* ============================================================== */}
      {/* 1. EXECUTIVE HERO CARD                                          */}
      {/* ============================================================== */}
      <div className="p-6 md:p-8 rounded-3xl border border-white/[0.08] bg-zinc-950/90 backdrop-blur-2xl shadow-2xl space-y-6 relative overflow-hidden print:border print:border-gray-300 print:bg-white print:p-6">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 pb-6 border-b border-white/[0.08] print:border-gray-200">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] font-mono tracking-widest text-emerald-400 uppercase font-semibold print:text-emerald-700">
                Performance Evaluation Audit
              </span>
              <span className="text-white/20 print:text-gray-400">•</span>
              <span className="text-[10px] font-mono tracking-wider text-white/50 print:text-gray-600 uppercase">
                {interview_type} Interview
                {technical_domain && ` • ${technical_domain}`}
                {` • ${interview_level}`}
              </span>
            </div>
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-white print:text-black">
              Candidate Cumulative Scorecard
            </h1>
            <p className="text-xs md:text-sm text-zinc-400 print:text-gray-600 mt-1.5 max-w-xl leading-relaxed">
              {summary_assessment}
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-3 self-stretch sm:self-auto print:hidden">
            <button
              onClick={handlePrint}
              className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-white/10 bg-white/[0.04] hover:bg-white/[0.08] text-xs font-medium text-zinc-200 hover:text-white transition-all shadow-sm"
              title="Print or save as PDF report"
            >
              <Printer className="w-3.5 h-3.5 text-emerald-400" />
              <span>Export PDF</span>
            </button>
            <button
              onClick={onReset}
              className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-black text-xs font-semibold transition-all shadow-[0_0_20px_rgba(16,185,129,0.25)]"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>New Session</span>
            </button>
          </div>
        </div>

        {/* Big Overall Score Block */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
          <div className="md:col-span-5 flex items-center gap-5">
            <div className={`w-28 h-28 rounded-2xl border-2 flex flex-col items-center justify-center shrink-0 ${getScoreColor(overall_score)}`}>
              <span className="text-4xl font-mono font-bold tracking-tight">
                {Math.round(overall_score)}
              </span>
              <span className="text-[10px] font-mono uppercase tracking-widest opacity-70">
                Score / 100
              </span>
            </div>
            <div className="space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-400 print:text-gray-500">
                Performance Rating
              </span>
              <h3 className="text-xl font-bold text-white print:text-black">
                {performance_level}
              </h3>
              <p className="text-xs text-zinc-400 print:text-gray-600 leading-relaxed">
                Evaluated across {aggregate_telemetry.total_questions_answered} adaptive inquiry stages.
              </p>
            </div>
          </div>

          {/* Quick Metrics Strip */}
          <div className="md:col-span-7 grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3.5 rounded-2xl bg-white/[0.02] border border-white/[0.06] print:border-gray-200 print:bg-gray-50">
              <div className="flex items-center gap-1.5 text-zinc-400 print:text-gray-500 text-[11px] mb-1">
                <Mic className="w-3.5 h-3.5 text-emerald-400" />
                <span>Pacing</span>
              </div>
              <div className="text-lg font-mono font-bold text-white print:text-black">
                {aggregate_telemetry.avg_wpm ? `${Math.round(aggregate_telemetry.avg_wpm)}` : "—"}
              </div>
              <span className="text-[10px] text-zinc-500">Words / Min</span>
            </div>

            <div className="p-3.5 rounded-2xl bg-white/[0.02] border border-white/[0.06] print:border-gray-200 print:bg-gray-50">
              <div className="flex items-center gap-1.5 text-zinc-400 print:text-gray-500 text-[11px] mb-1">
                <Clock className="w-3.5 h-3.5 text-teal-400" />
                <span>Spoken Time</span>
              </div>
              <div className="text-lg font-mono font-bold text-white print:text-black">
                {formatSeconds(aggregate_telemetry.total_speaking_time_sec)}
              </div>
              <span className="text-[10px] text-zinc-500">Total Duration</span>
            </div>

            <div className="p-3.5 rounded-2xl bg-white/[0.02] border border-white/[0.06] print:border-gray-200 print:bg-gray-50">
              <div className="flex items-center gap-1.5 text-zinc-400 print:text-gray-500 text-[11px] mb-1">
                <Eye className="w-3.5 h-3.5 text-cyan-400" />
                <span>Camera Presence</span>
              </div>
              <div className="text-lg font-mono font-bold text-white print:text-black">
                {aggregate_telemetry.avg_face_presence_pct != null
                  ? `${Math.round(aggregate_telemetry.avg_face_presence_pct)}%`
                  : "Audio Only"}
              </div>
              <span className="text-[10px] text-zinc-500">In-Frame Tracking</span>
            </div>

            <div className="p-3.5 rounded-2xl bg-white/[0.02] border border-white/[0.06] print:border-gray-200 print:bg-gray-50">
              <div className="flex items-center gap-1.5 text-zinc-400 print:text-gray-500 text-[11px] mb-1">
                <BarChart3 className="w-3.5 h-3.5 text-indigo-400" />
                <span>Pause Control</span>
              </div>
              <div className="text-lg font-mono font-bold text-white print:text-black">
                {aggregate_telemetry.avg_pause_duration_sec != null
                  ? `${aggregate_telemetry.avg_pause_duration_sec.toFixed(1)}s`
                  : "Controlled"}
              </div>
              <span className="text-[10px] text-zinc-500">Average Pause</span>
            </div>
          </div>
        </div>
      </div>

      {/* ============================================================== */}
      {/* 2. COMPETENCY SCORECARD BREAKDOWN                              */}
      {/* ============================================================== */}
      {competency_breakdown.length > 0 && (
        <div className="p-6 md:p-8 rounded-3xl border border-white/[0.08] bg-zinc-950/80 backdrop-blur-2xl shadow-xl space-y-6 print:border print:border-gray-300 print:bg-white print:p-6">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-[10px] font-mono uppercase tracking-widest text-emerald-400 print:text-emerald-700 font-semibold">
                Competency Mastery Matrix
              </span>
              <h2 className="text-xl font-bold text-white print:text-black mt-0.5">
                Target Competency Breakdown
              </h2>
            </div>
            <span className="text-xs text-zinc-400 print:text-gray-600 font-mono">
              {competency_breakdown.filter((c) => c.status === "demonstrated").length} of {competency_breakdown.length} Demonstrated
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {competency_breakdown.map((c) => (
              <div
                key={c.id}
                className="p-4 rounded-2xl border border-white/[0.06] bg-white/[0.02] space-y-3 print:border-gray-200 print:bg-gray-50"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <span className="text-[9px] font-mono tracking-wider uppercase text-zinc-400 bg-white/5 px-2 py-0.5 rounded print:text-gray-600 print:bg-gray-200">
                      {c.category}
                    </span>
                    <h4 className="text-sm font-semibold text-white print:text-black mt-1">
                      {c.name}
                    </h4>
                  </div>
                  <div className="text-right">
                    <span className="text-lg font-mono font-bold text-white print:text-black">
                      {c.score}%
                    </span>
                    <span className={`block text-[10px] font-mono uppercase tracking-wider capitalize ${
                      c.status === "demonstrated" ? "text-emerald-400" : c.status === "partially_demonstrated" ? "text-amber-400" : "text-zinc-400"
                    }`}>
                      {c.status.replace("_", " ")}
                    </span>
                  </div>
                </div>

                {/* Animated Progress Bar */}
                <div className="w-full h-2 rounded-full bg-white/[0.06] overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${getProgressBarColor(c.score)}`}
                    style={{ width: `${Math.min(100, Math.max(8, c.score))}%` }}
                  />
                </div>

                {c.evidence_count > 0 && (
                  <p className="text-[11px] text-zinc-400 print:text-gray-600 flex items-center gap-1.5">
                    <Check className="w-3 h-3 text-emerald-400" />
                    <span>{c.evidence_count} behavioral evidence markers verified</span>
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* 3. EXECUTIVE STRENGTHS & GROWTH TARGETS                        */}
      {/* ============================================================== */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Strengths */}
        <div className="p-6 rounded-3xl border border-emerald-500/20 bg-emerald-950/10 backdrop-blur-xl shadow-xl space-y-4 print:border-gray-300 print:bg-white">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <Award className="w-4 h-4" />
            </div>
            <h3 className="text-base font-bold text-white print:text-black">
              Demonstrated Strengths
            </h3>
          </div>
          {strengths && strengths.length > 0 ? (
            <div className="space-y-2.5">
              {strengths.map((str, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-white/[0.02] border border-emerald-500/15 flex items-start gap-2.5 text-xs text-emerald-200/90 print:text-gray-800 leading-relaxed"
                >
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span>{str}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-zinc-400 italic">No specific strengths recorded.</p>
          )}
        </div>

        {/* Growth Targets */}
        <div className="p-6 rounded-3xl border border-amber-500/20 bg-amber-950/10 backdrop-blur-xl shadow-xl space-y-4 print:border-gray-300 print:bg-white">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <Lightbulb className="w-4 h-4" />
            </div>
            <h3 className="text-base font-bold text-white print:text-black">
              High-Impact Growth Targets
            </h3>
          </div>
          {growth_targets && growth_targets.length > 0 ? (
            <div className="space-y-2.5">
              {growth_targets.map((gw, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-xl bg-white/[0.02] border border-amber-500/15 flex items-start gap-2.5 text-xs text-amber-200/90 print:text-gray-800 leading-relaxed"
                >
                  <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <span>{gw}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-zinc-400 italic">No critical deficiencies noted.</p>
          )}
        </div>
      </div>

      {/* ============================================================== */}
      {/* 4. QUESTION-BY-QUESTION AUDIT ACCORDION                        */}
      {/* ============================================================== */}
      {questions_audit && questions_audit.length > 0 && (
        <div className="p-6 md:p-8 rounded-3xl border border-white/[0.08] bg-zinc-950/80 backdrop-blur-2xl shadow-xl space-y-6 print:border print:border-gray-300 print:bg-white print:p-6">
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-emerald-400 print:text-emerald-700 font-semibold">
              Chronological Audit Trail
            </span>
            <h2 className="text-xl font-bold text-white print:text-black mt-0.5">
              Question-by-Question Evaluation Details
            </h2>
          </div>

          <div className="space-y-4">
            {questions_audit.map((qa, index) => {
              const isExpanded = expandedQuestion === index;
              return (
                <div
                  key={qa.question_id || index}
                  className="rounded-2xl border border-white/[0.08] bg-white/[0.02] overflow-hidden transition-all print:border-gray-200"
                >
                  {/* Header Row */}
                  <button
                    onClick={() => setExpandedQuestion(isExpanded ? null : index)}
                    className="w-full p-4 md:p-5 flex items-center justify-between gap-4 text-left hover:bg-white/[0.03] transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="w-7 h-7 rounded-xl bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center justify-center text-xs font-mono font-bold shrink-0">
                        {qa.question_number}
                      </span>
                      <div>
                        <h4 className="text-sm font-medium text-white print:text-black line-clamp-1">
                          {qa.question_text}
                        </h4>
                        <span className="text-[10px] font-mono text-zinc-400 capitalize">
                          {qa.question_type} Prompt • {qa.duration_sec}s
                          {qa.wpm && ` • ${Math.round(qa.wpm)} WPM`}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <div className="text-right">
                        <span className="text-sm font-mono font-bold text-white print:text-black">
                          {qa.total_marks_awarded} / {qa.total_max_marks}
                        </span>
                        <span className="block text-[10px] font-mono text-zinc-400">
                          {qa.score}%
                        </span>
                      </div>
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4 text-zinc-400" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-zinc-400" />
                      )}
                    </div>
                  </button>

                  {/* Expanded Body */}
                  {isExpanded && (
                    <div className="p-4 md:p-6 border-t border-white/[0.06] space-y-5 bg-black/20 print:bg-white">
                      {/* Full Question Text */}
                      <div>
                        <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                          Prompt
                        </span>
                        <p className="text-sm text-zinc-200 print:text-black font-medium mt-0.5">
                          {qa.question_text}
                        </p>
                      </div>

                      {/* Candidate Transcript */}
                      <div className="p-4 rounded-xl bg-zinc-950/80 border border-white/[0.06] space-y-1.5 print:bg-gray-50 print:border-gray-200">
                        <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-emerald-400">
                          <FileText className="w-3.5 h-3.5" />
                          <span>Candidate Spoken Transcript</span>
                        </div>
                        <p className="text-xs md:text-sm text-zinc-300 print:text-gray-800 leading-relaxed italic">
                          &ldquo;{qa.transcript}&rdquo;
                        </p>
                      </div>

                      {/* Rubric Criteria Table */}
                      {qa.rubric_criteria && qa.rubric_criteria.length > 0 && (
                        <div className="space-y-2.5">
                          <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                            Rubric Criteria Breakdown
                          </span>
                          <div className="grid grid-cols-1 gap-2">
                            {qa.rubric_criteria.map((c, cIdx) => (
                              <div
                                key={cIdx}
                                className="p-3.5 rounded-xl border border-white/[0.06] bg-white/[0.02] flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
                              >
                                <div>
                                  <div className="flex items-center gap-2">
                                    <span className="font-semibold text-zinc-200 print:text-black">
                                      {c.criterion_name}
                                    </span>
                                    <span className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded ${
                                      c.status === "full_credit"
                                        ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                                        : c.status === "partial_credit"
                                        ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                                        : "bg-zinc-500/15 text-zinc-400 border border-zinc-500/30"
                                    }`}>
                                      {c.status.replace("_", " ")}
                                    </span>
                                  </div>
                                  {c.reason_for_deduction && (
                                    <p className="text-[11px] text-zinc-400 mt-1">
                                      <span className="text-amber-400/90 font-medium">Gap: </span>
                                      {c.reason_for_deduction}
                                    </p>
                                  )}
                                  {c.exemplary_example && (
                                    <p className="text-[11px] text-zinc-400 mt-0.5">
                                      <span className="text-emerald-400/90 font-medium">Model Response: </span>
                                      {c.exemplary_example}
                                    </p>
                                  )}
                                </div>

                                <div className="text-right shrink-0">
                                  <span className="font-mono font-bold text-white print:text-black">
                                    {c.marks_awarded} / {c.max_marks} Marks
                                  </span>
                                  {c.deduction > 0 && (
                                    <span className="block text-[10px] text-rose-400 font-mono">
                                      -{c.deduction} deduction
                                    </span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Bottom Sticky Action Bar */}
      <div className="p-6 rounded-3xl border border-white/[0.08] bg-zinc-950/90 backdrop-blur-2xl flex flex-col sm:flex-row items-center justify-between gap-4 print:hidden">
        <div className="space-y-0.5 text-center sm:text-left">
          <h4 className="text-sm font-semibold text-white">Ready for your next mock interview?</h4>
          <p className="text-xs text-zinc-400">
            Export this report to track your improvement, or start a new targeted session.
          </p>
        </div>
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <button
            onClick={handlePrint}
            className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl border border-white/10 bg-white/[0.04] hover:bg-white/[0.08] text-xs font-semibold text-white transition-all shadow-sm"
          >
            <Printer className="w-3.5 h-3.5 text-emerald-400" />
            <span>Print Report</span>
          </button>
          <button
            onClick={onReset}
            className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-black text-xs font-semibold transition-all shadow-[0_0_20px_rgba(16,185,129,0.25)]"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Start New Interview</span>
          </button>
        </div>
      </div>
    </div>
  );
}
