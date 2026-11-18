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

export interface LiveAvatarDiagnostics {
  tokenStatus: "idle" | "requesting" | "available" | "error" | "unconfigured";
  sessionStatus: "idle" | "connecting" | "connected" | "disconnected" | "error";
  webrtcConnectionState: string;
  iceConnectionState: string;
  remoteVideoReceived: boolean;
  remoteAudioReceived: boolean;
  videoTrackReadyState: string;
  videoTrackMuted: boolean;
  srcObjectAttached: boolean;
  videoElementWidth: number;
  videoElementHeight: number;
  videoPlayStatus: "idle" | "playing" | "paused" | "failed";
  lastError: string | null;
  wsConnected: boolean;
  activeTracksCount: number;
  participantIdentity: string | null;
}

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

  const [diagnostics, setDiagnostics] = useState<LiveAvatarDiagnostics>({
    tokenStatus: "idle",
    sessionStatus: "idle",
    webrtcConnectionState: "disconnected",
    iceConnectionState: "new",
    remoteVideoReceived: false,
    remoteAudioReceived: false,
    videoTrackReadyState: "none",
    videoTrackMuted: false,
    srcObjectAttached: false,
    videoElementWidth: 0,
    videoElementHeight: 0,
    videoPlayStatus: "idle",
    lastError: null,
    wsConnected: false,
    activeTracksCount: 0,
    participantIdentity: null,
  });

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const sessionRef = useRef<any>(null);
  const connectingPromiseRef = useRef<Promise<boolean> | null>(null);
  const streamReadyRef = useRef<boolean>(false);
  const cachedTokenRef = useRef<string | null>(null);
  const currentEventIdRef = useRef<string | null>(null);

  // Direct WebRTC track references to bypass SDK participant ID filter bugs
  const remoteVideoTrackRef = useRef<any>(null);
  const remoteAudioTrackRef = useRef<any>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);

  // Safely attach remote tracks and stream to whatever video element is currently mounted
  const bindStreamToElement = useCallback((node: HTMLVideoElement) => {
    if (!node) return;

    try {
      node.playsInline = true;
      node.autoplay = true;

      // 1. Direct LiveKit track attachment
      if (remoteVideoTrackRef.current && typeof remoteVideoTrackRef.current.attach === "function") {
        try {
          remoteVideoTrackRef.current.attach(node);
        } catch (e) {
          console.warn("[LiveAvatar] Video track direct attach notice:", e);
        }
      }

      if (remoteAudioTrackRef.current && typeof remoteAudioTrackRef.current.attach === "function") {
        try {
          remoteAudioTrackRef.current.attach(node);
        } catch (e) {
          console.warn("[LiveAvatar] Audio track direct attach notice:", e);
        }
      }

      // 2. Ensure MediaStream is assigned to srcObject
      if (mediaStreamRef.current && mediaStreamRef.current.getTracks().length > 0) {
        if (node.srcObject !== mediaStreamRef.current) {
          node.srcObject = mediaStreamRef.current;
        }
      }

      // 3. Trigger playback
      node
        .play()
        .then(() => {
          setDiagnostics((d) => ({
            ...d,
            videoPlayStatus: "playing",
            srcObjectAttached: !!node.srcObject,
            videoElementWidth: node.videoWidth,
            videoElementHeight: node.videoHeight,
          }));
          if (node.videoWidth > 0) {
            setHasActiveStream(true);
          }
        })
        .catch((playErr) => {
          console.log("[LiveAvatar] Auto-play caught (will resume on candidate interaction):", playErr);
          setDiagnostics((d) => ({
            ...d,
            videoPlayStatus: "paused",
            lastError: playErr instanceof Error ? playErr.message : String(playErr),
          }));
        });
    } catch (err) {
      console.warn("[LiveAvatar] bindStreamToElement error:", err);
    }
  }, []);

  // Dynamic attach callback to support video elements mounted at any time (hero or compact)
  const attachVideo = useCallback(
    (node: HTMLVideoElement | null) => {
      videoRef.current = node;
      if (!node) {
        setDiagnostics((d) => ({ ...d, srcObjectAttached: false }));
        return;
      }

      node.playsInline = true;
      node.autoplay = true;

      node.onloadedmetadata = () => {
        setDiagnostics((d) => ({
          ...d,
          videoElementWidth: node.videoWidth,
          videoElementHeight: node.videoHeight,
          srcObjectAttached: !!node.srcObject,
        }));
        if (node.videoWidth > 0) {
          setHasActiveStream(true);
        }
      };

      node.onplaying = () => {
        setDiagnostics((d) => ({
          ...d,
          videoPlayStatus: "playing",
          videoElementWidth: node.videoWidth,
          videoElementHeight: node.videoHeight,
          srcObjectAttached: !!node.srcObject,
        }));
        setHasActiveStream(true);
      };

      node.onpause = () => {
        setDiagnostics((d) => ({ ...d, videoPlayStatus: "paused" }));
      };

      node.onerror = () => {
        setDiagnostics((d) => ({
          ...d,
          videoPlayStatus: "failed",
          lastError: "Video element playback error",
        }));
      };

      // If tracks are already subscribed from an active session, bind immediately
      if (remoteVideoTrackRef.current || (mediaStreamRef.current && mediaStreamRef.current.getTracks().length > 0)) {
        bindStreamToElement(node);
      }
    },
    [bindStreamToElement]
  );

  // Check backend credentials status on mount
  useEffect(() => {
    let isMounted = true;
    async function checkStatus() {
      setDiagnostics((d) => ({ ...d, tokenStatus: "requesting" }));
      try {
        const tokenRes: AvatarTokenResponse = await getAvatarSessionToken();
        if (!isMounted) return;
        if (tokenRes.available && tokenRes.token) {
          setIsConfigured(true);
          cachedTokenRef.current = tokenRes.token;
          setAvatarId(tokenRes.avatar_id || null);
          setStatusMessage("HeyGen LiveAvatar Lite configured.");
          setDiagnostics((d) => ({
            ...d,
            tokenStatus: "available",
          }));
        } else {
          setIsConfigured(false);
          setStatusMessage(tokenRes.message || "HeyGen credentials not configured in .env");
          setDiagnostics((d) => ({
            ...d,
            tokenStatus: "unconfigured",
            lastError: tokenRes.message || "Unconfigured",
          }));
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        setIsConfigured(false);
        const msg = err instanceof Error ? err.message : String(err);
        setStatusMessage("Failed to reach avatar credentials endpoint.");
        setDiagnostics((d) => ({
          ...d,
          tokenStatus: "error",
          lastError: msg,
        }));
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

  // Exit listening state prior to articulating speech
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

  // Connect to HeyGen LiveAvatar WebRTC session safely
  const connect = useCallback(async (): Promise<boolean> => {
    // If already connected and streaming, return success immediately
    if (sessionRef.current && (state === "CONNECTED" || state === "SPEAKING") && hasActiveStream) {
      return true;
    }

    // If connection is already in flight, reuse the same active promise
    if (connectingPromiseRef.current) {
      return connectingPromiseRef.current;
    }

    const connectionPromise = (async (): Promise<boolean> => {
      setState("CONNECTING");
      setStatusMessage("Connecting interviewer live video...");
      setDiagnostics((d) => ({
        ...d,
        sessionStatus: "connecting",
        lastError: null,
      }));

      try {
        // Reuse cached token or fetch fresh token
        let token = cachedTokenRef.current;
        if (!token) {
          setDiagnostics((d) => ({ ...d, tokenStatus: "requesting" }));
          const tokenRes = await getAvatarSessionToken();
          if (!tokenRes.available || !tokenRes.token) {
            setState("ERROR");
            setStatusMessage(tokenRes.message || "HeyGen credentials not configured in .env");
            setDiagnostics((d) => ({
              ...d,
              tokenStatus: "unconfigured",
              sessionStatus: "error",
              lastError: tokenRes.message || "Missing credentials",
            }));
            return false;
          }
          token = tokenRes.token;
          cachedTokenRef.current = token;
          setAvatarId(tokenRes.avatar_id || null);
          setDiagnostics((d) => ({ ...d, tokenStatus: "available" }));
        }

        // Dynamically load @heygen/liveavatar-web-sdk in browser client
        const { LiveAvatarSession, SessionEvent, AgentEventsEnum } = await import(
          "@heygen/liveavatar-web-sdk"
        );

        const session = new LiveAvatarSession(token, {
          autoKeepAlive: true,
        });

        sessionRef.current = session;

        // Initialize clean MediaStream for tracks
        const stream = new MediaStream();
        mediaStreamRef.current = stream;

        // Extract internal LiveKit Room directly
        const room = (session as any).room;
        if (room) {
          room.on("connectionStateChanged", (connState: string) => {
            setDiagnostics((d) => ({
              ...d,
              webrtcConnectionState: String(connState),
            }));
          });

          // Intercept TrackSubscribed for all participants
          room.on("trackSubscribed", (track: any, _pub: any, participant: any) => {
            const pId = participant?.identity || "unknown";
            setDiagnostics((d) => ({
              ...d,
              participantIdentity: pId,
            }));

            if (track.kind === "video") {
              remoteVideoTrackRef.current = track;
              (session as any)._remoteVideoTrack = track;

              if (track.mediaStreamTrack) {
                stream.addTrack(track.mediaStreamTrack);
                setDiagnostics((d) => ({
                  ...d,
                  remoteVideoReceived: true,
                  videoTrackReadyState: track.mediaStreamTrack.readyState,
                  videoTrackMuted: track.mediaStreamTrack.muted,
                  activeTracksCount: stream.getTracks().length,
                }));
              }

              streamReadyRef.current = true;
              setHasActiveStream(true);
              setState("CONNECTED");

              if (videoRef.current) {
                bindStreamToElement(videoRef.current);
              }
            } else if (track.kind === "audio") {
              remoteAudioTrackRef.current = track;
              (session as any)._remoteAudioTrack = track;

              if (track.mediaStreamTrack) {
                stream.addTrack(track.mediaStreamTrack);
                setDiagnostics((d) => ({
                  ...d,
                  remoteAudioReceived: true,
                  activeTracksCount: stream.getTracks().length,
                }));
              }

              if (videoRef.current) {
                bindStreamToElement(videoRef.current);
              }
            }
          });

          room.on("trackUnsubscribed", (track: any) => {
            if (track.mediaStreamTrack && stream) {
              stream.removeTrack(track.mediaStreamTrack);
            }
            if (track.kind === "video") {
              remoteVideoTrackRef.current = null;
              setDiagnostics((d) => ({
                ...d,
                remoteVideoReceived: false,
                activeTracksCount: stream.getTracks().length,
              }));
            } else if (track.kind === "audio") {
              remoteAudioTrackRef.current = null;
              setDiagnostics((d) => ({
                ...d,
                remoteAudioReceived: false,
                activeTracksCount: stream.getTracks().length,
              }));
            }
          });
        }

        // Standard SDK session stream ready event
        session.on(SessionEvent.SESSION_STREAM_READY, () => {
          streamReadyRef.current = true;
          setHasActiveStream(true);
          setState("CONNECTED");
          if (videoRef.current) {
            bindStreamToElement(videoRef.current);
          }
        });

        // Speech turn-taking events
        session.on(AgentEventsEnum.AVATAR_SPEAK_STARTED, () => {
          setState("SPEAKING");
          onSpeechStart?.();
        });

        session.on(AgentEventsEnum.AVATAR_SPEAK_ENDED, () => {
          setState("CONNECTED");
          startListening();
          onSpeechEnd?.();
        });

        session.on(SessionEvent.SESSION_DISCONNECTED, (_reason: any) => {
          setState("IDLE");
          setHasActiveStream(false);
          streamReadyRef.current = false;
          sessionRef.current = null;
          setDiagnostics((d) => ({
            ...d,
            sessionStatus: "disconnected",
            webrtcConnectionState: "disconnected",
            srcObjectAttached: false,
          }));
        });

        // Start the WebRTC session with safe error interception
        try {
          await session.start();
        } catch (startErr: unknown) {
          const errMsg = startErr instanceof Error ? startErr.message : String(startErr);
          console.warn("[LiveAvatar] session.start failed:", errMsg);
          setState("ERROR");
          setStatusMessage(
            errMsg.toLowerCase().includes("credit")
              ? "LiveAvatar video credits unavailable. Using Neural Voice interviewer."
              : `LiveAvatar notice: ${errMsg}`
          );
          setDiagnostics((d) => ({
            ...d,
            sessionStatus: "error",
            lastError: errMsg,
          }));
          sessionRef.current = null;
          onError?.(errMsg);
          return false;
        }

        setDiagnostics((d) => ({
          ...d,
          sessionStatus: "connected",
        }));

        if (videoRef.current) {
          bindStreamToElement(videoRef.current);
        }

        // Monitor WebSocket events
        const socket = (session as any)._sessionEventSocket as WebSocket | undefined;
        if (socket) {
          setDiagnostics((d) => ({ ...d, wsConnected: socket.readyState === WebSocket.OPEN }));
          socket.addEventListener("open", () => {
            setDiagnostics((d) => ({ ...d, wsConnected: true }));
          });
          socket.addEventListener("error", (ev) => {
            console.warn("[LiveAvatar WebSocket Error]:", ev);
            setDiagnostics((d) => ({ ...d, lastError: "WebSocket communication error" }));
          });
          socket.addEventListener("close", (ev) => {
            setDiagnostics((d) => ({ ...d, wsConnected: false }));
          });
        }

        setState("CONNECTED");
        setStatusMessage("Interviewer video connected.");

        // Start in attentive listening mode
        setTimeout(() => {
          startListening();
        }, 200);

        return true;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        console.warn("[LiveAvatar] Connection error:", msg);
        setState("ERROR");
        setStatusMessage(
          msg.toLowerCase().includes("credit")
            ? "LiveAvatar video credits unavailable. Using Neural Voice interviewer."
            : `LiveAvatar offline: ${msg}`
        );
        setDiagnostics((d) => ({
          ...d,
          sessionStatus: "error",
          lastError: msg,
        }));
        sessionRef.current = null;
        onError?.(msg);
        return false;
      }
    })();

    connectingPromiseRef.current = connectionPromise;
    try {
      return await connectionPromise;
    } finally {
      connectingPromiseRef.current = null;
    }
  }, [state, hasActiveStream, onSpeechStart, onSpeechEnd, onError, startListening, bindStreamToElement]);

  // Speak a question generated by Zaira's LLM via direct PCM 24k base64 chunks
  const speakText = useCallback(
    async (text: string): Promise<boolean> => {
      if (!text || !text.trim()) return false;

      // 1. Fetch PCM 24k 16-bit mono base64 chunks from Zaira backend
      const pcmData: PcmAudioResponse | null = await fetchQuestionPcmAudio(text);
      if (!pcmData || !pcmData.chunks || pcmData.chunks.length === 0) {
        console.warn("[LiveAvatar] PCM speech audio could not be synthesized.");
        return false;
      }

      // 2. Ensure LiveAvatar session is genuinely connected
      if (!sessionRef.current || (state !== "CONNECTED" && state !== "SPEAKING")) {
        const ok = await connect();
        if (!ok || !sessionRef.current) {
          return false;
        }
      }

      const session = sessionRef.current;
      const socket = (session as any)._sessionEventSocket as WebSocket | undefined;

      if (!socket || socket.readyState !== WebSocket.OPEN) {
        console.warn("[LiveAvatar] WebSocket not open for speech streaming.");
        return false;
      }

      // 3. Exit listening state prior to articulating speech
      stopListening();

      // 4. Send chunks directly through the session WebSocket (bypasses SDK repeatAudio base64-slicing bug)
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
        onSpeechStart?.();
        return true;
      } catch (err: unknown) {
        console.warn("[LiveAvatar] Error streaming speech chunks to LiveAvatar:", err);
        return false;
      }
    },
    [connect, state, stopListening, onSpeechStart]
  );

  // Gracefully stop session and release WebRTC tracks
  const disconnect = useCallback(async () => {
    streamReadyRef.current = false;
    setHasActiveStream(false);
    remoteVideoTrackRef.current = null;
    remoteAudioTrackRef.current = null;
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    }
    if (sessionRef.current) {
      try {
        await sessionRef.current.stop();
      } catch {
        // ignore
      }
      sessionRef.current = null;
    }
    setState("IDLE");
    setDiagnostics((d) => ({
      ...d,
      sessionStatus: "disconnected",
      webrtcConnectionState: "disconnected",
      srcObjectAttached: false,
    }));
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      streamReadyRef.current = false;
      setHasActiveStream(false);
      if (sessionRef.current) {
        sessionRef.current.stop().catch(() => {});
      }
    };
  }, []);

  return {
    state,
    isConfigured,
    avatarId,
    statusMessage,
    hasActiveStream,
    diagnostics,
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
