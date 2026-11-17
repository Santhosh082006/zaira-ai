"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  getAvatarSessionToken,
  AvatarTokenResponse,
  fetchQuestionPcmAudio,
  PcmAudioResponse,
} from "../lib/interviewApi";

export type LiveAvatarState =
  | "IDLE"
  | "CONNECTING"
  | "CONNECTED"
  | "SPEAKING"
  | "ERROR"
  | "UNCONFIGURED";

interface UseLiveAvatarOptions {
  onSpeechStart?: () => void;
  onSpeechEnd?: () => void;
  onError?: (err: string) => void;
}

export function useLiveAvatar({
  onSpeechStart,
  onSpeechEnd,
  onError,
}: UseLiveAvatarOptions = {}) {
  const [state, setState] = useState<LiveAvatarState>("IDLE");
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [isConfigured, setIsConfigured] = useState<boolean>(false);
  const [avatarId, setAvatarId] = useState<string | null>(null);
  const [hasActiveStream, setHasActiveStream] = useState<boolean>(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const sessionRef = useRef<any>(null);
  const connectingPromiseRef = useRef<Promise<boolean> | null>(null);
  const streamReadyRef = useRef<boolean>(false);
  const cachedTokenRef = useRef<string | null>(null);
  const currentEventIdRef = useRef<string | null>(null);

  // Dynamic attach callback to support video elements mounted at any time
  const attachVideo = useCallback((node: HTMLVideoElement | null) => {
    videoRef.current = node;
    if (!node) {
      console.log("[LiveAvatar] Video element detached/unmounted");
      return;
    }

    console.log("[LiveAvatar] Video element mounted, ready for WebRTC attachment");
    node.playsInline = true;

    // Track when real video frames actually arrive and render
    node.onloadedmetadata = () => {
      console.log(`[LiveAvatar] Video metadata loaded: ${node.videoWidth}x${node.videoHeight}`);
      if (node.videoWidth > 0) {
        setHasActiveStream(true);
      }
    };

    node.onplaying = () => {
      console.log("[LiveAvatar] Video element is playing received WebRTC stream");
      setHasActiveStream(true);
    };

    // If session and stream are already active, attach immediately
    if (sessionRef.current && streamReadyRef.current) {
      try {
        console.log("[LiveAvatar] Attaching video element to existing active WebRTC stream");
        sessionRef.current.attach(node);
        node.play().catch((err) => {
          console.log("[LiveAvatar] Autoplay caught (will play on interaction):", err);
        });
      } catch (err) {
        console.warn("[LiveAvatar] attach notice:", err);
      }
    }
  }, []);

  // Check backend credentials status on mount
  useEffect(() => {
    let isMounted = true;
    async function checkStatus() {
      try {
        const tokenRes: AvatarTokenResponse = await getAvatarSessionToken();
        if (!isMounted) return;
        if (tokenRes.available && tokenRes.token) {
          setIsConfigured(true);
          cachedTokenRef.current = tokenRes.token;
          setAvatarId(tokenRes.avatar_id || null);
          setStatusMessage("HeyGen LiveAvatar Lite configured and ready.");
        } else {
          setIsConfigured(false);
          setStatusMessage(tokenRes.message || "HEYGEN_API_KEY not configured in .env");
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        setIsConfigured(false);
        setStatusMessage("Failed to reach avatar credentials endpoint.");
      }
    }
    checkStatus();
    return () => {
      isMounted = false;
    };
  }, []);

  // Enter attentive listening state (mouth naturally closed, natural presence)
  const startListening = useCallback(() => {
    const session = sessionRef.current;
    if (!session) return;

    try {
      if (typeof session.startListening === "function") {
        session.startListening();
        return;
      }
    } catch {
      // Fallback to raw WebSocket event below
    }

    const socket = (session as any)._sessionEventSocket as WebSocket | undefined;
    const eventId =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : "evt_" + Math.random().toString(36).substring(2, 11);

    if (socket && socket.readyState === WebSocket.OPEN) {
      try {
        socket.send(
          JSON.stringify({
            type: "agent.start_listening",
            event_id: eventId,
          })
        );
      } catch (err) {
        console.warn("Failed to send start_listening over WebSocket:", err);
      }
    }
  }, []);

  // Exit listening state
  const stopListening = useCallback(() => {
    const session = sessionRef.current;
    if (!session) return;

    try {
      if (typeof session.stopListening === "function") {
        session.stopListening();
        return;
      }
    } catch {
      // Fallback to raw WebSocket event below
    }

    const socket = (session as any)._sessionEventSocket as WebSocket | undefined;
    const eventId =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : "evt_" + Math.random().toString(36).substring(2, 11);

    if (socket && socket.readyState === WebSocket.OPEN) {
      try {
        socket.send(
          JSON.stringify({
            type: "agent.stop_listening",
            event_id: eventId,
          })
        );
      } catch (err) {
        console.warn("Failed to send stop_listening over WebSocket:", err);
      }
    }
  }, []);

  // Interrupt avatar speech immediately and transition to listening state
  const interrupt = useCallback(() => {
    const session = sessionRef.current;
    if (!session) return;

    try {
      if (typeof session.interrupt === "function") {
        session.interrupt();
      }
    } catch {
      // ignore
    }

    const socket = (session as any)._sessionEventSocket as WebSocket | undefined;
    const eventId =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : "evt_" + Math.random().toString(36).substring(2, 11);

    if (socket && socket.readyState === WebSocket.OPEN) {
      try {
        socket.send(
          JSON.stringify({
            type: "agent.interrupt",
            event_id: eventId,
          })
        );
      } catch (err) {
        console.warn("Failed to send interrupt over WebSocket:", err);
      }
    }
    setState("CONNECTED");
    startListening();
  }, [startListening]);

  // Connect to HeyGen LiveAvatar WebRTC session
  const connect = useCallback(async (): Promise<boolean> => {
    // If already connected, return success immediately
    if (sessionRef.current && (state === "CONNECTED" || state === "SPEAKING")) {
      return true;
    }

    // If connection is already in flight, reuse the same active promise
    if (connectingPromiseRef.current) {
      return connectingPromiseRef.current;
    }

    const connectionPromise = (async (): Promise<boolean> => {
      setState("CONNECTING");
      setStatusMessage("Establishing real-time WebRTC LiveAvatar Lite session...");

      try {
        // Reuse cached token or fetch fresh token
        let token = cachedTokenRef.current;
        if (!token) {
          const tokenRes = await getAvatarSessionToken();
          if (!tokenRes.available || !tokenRes.token) {
            setState("UNCONFIGURED");
            setStatusMessage(tokenRes.message || "HeyGen credentials not configured in .env");
            return false;
          }
          token = tokenRes.token;
          cachedTokenRef.current = token;
          setAvatarId(tokenRes.avatar_id || null);
        }

        // Dynamically load @heygen/liveavatar-web-sdk in browser client
        const { LiveAvatarSession, SessionEvent, AgentEventsEnum } = await import(
          "@heygen/liveavatar-web-sdk"
        );

        console.log("[LiveAvatar] Instantiating LiveAvatarSession with token...");
        const session = new LiveAvatarSession(token, {
          autoKeepAlive: true,
          voiceChat: {
            defaultMuted: true, // Zaira handles candidate mic input independently
          },
        });

        sessionRef.current = session;

        // Bind WebRTC MediaStream to video element once stream is ready
        session.on(SessionEvent.SESSION_STREAM_READY, () => {
          console.log("[LiveAvatar] SESSION_STREAM_READY fired from HeyGen!");
          streamReadyRef.current = true;
          if (videoRef.current) {
            try {
              session.attach(videoRef.current);
              videoRef.current.play().catch((err) => {
                console.log("[LiveAvatar] Stream play triggered:", err);
              });
              setHasActiveStream(true);
            } catch (attachErr) {
              console.warn("[LiveAvatar] Video attach error on stream ready:", attachErr);
            }
          }
        });

        // Track speech lifecycle events for turn-taking
        session.on(AgentEventsEnum.AVATAR_SPEAK_STARTED, () => {
          console.log("[LiveAvatar] Event: AVATAR_SPEAK_STARTED");
          setState("SPEAKING");
          onSpeechStart?.();
        });

        session.on(AgentEventsEnum.AVATAR_SPEAK_ENDED, () => {
          console.log("[LiveAvatar] Event: AVATAR_SPEAK_ENDED");
          setState("CONNECTED");
          // Smoothly enter attentive listening state so mouth stays naturally closed
          startListening();
          onSpeechEnd?.();
        });

        session.on(SessionEvent.SESSION_DISCONNECTED, () => {
          console.log("[LiveAvatar] Event: SESSION_DISCONNECTED");
          setState("IDLE");
          setHasActiveStream(false);
          streamReadyRef.current = false;
          sessionRef.current = null;
        });

        // Start the WebRTC session
        console.log("[LiveAvatar] Starting WebRTC session connection...");
        await session.start();

        // If video element is already mounted, attach immediately
        if (videoRef.current && streamReadyRef.current) {
          try {
            session.attach(videoRef.current);
            videoRef.current.play().catch(() => {});
            setHasActiveStream(true);
          } catch (e) {
            console.warn("[LiveAvatar] Immediate video attach note:", e);
          }
        }

        // Monitor WebSocket events without silently swallowing errors
        const socket = (session as any)._sessionEventSocket as WebSocket | undefined;
        if (socket) {
          socket.addEventListener("error", (ev) => {
            console.error("[HeyGen LiveAvatar WebSocket Error]:", ev);
            setStatusMessage("LiveAvatar WebSocket communication error.");
          });
          socket.addEventListener("close", (ev) => {
            console.warn(`[HeyGen LiveAvatar WebSocket Closed]: code=${ev.code}, reason=${ev.reason}`);
          });
        }

        setState("CONNECTED");
        setStatusMessage("LiveAvatar Lite connected over WebRTC.");

        // Start in listening / attentive idle state
        setTimeout(() => {
          startListening();
        }, 400);

        return true;
      } catch (err: unknown) {
        console.error("[LiveAvatar] Connection error:", err);
        const msg = err instanceof Error ? err.message : String(err);
        setState("ERROR");
        setStatusMessage(`LiveAvatar connection failed: ${msg}`);
        onError?.(msg);
        sessionRef.current = null;
        return false;
      }
    })();

    connectingPromiseRef.current = connectionPromise;
    try {
      return await connectionPromise;
    } finally {
      connectingPromiseRef.current = null;
    }
  }, [state, onSpeechStart, onSpeechEnd, onError, startListening]);

  // Speak a question generated by Zaira's LLM via PCM 24k 16-bit mono chunks
  const speakText = useCallback(
    async (text: string): Promise<boolean> => {
      if (!text || !text.trim()) return false;

      // 1. Fetch PCM 24k 16-bit mono base64 chunks from Zaira backend
      console.log("[LiveAvatar] Fetching PCM 24k audio for text articulation...");
      const pcmData: PcmAudioResponse | null = await fetchQuestionPcmAudio(text);
      if (!pcmData || !pcmData.chunks || pcmData.chunks.length === 0) {
        console.warn("[LiveAvatar] PCM 24k speech audio could not be synthesized.");
        return false;
      }

      // 2. Ensure LiveAvatar session is connected
      if (!sessionRef.current || (state !== "CONNECTED" && state !== "SPEAKING")) {
        console.log("[LiveAvatar] Connecting session prior to speech...");
        const ok = await connect();
        if (!ok || !sessionRef.current) {
          console.warn("[LiveAvatar] Cannot speak: Session connection failed.");
          return false;
        }
      }

      const session = sessionRef.current;

      // 3. Exit listening state prior to articulating speech
      stopListening();

      // 4. Send audio: first try session.repeatAudio if available
      try {
        if (typeof session.repeatAudio === "function") {
          // Combine chunks or pass first full audio
          const fullAudio = pcmData.chunks.join("");
          session.repeatAudio(fullAudio);
          setState("SPEAKING");
          return true;
        }
      } catch (err) {
        console.log("[LiveAvatar] repeatAudio fallback to socket streaming:", err);
      }

      // 5. Fallback: Stream chunks directly over WebSocket
      const socket = (session as any)._sessionEventSocket as WebSocket | undefined;
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        console.warn("[LiveAvatar] WebSocket is not open for audio streaming.");
        return false;
      }

      const eventId =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : "evt_" + Math.random().toString(36).substring(2, 11);
      currentEventIdRef.current = eventId;

      try {
        for (const chunk of pcmData.chunks) {
          socket.send(
            JSON.stringify({
              type: "agent.speak",
              event_id: eventId,
              audio: chunk,
            })
          );
        }

        socket.send(
          JSON.stringify({
            type: "agent.speak_end",
            event_id: eventId,
          })
        );

        setState("SPEAKING");
        return true;
      } catch (err: unknown) {
        console.error("[LiveAvatar] Error streaming speech chunks to LiveAvatar:", err);
        return false;
      }
    },
    [connect, state, stopListening]
  );

  // Gracefully stop session and release WebRTC tracks
  const disconnect = useCallback(async () => {
    streamReadyRef.current = false;
    setHasActiveStream(false);
    if (sessionRef.current) {
      try {
        await sessionRef.current.stop();
      } catch {
        // ignore
      }
      sessionRef.current = null;
    }
    setState("IDLE");
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      streamReadyRef.current = false;
      setHasActiveStream(false);
      if (sessionRef.current) {
        sessionRef.current.stop().catch(() => {});
        sessionRef.current = null;
      }
    };
  }, []);

  return {
    state,
    isConfigured,
    avatarId,
    statusMessage,
    hasActiveStream,
    videoRef,
    attachVideo,
    connect,
    speakText,
    startListening,
    stopListening,
    interrupt,
    disconnect,
  };
}
