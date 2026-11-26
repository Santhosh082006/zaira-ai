"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import * as SkeletonUtils from "three/examples/jsm/utils/SkeletonUtils.js";
import { Sparkles, AlertCircle } from "lucide-react";
import {
  buildPhonemeTimeline,
  PhonemeFrame,
  sampleVisemeTimeline,
  WordTiming,
} from "../lib/visemeEngine";

// Module-level GLTF model cache with versioning to bust browser cache
const MODEL_VERSION = "20261126_v18";
const MODEL_URL = `/models/zaira.glb?v=${MODEL_VERSION}`;
let cachedGLTF: any = null;
let gltfPromise: Promise<any> | null = null;

function getZairaGLTF(loader: GLTFLoader): Promise<any> {
  if (cachedGLTF) {
    return Promise.resolve(cachedGLTF);
  }
  if (!gltfPromise) {
    gltfPromise = new Promise((resolve, reject) => {
      loader.load(
        MODEL_URL,
        (gltf) => {
          cachedGLTF = gltf;
          resolve(gltf);
        },
        undefined,
        (err) => {
          gltfPromise = null;
          reject(err);
        }
      );
    });
  }
  return gltfPromise;
}

export interface Zaira3DAvatarProps {
  isSpeaking: boolean;
  isListening?: boolean;
  isThinking?: boolean;
  analyserNode?: AnalyserNode | null;
  audioElement?: HTMLAudioElement | null;
  wordTimings?: WordTiming[];
  spokenText?: string;
  speechGeneration?: number;
  activeWord?: string;
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
  audioElement = null,
  wordTimings = [],
  spokenText = "",
  speechGeneration = 0,
  activeWord = "",
  mode = "hero",
  className = "",
  onLoaded,
}: Zaira3DAvatarProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(!cachedGLTF);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Keep latest props in refs to prevent unnecessary Three.js teardown & re-loading
  const isSpeakingRef = useRef<boolean>(isSpeaking);
  const isListeningRef = useRef<boolean>(isListening);
  const isThinkingRef = useRef<boolean>(isThinking);
  const analyserNodeRef = useRef<AnalyserNode | null>(analyserNode);
  const audioElementRef = useRef<HTMLAudioElement | null>(audioElement);
  const phonemeTimelineRef = useRef<PhonemeFrame[]>([]);
  const activeWordRef = useRef<string>(activeWord);
  const activeWordSinceRef = useRef<number>(0);
  const speechGenStartRef = useRef<number>(0);

  useEffect(() => {
    isSpeakingRef.current = isSpeaking;
    if (isSpeaking && speechGenStartRef.current === 0) {
      speechGenStartRef.current = performance.now();
    } else if (!isSpeaking) {
      speechGenStartRef.current = 0;
    }
  }, [isSpeaking]);

  useEffect(() => {
    isListeningRef.current = isListening;
  }, [isListening]);

  useEffect(() => {
    isThinkingRef.current = isThinking;
  }, [isThinking]);

  useEffect(() => {
    analyserNodeRef.current = analyserNode;
    if (analyserNode) {
      freqDataRef.current = new Uint8Array(analyserNode.frequencyBinCount);
    }
  }, [analyserNode]);

  useEffect(() => {
    audioElementRef.current = audioElement;
  }, [audioElement]);

  useEffect(() => {
    if (wordTimings && wordTimings.length > 0) {
      phonemeTimelineRef.current = buildPhonemeTimeline(wordTimings);
    } else {
      phonemeTimelineRef.current = [];
    }
  }, [wordTimings, speechGeneration]);

  useEffect(() => {
    activeWordRef.current = activeWord;
    activeWordSinceRef.current = performance.now();
  }, [activeWord, spokenText, speechGeneration]);

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
    leftArm?: THREE.Bone;
    rightArm?: THREE.Bone;
  }>({});
  const bonesRestRef = useRef<{
    headRot?: THREE.Euler;
    neckRot?: THREE.Euler;
    spine2Rot?: THREE.Euler;
  }>({});

  // Audio frequency buffer
  const freqDataRef = useRef<Uint8Array<ArrayBuffer> | null>(null);

  // Animation state tracking
  const nextBlinkTimeRef = useRef<number>(Date.now() + 2000);
  const blinkDurationRef = useRef<number>(115);
  const isBlinkingRef = useRef<boolean>(false);
  const blinkStartRef = useRef<number>(0);
  const pendingDoubleBlinkRef = useRef<boolean>(false);
  const activePhonemeRef = useRef<string | null>(null);

  // Current smoothed blendshape values
  const currentVisemesRef = useRef<{ [name: string]: number }>({
    jawOpen: 0,
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
    viseme_nn: 0,
    viseme_RR: 0,
    viseme_SS: 0,
    viseme_CH: 0,
    viseme_sil: 1,
    mouthSmile: 0.10,
    mouthClose: 0,
    mouthPressLeft: 0,
    mouthPressRight: 0,
    mouthRollLower: 0,
    mouthPucker: 0,
    mouthFunnel: 0,
    mouthLowerDownLeft: 0,
    mouthLowerDownRight: 0,
    mouthStretchLeft: 0,
    mouthStretchRight: 0,
    eyeBlinkLeft: 0,
    eyeBlinkRight: 0,
    eyeSquintLeft: 0,
    eyeSquintRight: 0,
    eyeLookInLeft: 0,
    eyeLookOutLeft: 0,
    eyeLookInRight: 0,
    eyeLookOutRight: 0,
    eyeLookUpLeft: 0,
    eyeLookDownLeft: 0,
    eyeLookUpRight: 0,
    eyeLookDownRight: 0,
    browInnerUp: 0,
    browOuterUpLeft: 0,
    browOuterUpRight: 0,
    browDownLeft: 0,
    browDownRight: 0,
    cheekSquintLeft: 0,
    cheekSquintRight: 0,
  });

  // Eye saccade timing
  const nextSaccadeTimeRef = useRef<number>(Date.now() + 1500);
  const targetEyeLookX = useRef<number>(0);
  const targetEyeLookY = useRef<number>(0);

  // Helper to set a morph target value across all meshes in the model
  const setMorphTarget = useCallback((name: string, value: number) => {
    const clamped = Math.max(0, Math.min(1, value));
    currentVisemesRef.current[name] = clamped;

    const meshes = morphMeshesRef.current;
    for (let i = 0; i < meshes.length; i++) {
      const { mesh, dict } = meshes[i];
      if (!mesh.morphTargetInfluences) continue;

      // Never distort tongue mesh with speech visemes so tongue remains properly inside the mouth
      if (mesh.name.toLowerCase().includes("tongue") && (name.startsWith("viseme_") || name === "jawOpen")) {
        continue;
      }

      // Teeth should ONLY follow jawOpen and never distort or double-open with speech vowels or lip drops
      if (mesh.name.toLowerCase().includes("teeth") && (name.startsWith("viseme_") || name.startsWith("mouth"))) {
        continue;
      }

      const idx = dict[name];
      if (idx !== undefined) {
        mesh.morphTargetInfluences[idx] = clamped;
      }

      // Automatically mirror unilateral smile blendshapes if mouthSmile is requested
      if (name === "mouthSmile") {
        if (dict.mouthSmileLeft !== undefined) mesh.morphTargetInfluences[dict.mouthSmileLeft] = clamped;
        if (dict.mouthSmileRight !== undefined) mesh.morphTargetInfluences[dict.mouthSmileRight] = clamped;
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
    // Head Y is at ~1.68m, eyes at 1.74m. Frame upper bust and head centered.
    const fov = mode === "compact" ? 28 : 30;
    const camera = new THREE.PerspectiveCamera(
      fov,
      container.clientWidth / container.clientHeight,
      0.1,
      20
    );
    // Camera positioned to frame head and tailored upper torso cleanly
    camera.position.set(0, 1.56, mode === "compact" ? 0.96 : 0.99);
    camera.lookAt(0, 1.56, 0);
    cameraRef.current = camera;

    // 3. Renderer with high-performance WebGL + soft shadow support
    const renderer = new THREE.WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.02;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    rendererRef.current = renderer;

    // 4. Studio Portrait Lighting (balanced three-point lighting + soft hemisphere fill for natural skin midtones)
    const ambientLight = new THREE.AmbientLight(0xfff6ee, 0.45);
    scene.add(ambientLight);

    const hemiLight = new THREE.HemisphereLight(0xf8fafc, 0x334155, 0.52);
    scene.add(hemiLight);

    // Warm Key Light (upper-front-right) calibrated for soft natural skin without hot specular blowout
    const keyLight = new THREE.DirectionalLight(0xfff4ea, 1.22);
    keyLight.position.set(0.85, 2.05, 1.65);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.width = 512;
    keyLight.shadow.mapSize.height = 512;
    keyLight.shadow.camera.near = 0.4;
    keyLight.shadow.camera.far = 5.0;
    keyLight.shadow.bias = -0.0006;
    keyLight.shadow.normalBias = 0.018;
    scene.add(keyLight);

    // Cool Fill Light (front-left)
    const fillLight = new THREE.DirectionalLight(0xeef4ff, 0.78);
    fillLight.position.set(-1.15, 1.68, 1.35);
    scene.add(fillLight);

    // Specular Eye Catchlight (adds crisp lifelike gleam on clearcoat corneas)
    const eyeCatchLight = new THREE.PointLight(0xffffff, 0.55, 3.2);
    eyeCatchLight.position.set(0.22, 1.72, 1.25);
    scene.add(eyeCatchLight);

    // Clean Natural Hair / Edge Rim Light (neutral daylight white instead of saturated teal tint)
    const rimLight = new THREE.DirectionalLight(0xf1f5f9, 0.58);
    rimLight.position.set(-0.25, 2.2, -1.4);
    scene.add(rimLight);

    // Soft Neutral Bounce Light (lifts chin & collar shadows subtly)
    const bounceLight = new THREE.DirectionalLight(0xf1f5f9, 0.18);
    bounceLight.position.set(0.0, 0.6, 1.0);
    scene.add(bounceLight);

    // 5. Load 3D Model (/models/zaira.glb) with module caching to eliminate loading screens
    const loader = new GLTFLoader();
    getZairaGLTF(loader)
      .then((gltf) => {
        if (isDisposed) return;

        // Clone model with skeleton/rig intact so each canvas instance runs cleanly
        const model = SkeletonUtils.clone(gltf.scene) as THREE.Group;
        scene.add(model);
        modelRef.current = model;

        model.position.set(0, 0, 0);
        model.rotation.set(0, 0, 0);

        const morphMeshes: MorphMeshInfo[] = [];
        const bones: {
          head?: THREE.Bone;
          neck?: THREE.Bone;
          spine2?: THREE.Bone;
          leftArm?: THREE.Bone;
          rightArm?: THREE.Bone;
        } = {};

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

            const meshNameLower = mesh.name.toLowerCase();
            const matName = (mesh.material && !Array.isArray(mesh.material)) ? (mesh.material as THREE.Material).name.toLowerCase() : "";

            mesh.castShadow = !meshNameLower.includes("high-poly") && !meshNameLower.includes("eyelash");
            mesh.receiveShadow = true;

            // EYES: Physical wet glass clearcoat while preserving cornea alpha cutout
            if (meshNameLower.includes("high-poly") || meshNameLower.includes("eye") || matName.includes("eye")) {
              const upgradeEyeMat = (origMat: any) => {
                return new THREE.MeshPhysicalMaterial({
                  map: origMat.map || null,
                  color: origMat.color ? origMat.color.clone() : new THREE.Color(0xffffff),
                  transparent: true,
                  alphaTest: 0.08,
                  depthWrite: true,
                  roughness: 0.05,
                  metalness: 0.0,
                  clearcoat: 1.0,
                  clearcoatRoughness: 0.02,
                  ior: 1.45,
                });
              };
              if (Array.isArray(mesh.material)) {
                mesh.material = mesh.material.map(upgradeEyeMat);
              } else if (mesh.material) {
                mesh.material = upgradeEyeMat(mesh.material);
              }
            }
            // EYELASHES: Clean alpha testing & depth writing
            else if (meshNameLower.includes("eyelash") || matName.includes("eyelash")) {
              if (Array.isArray(mesh.material)) {
                mesh.material.forEach((m) => {
                  m.transparent = true;
                  m.alphaTest = 0.20;
                  m.depthWrite = true;
                  m.needsUpdate = true;
                });
              } else if (mesh.material) {
                mesh.material.transparent = true;
                mesh.material.alphaTest = 0.20;
                mesh.material.depthWrite = true;
                mesh.material.needsUpdate = true;
              }
            }
            // EYEBROWS: Soft natural brow strands
            else if (meshNameLower.includes("eyebrow") || matName.includes("eyebrow") || matName.includes("brow")) {
              if (Array.isArray(mesh.material)) {
                mesh.material.forEach((m) => {
                  m.transparent = true;
                  m.alphaTest = 0.16;
                  m.depthWrite = true;
                  m.needsUpdate = true;
                });
              } else if (mesh.material) {
                mesh.material.transparent = true;
                mesh.material.alphaTest = 0.16;
                mesh.material.depthWrite = true;
                mesh.material.needsUpdate = true;
              }
            }
            // HAIR: Crisp dark brunette strands with double-sided rendering
            else if (meshNameLower.includes("hair") || matName.includes("hair") || meshNameLower.includes("ponytail")) {
              if (Array.isArray(mesh.material)) {
                mesh.material.forEach((m: any) => {
                  m.transparent = true;
                  m.alphaTest = 0.24;
                  m.depthWrite = true;
                  m.side = THREE.DoubleSide;
                  m.roughness = 0.46;
                  m.metalness = 0.0;
                  m.needsUpdate = true;
                });
              } else if (mesh.material) {
                const m = mesh.material as any;
                m.transparent = true;
                m.alphaTest = 0.24;
                m.depthWrite = true;
                m.side = THREE.DoubleSide;
                m.roughness = 0.46;
                m.metalness = 0.0;
                m.needsUpdate = true;
              }
            }
            // EXECUTIVE BLAZER & IVORY BLOUSE: Matte wool / silk fabric
            else if (meshNameLower.includes("blazer") || meshNameLower.includes("casualsuit") || matName.includes("blazer") || matName.includes("blouse") || matName.includes("casualsuit")) {
              if (Array.isArray(mesh.material)) {
                mesh.material.forEach((m: any) => {
                  m.roughness = 0.78;
                  m.metalness = 0.0;
                  m.side = THREE.DoubleSide;
                  m.needsUpdate = true;
                });
              } else if (mesh.material) {
                const m = mesh.material as any;
                m.roughness = 0.78;
                m.metalness = 0.0;
                m.side = THREE.DoubleSide;
                m.needsUpdate = true;
              }
            }
            // SKIN / FACE: Use roughness=1.0 when roughnessMap is attached so map values (0.68..0.76) aren't halved!
            else if (meshNameLower === "human" || meshNameLower === "base" || matName.includes("body") || matName.includes("skin")) {
              if (Array.isArray(mesh.material)) {
                mesh.material.forEach((m: any) => {
                  m.roughness = m.roughnessMap ? 1.0 : 0.72;
                  m.metalness = 0.0;
                  m.needsUpdate = true;
                });
              } else if (mesh.material) {
                const m = mesh.material as any;
                m.roughness = m.roughnessMap ? 1.0 : 0.72;
                m.metalness = 0.0;
                m.needsUpdate = true;
              }
            }
            // TEETH: Soft natural off-white enamel instead of stark paper #ffffff
            else if (meshNameLower.includes("teeth")) {
              if (mesh.material && !Array.isArray(mesh.material)) {
                const m = mesh.material as THREE.MeshStandardMaterial;
                m.color.setHex(0xebe6dc);
                m.roughness = 0.35;
                m.needsUpdate = true;
              }
            }
          }

          if ((child as THREE.Bone).isBone) {
            const bone = child as THREE.Bone;
            if (bone.name === "Head") {
              bones.head = bone;
              bonesRestRef.current.headRot = bone.rotation.clone();
            } else if (bone.name === "Neck") {
              bones.neck = bone;
              bonesRestRef.current.neckRot = bone.rotation.clone();
            } else if (bone.name === "Spine2") {
              bones.spine2 = bone;
              bonesRestRef.current.spine2Rot = bone.rotation.clone();
            } else if (bone.name === "LeftArm") {
              bones.leftArm = bone;
              bone.rotateX(THREE.MathUtils.degToRad(28));
            } else if (bone.name === "RightArm") {
              bones.rightArm = bone;
              bone.rotateX(THREE.MathUtils.degToRad(28));
            } else if (bone.name === "LeftForeArm" || bone.name === "RightForeArm") {
              bone.rotateX(THREE.MathUtils.degToRad(-10));
            }
          }
        });

        morphMeshesRef.current = morphMeshes;
        bonesRef.current = bones;

        // Set natural resting face (mouth closed, subtle warm corporate smile)
        for (const { mesh, dict } of morphMeshes) {
          if (!mesh.morphTargetInfluences) continue;
          if (dict.mouthSmile !== undefined) mesh.morphTargetInfluences[dict.mouthSmile] = 0.10;
          if (dict.mouthSmileLeft !== undefined) mesh.morphTargetInfluences[dict.mouthSmileLeft] = 0.10;
          if (dict.mouthSmileRight !== undefined) mesh.morphTargetInfluences[dict.mouthSmileRight] = 0.10;
          if (dict.viseme_sil !== undefined) mesh.morphTargetInfluences[dict.viseme_sil] = 1.0;
          if (dict.jawOpen !== undefined) mesh.morphTargetInfluences[dict.jawOpen] = 0.0;
          if (dict.mouthOpen !== undefined) mesh.morphTargetInfluences[dict.mouthOpen] = 0.0;
        }

        setIsLoading(false);
        onLoaded?.();
      })
      .catch((err) => {
        if (isDisposed) return;
        console.error("[Zaira3D] Error loading 3D avatar GLB:", err);
        setLoadError("Unable to load 3D digital human asset.");
        setIsLoading(false);
      });

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
      // A. Procedural Eye Blinking (Natural intervals + occasional double-blink)
      // -------------------------------------------------------------
      if (!isBlinkingRef.current && now > nextBlinkTimeRef.current) {
        isBlinkingRef.current = true;
        blinkStartRef.current = now;
        blinkDurationRef.current = 105 + Math.random() * 35;
      }

      if (isBlinkingRef.current) {
        const elapsed = now - blinkStartRef.current;
        const progress = elapsed / blinkDurationRef.current;

        if (progress >= 1.0) {
          isBlinkingRef.current = false;
          setMorphTarget("eyeBlinkLeft", 0);
          setMorphTarget("eyeBlinkRight", 0);
          if (pendingDoubleBlinkRef.current) {
            pendingDoubleBlinkRef.current = false;
            nextBlinkTimeRef.current = now + 2400 + Math.random() * 2200;
          } else if (Math.random() < 0.18) {
            pendingDoubleBlinkRef.current = true;
            nextBlinkTimeRef.current = now + 170;
          } else {
            nextBlinkTimeRef.current = now + 2400 + Math.random() * 2200;
          }
        } else {
          const blinkValue = Math.sin(progress * Math.PI);
          setMorphTarget("eyeBlinkLeft", blinkValue);
          setMorphTarget("eyeBlinkRight", blinkValue);
        }
      }

      // -------------------------------------------------------------
      // B. Procedural Head, Posture & State Expressions
      // -------------------------------------------------------------
      const bones = bonesRef.current;
      const rests = bonesRestRef.current;

      // 1. Natural idle breathing
      const breath = Math.sin(time * 1.55) * 0.003;
      if (bones.spine2 && rests.spine2Rot) {
        bones.spine2.rotation.x = rests.spine2Rot.x + breath;
      }
      if (bones.neck && rests.neckRot) {
        bones.neck.rotation.x = rests.neckRot.x + breath * 0.35;
      }

      const isSpeakingState = isSpeakingRef.current;
      const isListeningState = isListeningRef.current;
      const isThinkingState = isThinkingRef.current;
      const analyser = analyserNodeRef.current;
      const audioEl = audioElementRef.current;
      const cur = currentVisemesRef.current;

      // Measure syllable acoustic stress scalar (NEVER used alone as lip shape!)
      let acousticScale = 1.0;
      let audioVolume = 0;
      const freqData = freqDataRef.current;
      if (isSpeakingState && analyser && freqData) {
        analyser.getByteFrequencyData(freqData);
        let energySum = 0;
        for (let b = 2; b <= 32; b++) energySum += freqData[b];
        audioVolume = energySum / (31 * 255);
        acousticScale = 0.80 + Math.min(0.38, audioVolume * 1.8);
      }

      if (bones.head && rests.headRot) {
        if (isThinkingState) {
          bones.head.rotation.x = THREE.MathUtils.lerp(bones.head.rotation.x, rests.headRot.x - 0.025, 0.05);
          bones.head.rotation.y = THREE.MathUtils.lerp(bones.head.rotation.y, rests.headRot.y - 0.038, 0.05);
          bones.head.rotation.z = THREE.MathUtils.lerp(bones.head.rotation.z, rests.headRot.z + 0.024, 0.05);
          setMorphTarget("browInnerUp", THREE.MathUtils.lerp(cur.browInnerUp || 0, 0.14, 0.08));
          setMorphTarget("browDownLeft", THREE.MathUtils.lerp(cur.browDownLeft || 0, 0.08, 0.08));
          setMorphTarget("browDownRight", THREE.MathUtils.lerp(cur.browDownRight || 0, 0.04, 0.08));
        } else if (isListeningState) {
          const nod = Math.sin(time * 2.0) * 0.011;
          const tilt = Math.sin(time * 0.75) * 0.008;
          bones.head.rotation.x = THREE.MathUtils.lerp(bones.head.rotation.x, rests.headRot.x + nod + 0.008, 0.07);
          bones.head.rotation.y = THREE.MathUtils.lerp(bones.head.rotation.y, rests.headRot.y + 0.006, 0.05);
          bones.head.rotation.z = THREE.MathUtils.lerp(bones.head.rotation.z, rests.headRot.z + tilt, 0.05);
          setMorphTarget("browInnerUp", THREE.MathUtils.lerp(cur.browInnerUp || 0, 0.07, 0.08));
          setMorphTarget("browDownLeft", THREE.MathUtils.lerp(cur.browDownLeft || 0, 0, 0.1));
          setMorphTarget("browDownRight", THREE.MathUtils.lerp(cur.browDownRight || 0, 0, 0.1));
        } else if (isSpeakingState) {
          const stress = acousticScale - 1.0;
          const pitch = Math.sin(time * 2.4) * 0.011 + stress * 0.018;
          const yaw = Math.sin(time * 1.15) * 0.014;
          const roll = Math.sin(time * 0.9) * 0.006;
          bones.head.rotation.x = THREE.MathUtils.lerp(bones.head.rotation.x, rests.headRot.x + pitch, 0.08);
          bones.head.rotation.y = THREE.MathUtils.lerp(bones.head.rotation.y, rests.headRot.y + yaw, 0.07);
          bones.head.rotation.z = THREE.MathUtils.lerp(bones.head.rotation.z, rests.headRot.z + roll, 0.07);
        } else {
          const floatPitch = Math.sin(time * 0.65) * 0.004;
          const floatYaw = Math.sin(time * 0.45) * 0.005;
          bones.head.rotation.x = THREE.MathUtils.lerp(bones.head.rotation.x, rests.headRot.x + floatPitch, 0.05);
          bones.head.rotation.y = THREE.MathUtils.lerp(bones.head.rotation.y, rests.headRot.y + floatYaw, 0.05);
          bones.head.rotation.z = THREE.MathUtils.lerp(bones.head.rotation.z, rests.headRot.z, 0.05);
          setMorphTarget("browInnerUp", THREE.MathUtils.lerp(cur.browInnerUp || 0, 0.0, 0.08));
          setMorphTarget("browDownLeft", THREE.MathUtils.lerp(cur.browDownLeft || 0, 0, 0.1));
          setMorphTarget("browDownRight", THREE.MathUtils.lerp(cur.browDownRight || 0, 0, 0.1));
        }
      }

      // -------------------------------------------------------------
      // C. Eye Gaze & Micro-Saccades (state-aware)
      // -------------------------------------------------------------
      if (now > nextSaccadeTimeRef.current) {
        nextSaccadeTimeRef.current = now + (isListeningState ? 2200 : 1500) + Math.random() * 1700;
        if (isThinkingState) {
          targetEyeLookX.current = -0.10 + (Math.random() - 0.5) * 0.04;
          targetEyeLookY.current = 0.09 + (Math.random() - 0.5) * 0.03;
        } else if (isListeningState) {
          targetEyeLookX.current = (Math.random() - 0.5) * 0.03;
          targetEyeLookY.current = (Math.random() - 0.5) * 0.02;
        } else {
          targetEyeLookX.current = (Math.random() - 0.5) * 0.07;
          targetEyeLookY.current = (Math.random() - 0.5) * 0.04;
        }
      }
      const saccadeSpeed = 0.12;
      const eyeX = targetEyeLookX.current;
      const eyeY = targetEyeLookY.current;

      setMorphTarget("eyeLookInLeft", THREE.MathUtils.lerp(cur.eyeLookInLeft || 0, Math.max(0, eyeX), saccadeSpeed));
      setMorphTarget("eyeLookOutLeft", THREE.MathUtils.lerp(cur.eyeLookOutLeft || 0, Math.max(0, -eyeX), saccadeSpeed));
      setMorphTarget("eyeLookInRight", THREE.MathUtils.lerp(cur.eyeLookInRight || 0, Math.max(0, -eyeX), saccadeSpeed));
      setMorphTarget("eyeLookOutRight", THREE.MathUtils.lerp(cur.eyeLookOutRight || 0, Math.max(0, eyeX), saccadeSpeed));

      setMorphTarget("eyeLookUpLeft", THREE.MathUtils.lerp(cur.eyeLookUpLeft || 0, Math.max(0, eyeY), saccadeSpeed));
      setMorphTarget("eyeLookDownLeft", THREE.MathUtils.lerp(cur.eyeLookDownLeft || 0, Math.max(0, -eyeY), saccadeSpeed));
      setMorphTarget("eyeLookUpRight", THREE.MathUtils.lerp(cur.eyeLookUpRight || 0, Math.max(0, eyeY), saccadeSpeed));
      setMorphTarget("eyeLookDownRight", THREE.MathUtils.lerp(cur.eyeLookDownRight || 0, Math.max(0, -eyeY), saccadeSpeed));

      // -------------------------------------------------------------
      // D. Phoneme-to-Viseme Lip Synchronization (WordBoundary -> G2P)
      // -------------------------------------------------------------
      const timeline = phonemeTimelineRef.current;
      const audioActive = !audioEl || (!audioEl.ended && !audioEl.paused);
      let sampledWeights: Record<string, number> | null = null;
      let currentTimeMs = 0;

      if (isSpeakingState && audioActive) {
        if (timeline.length > 0) {
          currentTimeMs = audioEl ? audioEl.currentTime * 1000 : Math.max(0, performance.now() - speechGenStartRef.current);
          const sampled = sampleVisemeTimeline(timeline, currentTimeMs, acousticScale);
          sampledWeights = sampled.weights;
          activePhonemeRef.current = sampled.activePhoneme;
        } else if (activeWordRef.current.trim().length > 0) {
          // Browser SpeechSynthesis word-boundary fallback: articulate actual phonemes of spoken word
          const wordTimeline = buildPhonemeTimeline([
            { word: activeWordRef.current, offset_ms: 0, duration_ms: 300 },
          ]);
          const wordElapsed = Math.min(295, Math.max(0, performance.now() - activeWordSinceRef.current));
          const sampled = sampleVisemeTimeline(wordTimeline, wordElapsed, 1.0);
          sampledWeights = sampled.weights;
          activePhonemeRef.current = sampled.activePhoneme;
        }
      }

      if (sampledWeights && isSpeakingState && audioActive) {
        // Fast coarticulated transitions so bilabial M/B/P closures and vowel peaks land cleanly
        const lerpFactor = 0.44;
        setMorphTarget("jawOpen", THREE.MathUtils.lerp(cur.jawOpen || 0, sampledWeights.jawOpen || 0, lerpFactor));
        setMorphTarget("viseme_aa", THREE.MathUtils.lerp(cur.viseme_aa || 0, sampledWeights.viseme_aa || 0, lerpFactor));
        setMorphTarget("viseme_E", THREE.MathUtils.lerp(cur.viseme_E || 0, sampledWeights.viseme_E || 0, lerpFactor));
        setMorphTarget("viseme_I", THREE.MathUtils.lerp(cur.viseme_I || 0, sampledWeights.viseme_I || 0, lerpFactor));
        setMorphTarget("viseme_O", THREE.MathUtils.lerp(cur.viseme_O || 0, sampledWeights.viseme_O || 0, lerpFactor));
        setMorphTarget("viseme_U", THREE.MathUtils.lerp(cur.viseme_U || 0, sampledWeights.viseme_U || 0, lerpFactor));
        setMorphTarget("viseme_PP", THREE.MathUtils.lerp(cur.viseme_PP || 0, sampledWeights.viseme_PP || 0, lerpFactor));
        setMorphTarget("viseme_FF", THREE.MathUtils.lerp(cur.viseme_FF || 0, sampledWeights.viseme_FF || 0, lerpFactor));
        setMorphTarget("viseme_TH", THREE.MathUtils.lerp(cur.viseme_TH || 0, sampledWeights.viseme_TH || 0, lerpFactor));
        setMorphTarget("viseme_DD", THREE.MathUtils.lerp(cur.viseme_DD || 0, sampledWeights.viseme_DD || 0, lerpFactor));
        setMorphTarget("viseme_kk", THREE.MathUtils.lerp(cur.viseme_kk || 0, sampledWeights.viseme_kk || 0, lerpFactor));
        setMorphTarget("viseme_nn", THREE.MathUtils.lerp(cur.viseme_nn || 0, sampledWeights.viseme_nn || 0, lerpFactor));
        setMorphTarget("viseme_RR", THREE.MathUtils.lerp(cur.viseme_RR || 0, sampledWeights.viseme_RR || 0, lerpFactor));
        setMorphTarget("viseme_SS", THREE.MathUtils.lerp(cur.viseme_SS || 0, sampledWeights.viseme_SS || 0, lerpFactor));
        setMorphTarget("viseme_CH", THREE.MathUtils.lerp(cur.viseme_CH || 0, sampledWeights.viseme_CH || 0, lerpFactor));
        setMorphTarget("mouthClose", THREE.MathUtils.lerp(cur.mouthClose || 0, sampledWeights.mouthClose || 0, lerpFactor));
        setMorphTarget("mouthPressLeft", THREE.MathUtils.lerp(cur.mouthPressLeft || 0, sampledWeights.mouthPressLeft || 0, lerpFactor));
        setMorphTarget("mouthPressRight", THREE.MathUtils.lerp(cur.mouthPressRight || 0, sampledWeights.mouthPressRight || 0, lerpFactor));
        setMorphTarget("mouthRollLower", THREE.MathUtils.lerp(cur.mouthRollLower || 0, sampledWeights.mouthRollLower || 0, lerpFactor));
        setMorphTarget("mouthPucker", THREE.MathUtils.lerp(cur.mouthPucker || 0, sampledWeights.mouthPucker || 0, lerpFactor));
        setMorphTarget("mouthFunnel", THREE.MathUtils.lerp(cur.mouthFunnel || 0, sampledWeights.mouthFunnel || 0, lerpFactor));
        setMorphTarget("mouthStretchLeft", THREE.MathUtils.lerp(cur.mouthStretchLeft || 0, sampledWeights.mouthStretchLeft || 0, lerpFactor));
        setMorphTarget("mouthStretchRight", THREE.MathUtils.lerp(cur.mouthStretchRight || 0, sampledWeights.mouthStretchRight || 0, lerpFactor));
        setMorphTarget("mouthLowerDownLeft", THREE.MathUtils.lerp(cur.mouthLowerDownLeft || 0, 0, 0.35));
        setMorphTarget("mouthLowerDownRight", THREE.MathUtils.lerp(cur.mouthLowerDownRight || 0, 0, 0.35));
        setMorphTarget("viseme_sil", THREE.MathUtils.lerp(cur.viseme_sil || 0, sampledWeights.viseme_sil || 0, lerpFactor));
        setMorphTarget("mouthSmile", THREE.MathUtils.lerp(cur.mouthSmile || 0, 0.07, 0.12));

        const browLift = Math.min(0.09, Math.max(0, acousticScale - 0.85) * 0.25);
        const cheekLift = Math.min(0.05, Math.max(0, acousticScale - 0.85) * 0.14);
        setMorphTarget("browInnerUp", THREE.MathUtils.lerp(cur.browInnerUp || 0, 0.04 + browLift, 0.15));
        setMorphTarget("cheekSquintLeft", THREE.MathUtils.lerp(cur.cheekSquintLeft || 0, cheekLift, 0.15));
        setMorphTarget("cheekSquintRight", THREE.MathUtils.lerp(cur.cheekSquintRight || 0, cheekLift, 0.15));
      } else {
        activePhonemeRef.current = null;
        const closeSpeed = 0.28;
        setMorphTarget("jawOpen", THREE.MathUtils.lerp(cur.jawOpen || 0, 0, closeSpeed));
        setMorphTarget("viseme_aa", THREE.MathUtils.lerp(cur.viseme_aa || 0, 0, closeSpeed));
        setMorphTarget("viseme_E", THREE.MathUtils.lerp(cur.viseme_E || 0, 0, closeSpeed));
        setMorphTarget("viseme_I", THREE.MathUtils.lerp(cur.viseme_I || 0, 0, closeSpeed));
        setMorphTarget("viseme_O", THREE.MathUtils.lerp(cur.viseme_O || 0, 0, closeSpeed));
        setMorphTarget("viseme_U", THREE.MathUtils.lerp(cur.viseme_U || 0, 0, closeSpeed));
        setMorphTarget("viseme_PP", THREE.MathUtils.lerp(cur.viseme_PP || 0, 0, closeSpeed));
        setMorphTarget("viseme_FF", THREE.MathUtils.lerp(cur.viseme_FF || 0, 0, closeSpeed));
        setMorphTarget("viseme_TH", THREE.MathUtils.lerp(cur.viseme_TH || 0, 0, closeSpeed));
        setMorphTarget("viseme_DD", THREE.MathUtils.lerp(cur.viseme_DD || 0, 0, closeSpeed));
        setMorphTarget("viseme_kk", THREE.MathUtils.lerp(cur.viseme_kk || 0, 0, closeSpeed));
        setMorphTarget("viseme_nn", THREE.MathUtils.lerp(cur.viseme_nn || 0, 0, closeSpeed));
        setMorphTarget("viseme_RR", THREE.MathUtils.lerp(cur.viseme_RR || 0, 0, closeSpeed));
        setMorphTarget("viseme_SS", THREE.MathUtils.lerp(cur.viseme_SS || 0, 0, closeSpeed));
        setMorphTarget("viseme_CH", THREE.MathUtils.lerp(cur.viseme_CH || 0, 0, closeSpeed));
        setMorphTarget("mouthClose", THREE.MathUtils.lerp(cur.mouthClose || 0, 0, closeSpeed));
        setMorphTarget("mouthPressLeft", THREE.MathUtils.lerp(cur.mouthPressLeft || 0, 0, closeSpeed));
        setMorphTarget("mouthPressRight", THREE.MathUtils.lerp(cur.mouthPressRight || 0, 0, closeSpeed));
        setMorphTarget("mouthRollLower", THREE.MathUtils.lerp(cur.mouthRollLower || 0, 0, closeSpeed));
        setMorphTarget("mouthPucker", THREE.MathUtils.lerp(cur.mouthPucker || 0, 0, closeSpeed));
        setMorphTarget("mouthFunnel", THREE.MathUtils.lerp(cur.mouthFunnel || 0, 0, closeSpeed));
        setMorphTarget("mouthLowerDownLeft", THREE.MathUtils.lerp(cur.mouthLowerDownLeft || 0, 0, closeSpeed));
        setMorphTarget("mouthLowerDownRight", THREE.MathUtils.lerp(cur.mouthLowerDownRight || 0, 0, closeSpeed));
        setMorphTarget("mouthStretchLeft", THREE.MathUtils.lerp(cur.mouthStretchLeft || 0, 0, closeSpeed));
        setMorphTarget("mouthStretchRight", THREE.MathUtils.lerp(cur.mouthStretchRight || 0, 0, closeSpeed));
        setMorphTarget("viseme_sil", THREE.MathUtils.lerp(cur.viseme_sil || 0, 1.0, closeSpeed));
        setMorphTarget("mouthSmile", THREE.MathUtils.lerp(cur.mouthSmile || 0, isListeningState ? 0.13 : 0.10, 0.08));
        setMorphTarget("cheekSquintLeft", THREE.MathUtils.lerp(cur.cheekSquintLeft || 0, 0, closeSpeed));
        setMorphTarget("cheekSquintRight", THREE.MathUtils.lerp(cur.cheekSquintRight || 0, 0, closeSpeed));
      }

      if (typeof window !== "undefined") {
        (window as any).__ZAIRA_AVATAR_DEBUG__ = {
          state: isSpeakingState ? "SPEAKING" : isListeningState ? "LISTENING" : isThinkingState ? "THINKING" : "IDLE",
          activePhoneme: activePhonemeRef.current,
          audioTimeMs: Math.round(currentTimeMs),
          audioVolume: Number(audioVolume.toFixed(3)),
          viseme_PP: Number((cur.viseme_PP || 0).toFixed(3)),
          viseme_FF: Number((cur.viseme_FF || 0).toFixed(3)),
          mouthRollLower: Number((cur.mouthRollLower || 0).toFixed(3)),
          jawOpen: Number((cur.jawOpen || 0).toFixed(3)),
          viseme_aa: Number((cur.viseme_aa || 0).toFixed(3)),
          viseme_E: Number((cur.viseme_E || 0).toFixed(3)),
          viseme_O: Number((cur.viseme_O || 0).toFixed(3)),
          viseme_U: Number((cur.viseme_U || 0).toFixed(3)),
          viseme_sil: Number((cur.viseme_sil || 0).toFixed(3)),
          eyeBlinkLeft: Number((cur.eyeBlinkLeft || 0).toFixed(3)),
        };
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
  }, [mode, setMorphTarget, onLoaded]);

  return (
    <div
      ref={containerRef}
      className={`relative w-full h-full flex items-center justify-center overflow-hidden ${className}`}
    >
      {/* 3D WebGL Canvas */}
      <canvas
        ref={canvasRef}
        className={`w-full h-full block pointer-events-none select-none transition-opacity duration-700 ${
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
