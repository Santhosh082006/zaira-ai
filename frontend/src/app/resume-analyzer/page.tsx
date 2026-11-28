"use client";

import Link from "next/link";
import { ChangeEvent, useMemo, useState } from "react";
import { ArrowLeft, CheckCircle2, FileSearch, Loader2, UploadCloud } from "lucide-react";
import { parseResumeFile, ResumeParseResult } from "@/lib/interviewApi";

const SECTION_CHECKS = [
  { label: "Experience", pattern: /\b(experience|employment|work history|professional history)\b/i },
  { label: "Education", pattern: /\b(education|academic background|qualifications)\b/i },
  { label: "Skills", pattern: /\b(skills|technical skills|core competencies|expertise)\b/i },
  { label: "Projects", pattern: /\b(projects|selected projects|portfolio)\b/i },
  { label: "Contact details", pattern: /(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+?\d[\d\s().-]{7,}\d))/ },
];

export default function ResumeAnalyzerPage() {
  const [result, setResult] = useState<ResumeParseResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const sectionResults = useMemo(() => result ? SECTION_CHECKS.map((item) => ({ label: item.label, found: item.pattern.test(result.text) })) : [], [result]);

  const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const parsed = await parseResumeFile(file);
      if (!parsed.success || !parsed.text) setError(parsed.error || "We could not extract readable text from this file.");
      else setResult(parsed);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Resume parsing failed. Check that the backend is running and try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#050508] text-zinc-100">
      <header className="border-b border-white/[0.08] bg-[#07080c] px-5 py-4 md:px-8 flex items-center justify-between">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-white"><ArrowLeft className="w-4 h-4"/>Back to Zaira AI</Link>
        <span className="text-xs text-zinc-500">Independent feature</span>
      </header>
      <main className="max-w-5xl mx-auto px-5 py-10 md:px-8 md:py-14 space-y-7">
        <div>
          <div className="inline-flex items-center gap-2 text-xs uppercase tracking-widest text-emerald-300 mb-3"><FileSearch className="w-4 h-4"/>Resume Analyzer</div>
          <h1 className="text-3xl md:text-4xl font-semibold tracking-tight">Review a resume</h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-zinc-400">Upload a PDF, Word document or text file to extract its text and check for common sections. Section checks are simple text matches, not a measure of candidate quality.</p>
        </div>
        <label className="flex min-h-48 cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-white/15 bg-white/[0.02] p-8 text-center hover:border-emerald-400/40">
          <input className="sr-only" type="file" accept=".pdf,.docx,.txt,.md,.rtf" onChange={handleFile} disabled={busy}/>
          {busy ? <Loader2 className="w-8 h-8 animate-spin text-emerald-300"/> : <UploadCloud className="w-8 h-8 text-emerald-300"/>}
          <span className="font-medium">{busy ? "Extracting resume text…" : "Choose a resume to review"}</span>
          <span className="text-xs text-zinc-500">PDF, DOCX, TXT, MD or RTF</span>
        </label>
        {error && <div role="alert" className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}
        {result && <section className="grid gap-5 lg:grid-cols-[280px_1fr]">
          <aside className="space-y-4 rounded-2xl border border-white/10 bg-white/[0.02] p-5">
            <div><div className="text-sm font-semibold">Document overview</div><div className="mt-1 break-all text-xs text-zinc-500">{result.filename}</div></div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="rounded-lg bg-black/30 p-3"><div className="text-zinc-500">Pages</div><div className="mt-1 text-lg">{result.page_count}</div></div>
              <div className="rounded-lg bg-black/30 p-3"><div className="text-zinc-500">Words</div><div className="mt-1 text-lg">{result.word_count}</div></div>
            </div>
            <div className="space-y-2"><div className="text-xs font-medium text-zinc-300">Common sections found in text</div>{sectionResults.map(({ label, found }) => <div key={label} className="flex items-center gap-2 text-xs text-zinc-400"><CheckCircle2 className={`w-3.5 h-3.5 ${found ? "text-emerald-300" : "text-zinc-600"}`}/>{label}<span className="ml-auto">{found ? "Found" : "Not detected"}</span></div>)}</div>
            <p className="border-t border-white/10 pt-3 text-[11px] leading-relaxed text-zinc-500">“Not detected” means the parser did not find a matching heading or contact pattern. It does not prove the resume lacks that information.</p>
          </aside>
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5 md:p-6">
            <h2 className="text-sm font-semibold">Extracted text</h2>
            <pre className="mt-4 max-h-[65vh] overflow-auto whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-zinc-300">{result.text}</pre>
          </div>
        </section>}
      </main>
    </div>
  );
}
