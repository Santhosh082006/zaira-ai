"use client";

import { useEffect, useRef, useState } from "react";
import { AlertCircle, ArrowLeft, ArrowRight, Camera, CheckCircle2, Mic, VideoOff } from "lucide-react";

type DeviceResult = "unchecked" | "passed" | "failed";

export function InterviewPreflight({ onContinue, onBack }: { onContinue: (stream: MediaStream | null) => void; onBack: () => void }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamsRef = useRef<MediaStream[]>([]);
  const contextRef = useRef<AudioContext | null>(null);
  const frameRef = useRef<number | null>(null);
  const [cameraResult, setCameraResult] = useState<DeviceResult>("unchecked");
  const [micResult, setMicResult] = useState<DeviceResult>("unchecked");
  const [audioLevel, setAudioLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const stopAnalyzer = () => {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    frameRef.current = null;
    if (contextRef.current) {
      void contextRef.current.close();
      contextRef.current = null;
    }
  };

  const releaseStreams = () => {
    stopAnalyzer();
    streamsRef.current.forEach((stream) => stream.getTracks().forEach((track) => track.stop()));
    streamsRef.current = [];
    if (videoRef.current) videoRef.current.srcObject = null;
  };

  const stopStreams = () => {
    releaseStreams();
    setAudioLevel(0);
  };

  useEffect(() => () => releaseStreams(), []);

  const runChecks = async () => {
    stopStreams();
    setError(null);
    setChecking(true);
    setCameraResult("unchecked");
    setMicResult("unchecked");

    let cameraStream: MediaStream | null = null;
    let micStream: MediaStream | null = null;
    try {
      cameraStream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 360 } });
      streamsRef.current.push(cameraStream);
      setCameraResult("passed");
      if (videoRef.current) videoRef.current.srcObject = cameraStream;
    } catch {
      setCameraResult("failed");
    }
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamsRef.current.push(micStream);
      setMicResult("passed");
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        const context = new AudioCtx();
        contextRef.current = context;
        const analyser = context.createAnalyser();
        analyser.fftSize = 256;
        context.createMediaStreamSource(micStream).connect(analyser);
        const bins = new Uint8Array(analyser.frequencyBinCount);
        const update = () => {
          if (!streamsRef.current.length) return;
          analyser.getByteTimeDomainData(bins);
          const rms = Math.sqrt(bins.reduce((sum, value) => sum + ((value - 128) / 128) ** 2, 0) / bins.length);
          setAudioLevel(Math.min(100, Math.round(rms * 240)));
          frameRef.current = requestAnimationFrame(update);
        };
        update();
      }
    } catch {
      setMicResult("failed");
    }
    if (!cameraStream && !micStream) setError("Camera and microphone access was denied. Check browser permissions, then run the tests again.");
    setChecking(false);
  };

  const tested = cameraResult !== "unchecked" && micResult !== "unchecked";
  const resultLine = (label: string, result: DeviceResult) => (
    <div className="flex items-center justify-between rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-sm">
      <span className="text-zinc-200">{label}</span>
      <span className={result === "passed" ? "text-emerald-300" : result === "failed" ? "text-amber-300" : "text-zinc-500"}>
        {result === "passed" ? "Ready" : result === "failed" ? "Not available" : "Not checked"}
      </span>
    </div>
  );

  return (
    <section className="max-w-3xl mx-auto p-6 md:p-8 rounded-3xl border border-white/[0.08] bg-zinc-950/80 space-y-6">
      <div>
        <div className="text-xs uppercase tracking-widest text-emerald-300 mb-2">Before the interview</div>
        <h2 className="text-2xl font-semibold text-white">Check your camera and microphone</h2>
        <p className="text-sm text-zinc-400 mt-2">Run the device check, confirm the preview and microphone level, then continue.</p>
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        <div className="relative aspect-video rounded-xl overflow-hidden bg-black border border-white/10 flex items-center justify-center">
          <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover -scale-x-100" />
          {cameraResult !== "passed" && <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-zinc-400"><VideoOff className="w-7 h-7"/><span className="text-xs">Camera preview appears here</span></div>}
          <span className="absolute top-3 left-3 rounded-md bg-black/70 px-2 py-1 text-xs"><Camera className="inline w-3.5 h-3.5 mr-1"/>Camera</span>
        </div>
        <div className="rounded-xl border border-white/10 bg-black/30 p-4 flex flex-col justify-between gap-4">
          <div className="flex items-center gap-2 text-sm text-zinc-200"><Mic className="w-4 h-4 text-emerald-300"/>Microphone level <span className="ml-auto font-mono text-emerald-300">{audioLevel}%</span></div>
          <div className="h-3 rounded-full bg-white/10 overflow-hidden"><div className="h-full bg-gradient-to-r from-emerald-500 to-cyan-400 transition-[width] duration-100" style={{ width: `${audioLevel}%` }}/></div>
          <p className="text-xs text-zinc-400">Say a few words. The meter should move while you speak.</p>
          <div className="space-y-2">{resultLine("Camera", cameraResult)}{resultLine("Microphone", micResult)}</div>
        </div>
      </div>
      {error && <div role="alert" className="flex items-center gap-2 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-200"><AlertCircle className="w-4 h-4"/>{error}</div>}
      {tested && <div className="flex items-center gap-2 text-xs text-zinc-400"><CheckCircle2 className="w-4 h-4 text-emerald-300"/>Device results are shown above. You can continue even if a device is unavailable.</div>}
      <div className="flex flex-col-reverse sm:flex-row sm:justify-between gap-3 border-t border-white/10 pt-5">
          <button type="button" onClick={() => { stopStreams(); onBack(); }} className="rounded-xl border border-white/10 px-4 py-3 text-sm text-zinc-300 hover:bg-white/5"><ArrowLeft className="inline w-4 h-4 mr-2"/>Back to setup</button>
        <div className="flex flex-col-reverse sm:flex-row gap-3">
          <button type="button" disabled={checking} onClick={runChecks} className="rounded-xl border border-white/10 px-4 py-3 text-sm text-zinc-200 hover:bg-white/5 disabled:opacity-50">{checking ? "Checking devices…" : tested ? "Run checks again" : "Test camera & mic"}</button>
          <button type="button" disabled={!tested || checking} onClick={() => {
            stopAnalyzer();
            const tracks = streamsRef.current.flatMap((stream) => stream.getTracks());
            const sharedStream = tracks.length ? new MediaStream(tracks) : null;
            streamsRef.current = [];
            if (videoRef.current) videoRef.current.srcObject = null;
            onContinue(sharedStream);
          }} className="rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 px-5 py-3 text-sm font-semibold text-black disabled:cursor-not-allowed disabled:opacity-40">Continue to interview <ArrowRight className="inline w-4 h-4 ml-2"/></button>
        </div>
      </div>
    </section>
  );
}
