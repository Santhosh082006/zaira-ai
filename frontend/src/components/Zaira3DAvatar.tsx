"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { Sparkles, AlertCircle } from "lucide-react";

export interface Zaira3DAvatarProps {
  isSpeaking: boolean;
  isListening?: boolean;
  isThinking?: boolean;
  audioElement?: HTMLAudioElement | null;
  mode?: "hero" | "compact";
  className?: string;
  onLoaded?: () => void;
}

interface MorphMeshInfo {
  mesh: THREE.Mesh | THREE.SkinnedMesh;
  dict: { [name: string]: number };
}

export function Zaira3DAvatar({
  isSpeaking,
  isListening = false,
  isThinking = false,
  audioElement = null,
  mode = "hero",
  className = "",
  onLoaded,
}: Zaira3DAvatarProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Three.js internal references
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Model & Rigging references
  const modelRef = useRef<THREE.Group | null>(null);
  const morphMeshesRef = useRef<MorphMeshInfo[]>([]);
  const bonesRef = useRef<{
    head?: THREE.Bone;
    neck?: THREE.Bone;
    spine2?: THREE.Bone;
  }>({});

  // Audio analysis references
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioSourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const freqDataRef = useRef<Uint8Array<ArrayBuffer> | null>(null);

  // Animation state tracking
  const nextBlinkTimeRef = useRef<number>(Date.now() + 2000);
  const blinkDurationRef = useRef<number>(140);
  const isBlinkingRef = useRef<boolean>(false);
  const blinkStartRef = useRef<number>(0);

  // Current smoothed blendshape values (to prevent jerky transitions)
  const currentVisemesRef = useRef<{ [name: string]: number }>({
    jawOpen: 0,
    mouthOpen: 0,
    viseme_aa: 0,
    viseme_E: 0,
    viseme_I: 0,
    viseme_O: 0,
    viseme_U: 0,
    viseme_PP: 0,
    viseme_FF: 0,
    viseme_TH: 0,
    viseme_DD: 0,
    viseme_kk: 0,
    viseme_CH: 0,
    viseme_SS: 0,
    viseme_nn: 0,
    viseme_RR: 0,
    viseme_sil: 1,
    mouthSmile: 0.12,
    eyeBlinkLeft: 0,
    eyeBlinkRight: 0,
    browInnerUp: 0,
    browDownLeft: 0,
    browDownRight: 0,
  });

  // Helper to set a morph target value across all meshes in the model
  const setMorphTarget = useCallback((name: string, value: number) => {
    const clamped = Math.max(0, Math.min(1, value));
    currentVisemesRef.current[name] = clamped;

    const meshes = morphMeshesRef.current;
    for (let i = 0; i < meshes.length; i++) {
      const { mesh, dict } = meshes[i];
      const idx = dict[name];
      if (idx !== undefined && mesh.morphTargetInfluences) {
        mesh.morphTargetInfluences[idx] = clamped;
      }
    }
  }, []);

  // Connect Web Audio API to the authoritative audio element
  useEffect(() => {
    if (!audioElement) return;

    try {
      const AudioCtxClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtxClass) return;

      if (!audioContextRef.current) {
        audioContextRef.current = new AudioCtxClass();
      }

      const ctx = audioContextRef.current;
      if (ctx.state === "suspended") {
        ctx.resume().catch(() => {});
      }

      if (!analyserRef.current) {
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 512;
        analyser.smoothingTimeConstant = 0.5;
        analyserRef.current = analyser;
        freqDataRef.current = new Uint8Array(analyser.frequencyBinCount);
      }

      // Check if source already attached to avoid InvalidStateError
      if (!audioSourceRef.current && analyserRef.current) {
        try {
          const source = ctx.createMediaElementSource(audioElement);
          source.connect(analyserRef.current);
          analyserRef.current.connect(ctx.destination);
          audioSourceRef.current = source;
        } catch {
          // If already connected by browser or another node, ignore
        }
      }
    } catch (err) {
      console.warn("[Zaira3D] AudioContext init notice:", err);
    }
  }, [audioElement]);

  // Main Three.js Scene Setup & Model Loading
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    let isDisposed = false;

    // 1. Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // 2. Camera: Focused on upper bust / portrait framing
    // Height of face in zaira.glb is around y = 1.62m
    const fov = mode === "compact" ? 26 : 28;
    const camera = new THREE.PerspectiveCamera(
      fov,
      container.clientWidth / container.clientHeight,
      0.1,
      20
    );
    // Camera placed slightly below eye level looking slightly up
    camera.position.set(0, 1.58, 0.82);
    camera.lookAt(0, 1.62, 0);
    cameraRef.current = camera;

    // 3. Renderer with high-performance WebGL
    const renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    rendererRef.current = renderer;

    // 4. Professional Studio 3-Point Lighting
    // Base ambient
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    scene.add(ambientLight);

    // Key Light (top-front-right, warm white)
    const keyLight = new THREE.DirectionalLight(0xfff8f0, 2.2);
    keyLight.position.set(1.5, 2.6, 2.0);
    scene.add(keyLight);

    // Fill Light (top-front-left, soft cool neutral)
    const fillLight = new THREE.DirectionalLight(0xdbeafe, 1.3);
    fillLight.position.set(-1.8, 1.8, 1.5);
    scene.add(fillLight);

    // Rim / Hair Light (back, teal/cyan accent matching Zaira aesthetic)
    const rimLight = new THREE.DirectionalLight(0x2dd4bf, 2.4);
    rimLight.position.set(0.0, 2.2, -1.8);
    scene.add(rimLight);

    // Subtle soft bottom-up chest bounce
    const bounceLight = new THREE.DirectionalLight(0x0f766e, 0.5);
    bounceLight.position.set(0.0, 0.2, 1.0);
    scene.add(bounceLight);

    // 5. Load 3D Digital Human Model (/models/zaira.glb)
    const loader = new GLTFLoader();
    loader.load(
      "/models/zaira.glb",
      (gltf) => {
        if (isDisposed) return;

        const model = gltf.scene;
        scene.add(model);
        modelRef.current = model;

        // Position model: feet at ground, face centered
        model.position.set(0, 0, 0);
        model.rotation.set(0, 0, 0);

        // Scan meshes for morph targets and bones
        const morphMeshes: MorphMeshInfo[] = [];
        const bones: { head?: THREE.Bone; neck?: THREE.Bone; spine2?: THREE.Bone } = {};

        model.traverse((child) => {
          if ((child as THREE.Mesh).isMesh || (child as THREE.SkinnedMesh).isSkinnedMesh) {
            const mesh = child as THREE.Mesh | THREE.SkinnedMesh;
            mesh.frustumCulled = false;

            if (mesh.morphTargetDictionary && mesh.morphTargetInfluences) {
              morphMeshes.push({
                mesh,
                dict: mesh.morphTargetDictionary,
              });
            }

            // Material quality enhancements
            if (Array.isArray(mesh.material)) {
              mesh.material.forEach((m) => {
                m.transparent = false;
                m.depthWrite = true;
              });
            } else if (mesh.material) {
              mesh.material.transparent = false;
              mesh.material.depthWrite = true;
            }
          }

          if ((child as THREE.Bone).isBone) {
            const bone = child as THREE.Bone;
            if (bone.name === "Head") bones.head = bone;
            else if (bone.name === "Neck") bones.neck = bone;
            else if (bone.name === "Spine2") bones.spine2 = bone;
          }
        });

        morphMeshesRef.current = morphMeshes;
        bonesRef.current = bones;

        // Set natural resting face (gentle friendly smile)
        const meshes = morphMeshesRef.current;
        for (const { mesh, dict } of meshes) {
          if (!mesh.morphTargetInfluences) continue;
          if (dict.mouthSmile !== undefined) mesh.morphTargetInfluences[dict.mouthSmile] = 0.12;
          if (dict.viseme_sil !== undefined) mesh.morphTargetInfluences[dict.viseme_sil] = 1.0;
        }

        setIsLoading(false);
        onLoaded?.();
      },
      undefined,
      (err) => {
        if (isDisposed) return;
        console.error("[Zaira3D] Error loading 3D avatar GLB:", err);
        setLoadError("Unable to load 3D digital human asset.");
        setIsLoading(false);
      }
    );

    // 6. Handle Window & Container Resizing
    const handleResize = () => {
      if (!container || !renderer || !camera) return;
      const width = container.clientWidth;
      const height = container.clientHeight;
      if (width === 0 || height === 0) return;

      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    // 7. 60 FPS Render & Procedural Animation Loop
    let clock = new THREE.Clock();

    const animate = () => {
      animationFrameRef.current = requestAnimationFrame(animate);

      const delta = clock.getDelta();
      const time = clock.getElapsedTime();
      const now = Date.now();

      // -------------------------------------------------------------
      // A. Procedural Blinking
      // -------------------------------------------------------------
      if (!isBlinkingRef.current && now > nextBlinkTimeRef.current) {
        isBlinkingRef.current = true;
        blinkStartRef.current = now;
        blinkDurationRef.current = 130 + Math.random() * 40; // 130-170ms
      }

      if (isBlinkingRef.current) {
        const elapsed = now - blinkStartRef.current;
        const progress = elapsed / blinkDurationRef.current;

        if (progress >= 1.0) {
          isBlinkingRef.current = false;
          setMorphTarget("eyeBlinkLeft", 0);
          setMorphTarget("eyeBlinkRight", 0);
          // Next blink in 2.8 - 4.5 seconds
          nextBlinkTimeRef.current = now + 2800 + Math.random() * 1700;
        } else {
          // Smooth sine curve: open -> closed -> open
          const blinkValue = Math.sin(progress * Math.PI);
          setMorphTarget("eyeBlinkLeft", blinkValue);
          setMorphTarget("eyeBlinkRight", blinkValue);
        }
      }

      // -------------------------------------------------------------
      // B. Procedural Head & Body Motion
      // -------------------------------------------------------------
      const bones = bonesRef.current;

      // 1. Idle breathing (subtle chest and neck expansion)
      const breath = Math.sin(time * 1.7) * 0.003;
      if (bones.spine2) {
        bones.spine2.rotation.x = breath;
      }
      if (bones.neck) {
        bones.neck.rotation.x = breath * 0.5;
      }

      // 2. Attentive Listening / Speaking / Thinking head posture
      if (bones.head) {
        if (isThinking) {
          // Slightly tilted up-left during evaluation
          bones.head.rotation.x = THREE.MathUtils.lerp(bones.head.rotation.x, -0.04, 0.05);
          bones.head.rotation.y = THREE.MathUtils.lerp(bones.head.rotation.y, -0.06, 0.05);
          bones.head.rotation.z = THREE.MathUtils.lerp(bones.head.rotation.z, 0.02, 0.05);
          setMorphTarget("browInnerUp", THREE.MathUtils.lerp(currentVisemesRef.current.browInnerUp || 0, 0.18, 0.1));
          setMorphTarget("browDownLeft", THREE.MathUtils.lerp(currentVisemesRef.current.browDownLeft || 0, 0.12, 0.1));
        } else if (isListening) {
          // Attentive affirmative nods while candidate speaks
          const nod = Math.sin(time * 2.4) * 0.025;
          const tilt = Math.sin(time * 0.9) * 0.015;
          bones.head.rotation.x = THREE.MathUtils.lerp(bones.head.rotation.x, nod + 0.02, 0.08);
          bones.head.rotation.y = THREE.MathUtils.lerp(bones.head.rotation.y, 0.0, 0.05);
          bones.head.rotation.z = THREE.MathUtils.lerp(bones.head.rotation.z, tilt, 0.05);
          setMorphTarget("browInnerUp", THREE.MathUtils.lerp(currentVisemesRef.current.browInnerUp || 0, 0.10, 0.08));
          setMorphTarget("browDownLeft", 0);
          setMorphTarget("browDownRight", 0);
        } else if (isSpeaking) {
          // Natural conversational head accents
          const pitch = Math.sin(time * 3.2) * 0.02;
          const yaw = Math.sin(time * 1.5) * 0.025;
          bones.head.rotation.x = THREE.MathUtils.lerp(bones.head.rotation.x, pitch, 0.08);
          bones.head.rotation.y = THREE.MathUtils.lerp(bones.head.rotation.y, yaw, 0.08);
          bones.head.rotation.z = THREE.MathUtils.lerp(bones.head.rotation.z, 0.0, 0.08);
          setMorphTarget("browInnerUp", THREE.MathUtils.lerp(currentVisemesRef.current.browInnerUp || 0, 0.08, 0.1));
          setMorphTarget("browDownLeft", 0);
          setMorphTarget("browDownRight", 0);
        } else {
          // Neutral resting gaze targeting candidate
          bones.head.rotation.x = THREE.MathUtils.lerp(bones.head.rotation.x, 0.0, 0.05);
          bones.head.rotation.y = THREE.MathUtils.lerp(bones.head.rotation.y, 0.0, 0.05);
          bones.head.rotation.z = THREE.MathUtils.lerp(bones.head.rotation.z, 0.0, 0.05);
          setMorphTarget("browInnerUp", THREE.MathUtils.lerp(currentVisemesRef.current.browInnerUp || 0, 0.0, 0.08));
          setMorphTarget("browDownLeft", 0);
          setMorphTarget("browDownRight", 0);
        }
      }

      // -------------------------------------------------------------
      // C. Audio-Driven Lip Synchronization
      // -------------------------------------------------------------
      if (isSpeaking) {
        let volume = 0;
        let lowFormant = 0;
        let midFormant = 0;
        let highFormant = 0;

        const analyser = analyserRef.current;
        const freqData = freqDataRef.current;

        if (analyser && freqData && audioElement && !audioElement.paused) {
          analyser.getByteFrequencyData(freqData);

          // Bin frequencies: FFT size 512 = 256 bins across 24000 Hz (~93.75 Hz/bin)
          // Low Formant (F1: 200 - 800 Hz): Bins 2 to 9
          let lowSum = 0;
          for (let b = 2; b <= 9; b++) lowSum += freqData[b];
          lowFormant = lowSum / (8 * 255);

          // Mid Formant (F2: 900 - 2200 Hz): Bins 10 to 24
          let midSum = 0;
          for (let b = 10; b <= 24; b++) midSum += freqData[b];
          midFormant = midSum / (15 * 255);

          // High Formant (F3: 2300 - 4500 Hz): Bins 25 to 48
          let highSum = 0;
          for (let b = 25; b <= 48; b++) highSum += freqData[b];
          highFormant = highSum / (24 * 255);

          // Overall voice volume
          volume = Math.max(lowFormant * 1.2, (lowFormant + midFormant + highFormant) / 2.2);
        } else {
          // Synthetic speech cadence fallback when audio element analyser is not yet attached
          const speechCycle = Math.sin(time * 15.0) * 0.5 + 0.5;
          const syllableBurst = Math.sin(time * 4.5) * 0.3 + 0.7;
          volume = speechCycle * syllableBurst * 0.75;
          lowFormant = volume * 0.8;
          midFormant = (Math.cos(time * 12.0) * 0.5 + 0.5) * volume;
          highFormant = (Math.sin(time * 18.0) * 0.5 + 0.5) * volume * 0.6;
        }

        // Map audio frequencies to Viseme Blendshapes
        const targetJawOpen = Math.min(1.0, lowFormant * 1.5 + volume * 0.4);
        const targetVisemeAA = Math.min(1.0, lowFormant * 1.4);
        const targetVisemeE = Math.min(1.0, midFormant * 1.3);
        const targetVisemeO = Math.min(1.0, (lowFormant * 0.7 + highFormant * 0.3) * 1.1);
        const targetVisemeSS = Math.min(1.0, highFormant * 1.2);

        // Smooth interpolation for fluid lip articulation (no jitter)
        const lerpFactor = 0.35;
        const cur = currentVisemesRef.current;

        setMorphTarget("jawOpen", THREE.MathUtils.lerp(cur.jawOpen || 0, targetJawOpen, lerpFactor));
        setMorphTarget("mouthOpen", THREE.MathUtils.lerp(cur.mouthOpen || 0, targetJawOpen * 0.8, lerpFactor));
        setMorphTarget("viseme_aa", THREE.MathUtils.lerp(cur.viseme_aa || 0, targetVisemeAA, lerpFactor));
        setMorphTarget("viseme_E", THREE.MathUtils.lerp(cur.viseme_E || 0, targetVisemeE, lerpFactor));
        setMorphTarget("viseme_O", THREE.MathUtils.lerp(cur.viseme_O || 0, targetVisemeO, lerpFactor));
        setMorphTarget("viseme_SS", THREE.MathUtils.lerp(cur.viseme_SS || 0, targetVisemeSS, lerpFactor));
        setMorphTarget("viseme_sil", THREE.MathUtils.lerp(cur.viseme_sil || 0, Math.max(0, 1 - volume * 2), 0.2));
        setMorphTarget("mouthSmile", 0.10);
      } else {
        // Speech ended: smoothly close mouth to natural resting position within 60ms
        const cur = currentVisemesRef.current;
        const closeSpeed = 0.22;

        setMorphTarget("jawOpen", THREE.MathUtils.lerp(cur.jawOpen || 0, 0, closeSpeed));
        setMorphTarget("mouthOpen", THREE.MathUtils.lerp(cur.mouthOpen || 0, 0, closeSpeed));
        setMorphTarget("viseme_aa", THREE.MathUtils.lerp(cur.viseme_aa || 0, 0, closeSpeed));
        setMorphTarget("viseme_E", THREE.MathUtils.lerp(cur.viseme_E || 0, 0, closeSpeed));
        setMorphTarget("viseme_O", THREE.MathUtils.lerp(cur.viseme_O || 0, 0, closeSpeed));
        setMorphTarget("viseme_SS", THREE.MathUtils.lerp(cur.viseme_SS || 0, 0, closeSpeed));
        setMorphTarget("viseme_sil", THREE.MathUtils.lerp(cur.viseme_sil || 0, 1.0, closeSpeed));
        setMorphTarget("mouthSmile", THREE.MathUtils.lerp(cur.mouthSmile || 0, 0.14, 0.1));
      }

      // Render frame
      renderer.render(scene, camera);
    };

    animationFrameRef.current = requestAnimationFrame(animate);

    return () => {
      isDisposed = true;
      resizeObserver.disconnect();
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (renderer) {
        renderer.dispose();
      }
      if (scene) {
        scene.clear();
      }
    };
  }, [mode, isSpeaking, isListening, isThinking, audioElement, setMorphTarget, onLoaded]);

  return (
    <div
      ref={containerRef}
      className={`relative w-full h-full flex items-center justify-center overflow-hidden ${className}`}
    >
      {/* 3D WebGL Canvas */}
      <canvas
        ref={canvasRef}
        className={`w-full h-full object-contain pointer-events-none select-none transition-opacity duration-700 ${
          isLoading ? "opacity-0" : "opacity-100"
        }`}
      />

      {/* Loading Shimmer State */}
      {isLoading && !loadError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center space-y-3 p-6 text-center animate-fadeIn z-10">
          <div className="relative w-14 h-14 flex items-center justify-center">
            <div className="absolute inset-0 rounded-full border-2 border-teal-500/20 animate-ping" />
            <div className="w-12 h-12 rounded-full border-2 border-teal-500/30 border-t-teal-400 animate-spin flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-teal-400" />
            </div>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-mono font-medium text-white">Loading Digital Human</p>
            <p className="text-[11px] text-zinc-400">Initializing 60 FPS real-time interviewer avatar...</p>
          </div>
        </div>
      )}

      {/* Load Error State */}
      {loadError && (
        <div className="absolute inset-0 flex flex-col items-center justify-center space-y-2 p-6 text-center text-red-400 z-10">
          <AlertCircle className="w-6 h-6 text-red-400" />
          <p className="text-xs font-mono">{loadError}</p>
        </div>
      )}
    </div>
  );
}
