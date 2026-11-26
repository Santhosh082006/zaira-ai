"use client";

import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { Camera, CheckCircle, RefreshCw, Eye, Sparkles, Volume2, Mic, Brain } from "lucide-react";
import { Zaira3DAvatar } from "../../components/Zaira3DAvatar";
import { useAvatarVoice } from "../../hooks/useAvatarVoice";

type AnglePreset = "front" | "three_quarter" | "profile" | "eyes_closeup" | "upper_body";

interface PresetConfig {
  name: string;
  camPos: [number, number, number];
  lookAt: [number, number, number];
  fov: number;
}

const PRESETS: Record<AnglePreset, PresetConfig> = {
  front: {
    name: "1. Front-Facing Portrait",
    camPos: [0, 1.65, 0.85],
    lookAt: [0, 1.65, 0.13],
    fov: 28,
  },
  three_quarter: {
    name: "2. Three-Quarter View (45°)",
    camPos: [0.55, 1.65, 0.70],
    lookAt: [0, 1.65, 0.13],
    fov: 28,
  },
  profile: {
    name: "3. Side Profile (90°)",
    camPos: [0.80, 1.65, 0.13],
    lookAt: [0, 1.65, 0.13],
    fov: 28,
  },
  eyes_closeup: {
    name: "4. Close-Up Eyes & Facial Details",
    camPos: [0, 1.65, 0.42],
    lookAt: [0, 1.65, 0.13],
    fov: 20,
  },
  upper_body: {
    name: "5. Full Upper-Body & Blazer View",
    camPos: [0, 1.38, 1.65],
    lookAt: [0, 1.30, 0.05],
    fov: 34,
  },
};

export default function CandidatePreviewPage() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const [activePreset, setActivePreset] = useState<AnglePreset>("front");
  const [modelLoaded, setModelLoaded] = useState<boolean>(false);
  const [statusText, setStatusText] = useState<string>("Loading candidate model...");
  const [savedViews, setSavedViews] = useState<Record<string, boolean>>({});
  const [isExportingAll, setIsExportingAll] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<"static" | "live">("static");
  const [simState, setSimState] = useState<"idle" | "listening" | "thinking">("idle");

  const avatarVoice = useAvatarVoice();

  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const morphMeshesRef = useRef<Array<{ mesh: THREE.Mesh; dict: { [name: string]: number } }>>([]);

  const setMorph = (name: string, val: number) => {
    for (const { mesh, dict } of morphMeshesRef.current) {
      const idx = dict[name];
      if (idx !== undefined && mesh.morphTargetInfluences) {
        mesh.morphTargetInfluences[idx] = val;
      }
    }
  };

  const switchPreset = (presetKey: AnglePreset) => {
    setActivePreset(presetKey);
    const preset = PRESETS[presetKey];
    if (cameraRef.current) {
      cameraRef.current.position.set(...preset.camPos);
      cameraRef.current.lookAt(...preset.lookAt);
      cameraRef.current.fov = preset.fov;
      cameraRef.current.updateProjectionMatrix();
    }
  };

  useEffect(() => {
    const handleSwitch = (e: any) => {
      if (e.detail && PRESETS[e.detail as AnglePreset]) {
        switchPreset(e.detail as AnglePreset);
      }
    };
    window.addEventListener("switch-preset", handleSwitch);
    return () => window.removeEventListener("switch-preset", handleSwitch);
  }, []);

  useEffect(() => {
    if (viewMode !== "static") return;
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    let isDisposed = false;

    // 1. Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0c10);
    sceneRef.current = scene;

    // 2. Camera
    const camera = new THREE.PerspectiveCamera(
      PRESETS.front.fov,
      container.clientWidth / container.clientHeight,
      0.05,
      20
    );
    camera.position.set(...PRESETS.front.camPos);
    camera.lookAt(...PRESETS.front.lookAt);
    cameraRef.current = camera;

    // 3. Renderer with high color accuracy
    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      preserveDrawingBuffer: true,
      powerPreference: "high-performance",
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.02;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    rendererRef.current = renderer;

    // 4. Calibrated Natural Portrait Lighting
    const ambientLight = new THREE.AmbientLight(0xfff6ee, 0.45);
    scene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xfff4ea, 1.25);
    keyLight.position.set(1.2, 2.2, 1.8);
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0xeef4ff, 0.78);
    fillLight.position.set(-1.5, 1.7, 1.5);
    scene.add(fillLight);

    const rimLight = new THREE.DirectionalLight(0xf1f5f9, 0.55);
    rimLight.position.set(-0.2, 2.3, -1.6);
    scene.add(rimLight);

    const bounceLight = new THREE.DirectionalLight(0xf1f5f9, 0.22);
    bounceLight.position.set(0.0, 0.4, 1.2);
    scene.add(bounceLight);

    // 5. Load Candidate MPFB Model
    const loader = new GLTFLoader();
    loader.load(
      "/models/zaira.glb",
      (gltf) => {
        if (isDisposed) return;
        try {
          const model = gltf.scene;
          scene.add(model);

          const meshes: Array<{ mesh: THREE.Mesh; dict: { [name: string]: number } }> = [];

          model.traverse((child) => {
            if ((child as THREE.Mesh).isMesh || (child as THREE.SkinnedMesh).isSkinnedMesh) {
              const mesh = child as THREE.Mesh;
              mesh.frustumCulled = false;

              if (mesh.morphTargetDictionary && mesh.morphTargetInfluences) {
                meshes.push({
                  mesh,
                  dict: mesh.morphTargetDictionary,
                });
              }

              // Material adjustments for natural realistic skin and eyes
              if (mesh.material) {
                const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
                mats.forEach((m, idx) => {
                  const mName = (m.name || "").toLowerCase();
                  if (mName.includes("eyelash") || mName.includes("eyebrow") || mName.includes("brow")) {
                    m.transparent = true;
                    m.alphaTest = 0.22;
                    m.depthWrite = true;
                  } else if (mName.includes("hair") || mesh.name.toLowerCase().includes("hair")) {
                    m.transparent = true;
                    m.alphaTest = 0.28;
                    m.depthWrite = true;
                    (m as any).side = THREE.DoubleSide;
                    (m as any).roughness = 0.48;
                  } else if (mName.includes("high-poly") || mName.includes("eye")) {
                    const std = m as THREE.MeshStandardMaterial;
                    const phys = new THREE.MeshPhysicalMaterial({
                      map: std.map,
                      color: std.color ? std.color.clone() : new THREE.Color(0xffffff),
                      transparent: true,
                      alphaTest: 0.08,
                      depthWrite: true,
                      roughness: 0.04,
                      metalness: 0.0,
                      clearcoat: 1.0,
                      clearcoatRoughness: 0.02,
                      ior: 1.45,
                    });
                    if (Array.isArray(mesh.material)) {
                      mesh.material[idx] = phys;
                    } else {
                      mesh.material = phys;
                    }
                  } else if (mName.includes("body") || mName.includes("skin")) {
                    (m as any).roughness = (m as any).roughnessMap ? 1.0 : 0.72;
                    (m as any).metalness = 0.0;
                  }
                });
              }
            }

            if ((child as THREE.Bone).isBone) {
              const b = child as THREE.Bone;
              if (b.name === "LeftArm" || b.name === "RightArm") {
                b.rotateX(THREE.MathUtils.degToRad(28));
              } else if (b.name === "LeftForeArm" || b.name === "RightForeArm") {
                b.rotateX(THREE.MathUtils.degToRad(-10));
              }
            }
          });

          morphMeshesRef.current = meshes;

          // Natural friendly smile using ARKit 52 targets
          setMorph("mouthSmileLeft", 0.10);
          setMorph("mouthSmileRight", 0.10);

          setModelLoaded(true);
          setStatusText("Candidate model ready. Review all 5 angles below.");
        } catch (e: any) {
          console.error("Error setting up candidate model:", e);
          setStatusText("Setup error: " + (e?.message || String(e)));
        }
      },
      (xhr) => {
        if (xhr.total > 0) {
          const pct = Math.round((xhr.loaded / xhr.total) * 100);
          setStatusText(`Loading candidate model (${pct}%)...`);
        }
      },
      (err) => {
        if (isDisposed) return;
        console.error("Error loading candidate model:", err);
        setStatusText("Error loading candidate model: " + String(err));
      }
    );

    // Render loop
    let reqId: number;
    const renderLoop = () => {
      reqId = requestAnimationFrame(renderLoop);
      renderer.render(scene, camera);
    };
    reqId = requestAnimationFrame(renderLoop);

    return () => {
      isDisposed = true;
      cancelAnimationFrame(reqId);
      renderer.dispose();
      scene.clear();
    };
  }, [viewMode]);

  const captureSingleView = async (presetKey: AnglePreset) => {
    switchPreset(presetKey);
    await new Promise((r) => setTimeout(r, 150));

    const canvas = canvasRef.current;
    if (!canvas) return;

    const dataUrl = canvas.toDataURL("image/png");
    try {
      const res = await fetch("http://localhost:8000/api/candidate/save-preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: `candidate_view_${presetKey}`,
          image_base64: dataUrl,
        }),
      });
      if (res.ok) {
        setSavedViews((prev) => ({ ...prev, [presetKey]: true }));
      }
    } catch (e) {
      console.error("Failed to post preview:", e);
    }
  };

  const captureAllFiveViews = async () => {
    setIsExportingAll(true);
    setStatusText("Rendering all 5 required angles at full resolution...");

    const keys: AnglePreset[] = ["front", "three_quarter", "profile", "eyes_closeup", "upper_body"];
    for (const k of keys) {
      await captureSingleView(k);
      await new Promise((r) => setTimeout(r, 200));
    }

    switchPreset("front");
    setIsExportingAll(false);
    setStatusText("All 5 preview angles successfully rendered and saved!");
  };

  return (
    <div className="min-h-screen bg-[#07090e] text-white flex flex-col items-center p-6 space-y-6">
      {/* Header */}
      <div className="w-full max-w-5xl flex items-center justify-between border-b border-white/10 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-teal-400 animate-pulse" />
            <h1 className="text-xl font-bold font-mono tracking-tight text-white">
              Zaira AI — Digital Human Candidate Preview (MPFB / CC0)
            </h1>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Free & Open-Source Rigged 3D Female Character • High-Fidelity ARKit 52 Blendshapes • CC0 Commercial
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            data-testid="tab-static"
            onClick={() => {
              avatarVoice.stopSpeaking();
              setViewMode("static");
            }}
            className={`px-3 py-2 rounded-xl text-xs font-mono border transition-all ${
              viewMode === "static"
                ? "bg-teal-500/20 border-teal-400 text-teal-200"
                : "bg-white/5 border-white/10 text-zinc-400 hover:text-white"
            }`}
          >
            5-Angle Inspector
          </button>
          <button
            data-testid="tab-live"
            onClick={() => setViewMode("live")}
            className={`px-3 py-2 rounded-xl text-xs font-mono border transition-all flex items-center gap-1.5 ${
              viewMode === "live"
                ? "bg-teal-500/20 border-teal-400 text-teal-200"
                : "bg-white/5 border-white/10 text-zinc-400 hover:text-white"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Live Animation & Speech</span>
          </button>
          {viewMode === "static" && (
            <button
              onClick={captureAllFiveViews}
              disabled={!modelLoaded || isExportingAll}
              className="px-4 py-2 rounded-xl bg-teal-500 hover:bg-teal-400 disabled:opacity-50 text-black font-semibold font-mono text-xs flex items-center gap-2 transition-all shadow-lg active:scale-95"
            >
              {isExportingAll ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Rendering 5 Views...</span>
                </>
              ) : (
                <>
                  <Camera className="w-4 h-4" />
                  <span>Capture All 5 Review Angles</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {viewMode === "live" ? (
        <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <div className="lg:col-span-8 bg-black/70 rounded-3xl border border-white/10 overflow-hidden relative shadow-2xl h-[560px]">
            <Zaira3DAvatar
              isSpeaking={avatarVoice.isSpeaking}
              isListening={!avatarVoice.isSpeaking && simState === "listening"}
              isThinking={!avatarVoice.isSpeaking && simState === "thinking"}
              analyserNode={avatarVoice.analyserNode}
              audioElement={avatarVoice.audioElement}
              wordTimings={avatarVoice.wordTimings}
              spokenText={avatarVoice.spokenText}
              speechGeneration={avatarVoice.speechGeneration}
              activeWord={avatarVoice.activeWord}
              mode="hero"
            />
          </div>

          <div className="lg:col-span-4 space-y-4">
            <div className="p-4 rounded-2xl bg-zinc-950/70 border border-white/10 space-y-3">
              <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-teal-400">
                State Machine Controls
              </h2>
              <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                <button
                  data-testid="state-idle"
                  onClick={() => {
                    avatarVoice.stopSpeaking();
                    setSimState("idle");
                  }}
                  className={`px-2 py-2 rounded-xl border ${
                    !avatarVoice.isSpeaking && simState === "idle"
                      ? "bg-teal-500/20 border-teal-400 text-white"
                      : "bg-white/5 border-white/10 text-zinc-400"
                  }`}
                >
                  Idle
                </button>
                <button
                  data-testid="state-listening"
                  onClick={() => {
                    avatarVoice.stopSpeaking();
                    setSimState("listening");
                  }}
                  className={`px-2 py-2 rounded-xl border flex items-center justify-center gap-1 ${
                    !avatarVoice.isSpeaking && simState === "listening"
                      ? "bg-teal-500/20 border-teal-400 text-white"
                      : "bg-white/5 border-white/10 text-zinc-400"
                  }`}
                >
                  <Mic className="w-3 h-3" />
                  <span>Listen</span>
                </button>
                <button
                  data-testid="state-thinking"
                  onClick={() => {
                    avatarVoice.stopSpeaking();
                    setSimState("thinking");
                  }}
                  className={`px-2 py-2 rounded-xl border flex items-center justify-center gap-1 ${
                    !avatarVoice.isSpeaking && simState === "thinking"
                      ? "bg-teal-500/20 border-teal-400 text-white"
                      : "bg-white/5 border-white/10 text-zinc-400"
                  }`}
                >
                  <Brain className="w-3 h-3" />
                  <span>Think</span>
                </button>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-zinc-950/70 border border-white/10 space-y-2.5">
              <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-teal-400">
                Phoneme Lip-Sync Audio Tests
              </h2>
              <button
                data-testid="speak-short"
                onClick={() =>
                  avatarVoice.speakText(
                    "Welcome back! Please briefly walk me through your best architectural decision."
                  )
                }
                className="w-full px-3 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-mono text-left flex items-center gap-2"
              >
                <Volume2 className="w-3.5 h-3.5 text-teal-400 shrink-0" />
                <span>Speak Short Prompt (~5s, M/B/P test)</span>
              </button>
              <button
                data-testid="speak-long"
                onClick={() =>
                  avatarVoice.speakText(
                    "Hello, I am Zaira, your technical interviewer today. Let us begin with system design and distributed architecture... Could you walk me through a complex production bottleneck you personally solved, explain how you balanced performance, reliability, and fault tolerance, and describe what measurable value or improvements your fix achieved?"
                  )
                }
                className="w-full px-3 py-2 rounded-xl bg-teal-500/15 hover:bg-teal-500/25 border border-teal-500/40 text-xs font-mono text-left flex items-center gap-2 text-teal-200"
              >
                <Volume2 className="w-3.5 h-3.5 text-teal-400 shrink-0" />
                <span>Speak Long Interview (~20s)</span>
              </button>
              <button
                data-testid="speak-repeat"
                onClick={() =>
                  avatarVoice.speakText(
                    "Thank you. Now tell me how you mentor junior engineers on code quality and automated testing."
                  )
                }
                className="w-full px-3 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-mono text-left flex items-center gap-2"
              >
                <RefreshCw className="w-3.5 h-3.5 text-teal-400 shrink-0" />
                <span>Interrupt & Repeat Question</span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* 3D WebGL Viewport (8 cols) */}
        <div
          ref={containerRef}
          className="lg:col-span-8 bg-black/60 rounded-3xl border border-white/10 overflow-hidden relative shadow-2xl h-[560px] flex items-center justify-center"
        >
          <canvas ref={canvasRef} className="w-full h-full block" />

          {/* Active Preset Pill */}
          <div className="absolute top-4 left-4 z-20 px-3 py-1.5 rounded-full bg-black/75 backdrop-blur-md border border-white/15 text-xs font-mono text-teal-300 flex items-center gap-2">
            <Eye className="w-3.5 h-3.5 text-teal-400" />
            <span>{PRESETS[activePreset].name}</span>
          </div>

          {/* Status Overlay */}
          <div className="absolute bottom-4 inset-x-4 z-20 flex justify-center">
            <div className="px-4 py-1.5 rounded-full bg-black/80 backdrop-blur-md border border-white/10 text-[11px] font-mono text-zinc-300">
              {statusText}
            </div>
          </div>
        </div>

        {/* Inspection Panel (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          {/* Preset Buttons */}
          <div className="p-4 rounded-2xl bg-zinc-950/70 border border-white/10 space-y-3">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-teal-400">
              Required Review Angles
            </h2>
            <div className="space-y-2">
              {(Object.keys(PRESETS) as AnglePreset[]).map((key) => {
                const isSelected = activePreset === key;
                const isSaved = Boolean(savedViews[key]);
                return (
                  <button
                    key={key}
                    onClick={() => switchPreset(key)}
                    className={`w-full text-left px-3 py-2.5 rounded-xl text-xs font-mono transition-all flex items-center justify-between border ${
                      isSelected
                        ? "bg-teal-500/20 border-teal-500/50 text-white font-medium shadow-md"
                        : "bg-white/[0.03] border-white/5 text-zinc-400 hover:text-white hover:bg-white/[0.06]"
                    }`}
                  >
                    <span>{PRESETS[key].name}</span>
                    {isSaved && <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Blendshape & Rig Verification Controls */}
          <div className="p-4 rounded-2xl bg-zinc-950/70 border border-white/10 space-y-3">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-teal-400">
              Facial Rig Verification
            </h2>
            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
              <button
                onClick={() => {
                  setMorph("mouthSmileLeft", 0.40);
                  setMorph("mouthSmileRight", 0.40);
                  setMorph("viseme_aa", 0);
                  setMorph("eyeBlinkLeft", 0);
                  setMorph("eyeBlinkRight", 0);
                }}
                className="px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 text-center"
              >
                Smile (0.40)
              </button>
              <button
                onClick={() => {
                  setMorph("viseme_aa", 0.55);
                  setMorph("jawOpen", 0.25);
                }}
                className="px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 text-center"
              >
                Open AA (0.55)
              </button>
              <button
                onClick={() => {
                  setMorph("viseme_O", 0.60);
                  setMorph("jawOpen", 0.20);
                }}
                className="px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 text-center"
              >
                Pucker O (0.60)
              </button>
              <button
                onClick={() => {
                  setMorph("eyeBlinkLeft", 1.0);
                  setMorph("eyeBlinkRight", 1.0);
                }}
                className="px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-300 text-center"
              >
                Blink (1.0)
              </button>
              <button
                onClick={() => {
                  setMorph("mouthSmileLeft", 0.10);
                  setMorph("mouthSmileRight", 0.10);
                  setMorph("viseme_aa", 0);
                  setMorph("viseme_O", 0);
                  setMorph("jawOpen", 0);
                  setMorph("eyeBlinkLeft", 0);
                  setMorph("eyeBlinkRight", 0);
                }}
                className="col-span-2 px-2.5 py-1.5 rounded-lg bg-teal-500/10 hover:bg-teal-500/20 border border-teal-500/30 text-teal-300 text-center"
              >
                Reset to Resting Expression
              </button>
            </div>
          </div>

          {/* Specifications Checklist */}
          <div className="p-4 rounded-2xl bg-zinc-950/70 border border-white/10 space-y-2 text-[11px] text-zinc-400">
            <h3 className="font-mono font-bold text-white text-xs">Model Specifications</h3>
            <ul className="space-y-1">
              <li>• Base: MakeHuman Community / MPFB</li>
              <li>• Attire: Professional dark female suit</li>
              <li>• Rig: 66 facial blendshapes + visemes</li>
              <li>• License: CC0 / CC-BY (100% Free & Open)</li>
              <li>• Status: Isolated preview (Not integrated)</li>
            </ul>
          </div>
        </div>
      </div>
      )}
    </div>
  );
}
