"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { Sparkles, AlertCircle } from "lucide-react";

export interface Zaira3DAvatarProps {
  isSpeaking: boolean;
  isListening?: boolean;
  isThinking?: boolean;
  analyserNode?: AnalyserNode | null;
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
  analyserNode = null,
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

  // Audio frequency buffer
  const freqDataRef = useRef<Uint8Array<ArrayBuffer> | null>(null);

  // Animation state tracking
  const nextBlinkTimeRef = useRef<number>(Date.now() + 2000);
  const blinkDurationRef = useRef<number>(130);
  const isBlinkingRef = useRef<boolean>(false);
  const blinkStartRef = useRef<number>(0);

  // Current smoothed blendshape values
  const currentVisemesRef = useRef<{ [name: string]: number }>({
    jawOpen: 0,
    viseme_aa: 0,
    viseme_E: 0,
    viseme_I: 0,
    viseme_O: 0,
    viseme_SS: 0,
    viseme_sil: 1,
    mouthSmile: 0.08,
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

  // Update frequency data buffer when analyser node is ready
  useEffect(() => {
    if (analyserNode) {
      freqDataRef.current = new Uint8Array(analyserNode.frequencyBinCount);
    }
  }, [analyserNode]);

  // Main Three.js Scene Setup & Model Loading
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    let isDisposed = false;

    // 1. Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // 2. Camera: Precise portrait framing for the realistic model
    // Model Head world Y is at 1.68m, eyes at 1.75m, mouth at 1.65m
    const fov = mode === "compact" ? 24 : 26;
    const camera = new THREE.PerspectiveCamera(
      fov,
      container.clientWidth / container.clientHeight,
      0.1,
      20
    );
    // Camera positioned at bust height (1.63m) looking at face center (1.66m)
    camera.position.set(0, 1.63, 0.72);
    camera.lookAt(0, 1.66, 0);
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
    renderer.toneMappingExposure = 1.05;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    rendererRef.current = renderer;

    // 4. Professional Studio 3-Point Lighting for natural human skin
    // Soft base ambient
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
    scene.add(ambientLight);

    // Key Light (top-front-right, warm white)
    const keyLight = new THREE.DirectionalLight(0xfffaed, 2.0);
    keyLight.position.set(1.2, 2.4, 1.8);
    scene.add(keyLight);

    // Fill Light (top-front-left, soft cool neutral)
    const fillLight = new THREE.DirectionalLight(0xdbeafe, 1.1);
    fillLight.position.set(-1.5, 1.8, 1.4);
    scene.add(fillLight);

    // Rim / Hair Light (back, teal/cyan accent matching Zaira aesthetic)
    const rimLight = new THREE.DirectionalLight(0x2dd4bf, 2.0);
    rimLight.position.set(0.0, 2.2, -1.6);
    scene.add(rimLight);

    // Subtle chest/chin bounce
    const bounceLight = new THREE.DirectionalLight(0x14b8a6, 0.4);
    bounceLight.position.set(0.0, 0.5, 1.0);
    scene.add(bounceLight);

    // 5. Load 3D Model (/models/zaira.glb)
    const loader = new GLTFLoader();
    loader.load(
      "/models/zaira.glb",
      (gltf) => {
        if (isDisposed) return;

        const model = gltf.scene;
        scene.add(model);
        modelRef.current = model;

        model.position.set(0, 0, 0);
        model.rotation.set(0, 0, 0);

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

        // Set natural resting face (mouth closed, subtle warm smile)
        for (const { mesh, dict } of morphMeshes) {
          if (!mesh.morphTargetInfluences) continue;
          if (dict.mouthSmile !== undefined) mesh.morphTargetInfluences[dict.mouthSmile] = 0.08;
          if (dict.viseme_sil !== undefined) mesh.morphTargetInfluences[dict.viseme_sil] = 1.0;
          if (dict.jawOpen !== undefined) mesh.morphTargetInfluences[dict.jawOpen] = 0.0;
          if (dict.mouthOpen !== undefined) mesh.morphTargetInfluences[dict.mouthOpen] = 0.0;
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

    // 7. 60 FPS Render & Animation Loop
    let clock = new THREE.Clock();

    const animate = () => {
      animationFrameRef.current = requestAnimationFrame(animate);

      const time = clock.getElapsedTime();
      const now = Date.now();

      // -------------------------------------------------------------
      // A. Procedural Eye Blinking (Every 2.8 - 4.5s, 130ms duration)
      // -------------------------------------------------------------
      if (!isBlinkingRef.current && now > nextBlinkTimeRef.current) {
        isBlinkingRef.current = true;
        blinkStartRef.current = now;
        blinkDurationRef.current = 120 + Math.random() * 30;
      }

      if (isBlinkingRef.current) {
        const elapsed = now - blinkStartRef.current;
        const progress = elapsed / blinkDurationRef.current;

        if (progress >= 1.0) {
          isBlinkingRef.current = false;
          setMorphTarget("eyeBlinkLeft", 0);
          setMorphTarget("eyeBlinkRight", 0);
          nextBlinkTimeRef.current = now + 2800 + Math.random() * 1700;
        } else {
          const blinkValue = Math.sin(progress * Math.PI);
          setMorphTarget("eyeBlinkLeft", blinkValue);
          setMorphTarget("eyeBlinkRight", blinkValue);
        }
      }

      // -------------------------------------------------------------
      // B. Procedural Head & Breathing Motion
      // -------------------------------------------------------------
      const bones = bonesRef.current;

      // 1. Natural idle breathing
      const breath = Math.sin(time * 1.6) * 0.0025;
      if (bones.spine2) {
        bones.spine2.rotation.x = breath;
      }
      if (bones.neck) {
        bones.neck.rotation.x = breath * 0.5;
      }

      // 2. Head posture
      if (bones.head) {
        if (isThinking) {
          // Attentive evaluation: slightly tilted up-left
          bones.head.rotation.x = THREE.MathUtils.lerp(bones.head.rotation.x, -0.03, 0.05);
          bones.head.rotation.y = THREE.MathUtils.lerp(bones.head.rotation.y, -0.05, 0.05);
          bones.head.rotation.z = THREE.MathUtils.lerp(bones.head.rotation.z, 0.02, 0.05);
          setMorphTarget("browInnerUp", THREE.MathUtils.lerp(currentVisemesRef.current.browInnerUp || 0, 0.14, 0.08));
          setMorphTarget("browDownLeft", THREE.MathUtils.lerp(currentVisemesRef.current.browDownLeft || 0, 0.10, 0.08));
        } else if (isListening) {
          // Attentive listening: affirmative nod while candidate speaks
          const nod = Math.sin(time * 2.2) * 0.02;
          const tilt = Math.sin(time * 0.8) * 0.012;
          bones.head.rotation.x = THREE.MathUtils.lerp(bones.head.rotation.x, nod + 0.015, 0.08);
          bones.head.rotation.y = THREE.MathUtils.lerp(bones.head.rotation.y, 0.0, 0.05);
          bones.head.rotation.z = THREE.MathUtils.lerp(bones.head.rotation.z, tilt, 0.05);
          setMorphTarget("browInnerUp", THREE.MathUtils.lerp(currentVisemesRef.current.browInnerUp || 0, 0.08, 0.08));
          setMorphTarget("browDownLeft", 0);
          setMorphTarget("browDownRight", 0);
        } else if (isSpeaking) {
          // Natural conversational head accents
          const pitch = Math.sin(time * 2.8) * 0.016;
          const yaw = Math.sin(time * 1.4) * 0.018;
          bones.head.rotation.x = THREE.MathUtils.lerp(bones.head.rotation.x, pitch, 0.08);
          bones.head.rotation.y = THREE.MathUtils.lerp(bones.head.rotation.y, yaw, 0.08);
          bones.head.rotation.z = THREE.MathUtils.lerp(bones.head.rotation.z, 0.0, 0.08);
          setMorphTarget("browInnerUp", THREE.MathUtils.lerp(currentVisemesRef.current.browInnerUp || 0, 0.06, 0.08));
          setMorphTarget("browDownLeft", 0);
          setMorphTarget("browDownRight", 0);
        } else {
          // Neutral resting gaze
          bones.head.rotation.x = THREE.MathUtils.lerp(bones.head.rotation.x, 0.0, 0.05);
          bones.head.rotation.y = THREE.MathUtils.lerp(bones.head.rotation.y, 0.0, 0.05);
          bones.head.rotation.z = THREE.MathUtils.lerp(bones.head.rotation.z, 0.0, 0.05);
          setMorphTarget("browInnerUp", THREE.MathUtils.lerp(currentVisemesRef.current.browInnerUp || 0, 0.0, 0.08));
          setMorphTarget("browDownLeft", 0);
          setMorphTarget("browDownRight", 0);
        }
      }

      // -------------------------------------------------------------
      // C. Realistic Audio-Driven Lip Synchronization
      // -------------------------------------------------------------
      let volume = 0;
      let targetJawOpen = 0;
      let targetVisemeAA = 0;
      let targetVisemeE = 0;
      let targetVisemeO = 0;
      let targetVisemeSS = 0;

      const freqData = freqDataRef.current;

      // Only articulate when speech is active AND real audio frequency data is present
      if (isSpeaking && analyserNode && freqData) {
        analyserNode.getByteFrequencyData(freqData);

        // Low Formant (F1: 200 - 800 Hz): Bins 2 to 9
        let lowSum = 0;
        for (let b = 2; b <= 9; b++) lowSum += freqData[b];
        const lowFormant = lowSum / (8 * 255);

        // Mid Formant (F2: 900 - 2200 Hz): Bins 10 to 24
        let midSum = 0;
        for (let b = 10; b <= 24; b++) midSum += freqData[b];
        const midFormant = midSum / (15 * 255);

        // High Formant (F3: 2300 - 4500 Hz): Bins 25 to 48
        let highSum = 0;
        for (let b = 25; b <= 48; b++) highSum += freqData[b];
        const highFormant = highSum / (24 * 255);

        // Overall voice volume
        volume = (lowFormant * 1.5 + midFormant + highFormant) / 3;

        // Threshold for speech vs silence/breath
        if (volume >= 0.04) {
          // Competitive phoneme selection (mutually exclusive dominance, never stack all at once)
          if (lowFormant > midFormant && lowFormant > highFormant) {
            // Open Vowel ("AA", "AH"): subtle jaw drop (max 0.20) + lip relaxation
            targetJawOpen = Math.min(0.20, lowFormant * 0.38);
            targetVisemeAA = Math.min(0.22, lowFormant * 0.42);
          } else if (midFormant > lowFormant) {
            // Front Vowel ("EE", "IH"): slight jaw drop (max 0.14) + spread lips
            targetJawOpen = Math.min(0.14, midFormant * 0.26);
            targetVisemeE = Math.min(0.20, midFormant * 0.38);
          } else if (lowFormant > 0.08 && midFormant > 0.08 && highFormant < 0.08) {
            // Rounded Vowel ("OH", "OO"): slight jaw drop (max 0.16) + rounded lips
            targetJawOpen = Math.min(0.16, lowFormant * 0.28);
            targetVisemeO = Math.min(0.22, lowFormant * 0.40);
          } else if (highFormant > 0.06) {
            // Fricative / Sibilant ("SS", "CH", "TH"): minimal jaw drop + dental viseme
            targetJawOpen = 0.04;
            targetVisemeSS = Math.min(0.16, highFormant * 0.32);
          }
        }
      }

      // Smooth interpolation for natural lip movement without jarring transitions
      const cur = currentVisemesRef.current;
      const isAudiblySpeaking = isSpeaking && volume >= 0.04;

      if (isAudiblySpeaking) {
        const lerpFactor = 0.30;
        setMorphTarget("jawOpen", THREE.MathUtils.lerp(cur.jawOpen || 0, targetJawOpen, lerpFactor));
        setMorphTarget("viseme_aa", THREE.MathUtils.lerp(cur.viseme_aa || 0, targetVisemeAA, lerpFactor));
        setMorphTarget("viseme_E", THREE.MathUtils.lerp(cur.viseme_E || 0, targetVisemeE, lerpFactor));
        setMorphTarget("viseme_O", THREE.MathUtils.lerp(cur.viseme_O || 0, targetVisemeO, lerpFactor));
        setMorphTarget("viseme_SS", THREE.MathUtils.lerp(cur.viseme_SS || 0, targetVisemeSS, lerpFactor));
        setMorphTarget("viseme_sil", THREE.MathUtils.lerp(cur.viseme_sil || 0, 0, 0.2));
        setMorphTarget("mouthSmile", 0.06);
      } else {
        // Silence or Speech concluded: smoothly close mouth to natural resting position within 50ms
        const closeSpeed = 0.28;
        setMorphTarget("jawOpen", THREE.MathUtils.lerp(cur.jawOpen || 0, 0, closeSpeed));
        setMorphTarget("viseme_aa", THREE.MathUtils.lerp(cur.viseme_aa || 0, 0, closeSpeed));
        setMorphTarget("viseme_E", THREE.MathUtils.lerp(cur.viseme_E || 0, 0, closeSpeed));
        setMorphTarget("viseme_O", THREE.MathUtils.lerp(cur.viseme_O || 0, 0, closeSpeed));
        setMorphTarget("viseme_SS", THREE.MathUtils.lerp(cur.viseme_SS || 0, 0, closeSpeed));
        setMorphTarget("viseme_sil", THREE.MathUtils.lerp(cur.viseme_sil || 0, 1.0, closeSpeed));
        setMorphTarget("mouthSmile", THREE.MathUtils.lerp(cur.mouthSmile || 0, 0.08, 0.1));
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
  }, [mode, isSpeaking, isListening, isThinking, analyserNode, setMorphTarget, onLoaded]);

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
