/**
 * Speech synthesis utility for TruthLens AI Interviewer.
 * Uses the browser's native SpeechSynthesis API to speak questions aloud
 * with a preferred female-sounding voice, with fallback to default English.
 * 
 * Handles asynchronous voice loading, browser autoplay policies,
 * utterance garbage collection protection, stale callback prevention,
 * and speech lifecycle events.
 */

export function selectFemaleVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  if (!voices || voices.length === 0) return null;

  const englishVoices = voices.filter((v) => v.lang && v.lang.toLowerCase().startsWith("en"));
  const pool = englishVoices.length > 0 ? englishVoices : voices;

  const femaleKeywords = [
    "female", "woman",
    "samantha", "victoria", "karen", "zira", "moira", "fiona", "tessa",
    "siri", "ava", "allison", "susan", "veena", "kate", "serena", "stephanie",
    "jenny", "aria", "sonia", "libby", "natasha", "hazel"
  ];

  for (const kw of femaleKeywords) {
    const match = pool.find((v) => v.name && v.name.toLowerCase().includes(kw));
    if (match) return match;
  }

  // Fallback to default English voice or first English voice
  const defaultEnglish = englishVoices.find((v) => v.default) || englishVoices[0];
  if (defaultEnglish) return defaultEnglish;

  // Fallback to default voice or first available
  return voices.find((v) => v.default) || voices[0] || null;
}

// Module-level reference to prevent garbage collection of active utterance in Chromium
let activeUtteranceHolder: SpeechSynthesisUtterance | null = null;

export function getActiveUtterance(): SpeechSynthesisUtterance | null {
  return activeUtteranceHolder;
}

export class QuestionSpeaker {
  private currentUtterance: SpeechSynthesisUtterance | null = null;
  private voices: SpeechSynthesisVoice[] = [];
  private isBrowserSupported: boolean = false;
  private watchdogTimer: ReturnType<typeof setTimeout> | null = null;
  private activeUtteranceId: number = 0;

  constructor() {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      this.isBrowserSupported = true;
      this.initVoices();
    }
  }

  private initVoices() {
    if (!this.isBrowserSupported) return;
    this.voices = window.speechSynthesis.getVoices();
    
    // Bind both event listener and property for cross-browser reliability
    const onVoicesChanged = () => {
      this.voices = window.speechSynthesis.getVoices();
    };

    if (typeof window.speechSynthesis.addEventListener === "function") {
      window.speechSynthesis.addEventListener("voiceschanged", onVoicesChanged);
    }
    window.speechSynthesis.onvoiceschanged = onVoicesChanged;
  }

  public isAvailable(): boolean {
    return this.isBrowserSupported;
  }

  public isSpeaking(): boolean {
    return this.currentUtterance !== null || activeUtteranceHolder !== null;
  }

  public getPreferredVoice(): SpeechSynthesisVoice | null {
    if (!this.isBrowserSupported) return null;
    if (this.voices.length === 0) {
      this.voices = window.speechSynthesis.getVoices();
    }
    return selectFemaleVoice(this.voices);
  }

  public speak(
    text: string,
    onStart?: () => void,
    onEnd?: () => void,
    onError?: (err: unknown) => void,
    onBoundary?: (charIndex: number, charLength: number, word: string) => void
  ): boolean {
    if (!this.isBrowserSupported) {
      onError?.(new Error("Speech synthesis not supported in this browser"));
      return false;
    }

    if (!text || text.trim() === "") {
      onError?.(new Error("Empty question text"));
      return false;
    }

    // Cancel any active speech and increment generation to discard stale callbacks
    this.stop();

    const utteranceId = ++this.activeUtteranceId;
    let hasStarted = false;
    let hasTerminated = false;

    // Safety watchdog: Detect failure to START speaking within 3500ms
    // If onstart fires, the watchdog is immediately cancelled.
    // This strictly catches browser autoplay blocking or hung engine queues without prematurely stopping playback.
    this.watchdogTimer = setTimeout(() => {
      if (this.activeUtteranceId !== utteranceId || hasTerminated) return;
      if (!hasStarted) {
        hasTerminated = true;
        this.stop();
        console.warn("Speech synthesis watchdog: audio playback failed to start within 3.5s (likely browser autoplay policy).");
        onError?.(new Error("Speech synthesis playback failed to start within 3500ms"));
      }
    }, 3500);

    try {
      // Resume if browser audio synthesis was paused
      if (window.speechSynthesis.paused) {
        window.speechSynthesis.resume();
      }

      const utterance = new SpeechSynthesisUtterance(text);
      const voice = this.getPreferredVoice();
      if (voice) {
        utterance.voice = voice;
      }
      utterance.lang = voice?.lang || "en-US";
      utterance.rate = 0.95; // Slightly measured, clear interviewer cadence
      utterance.pitch = 1.02;

      utterance.onstart = () => {
        // Discard event if this utterance was already cancelled or superseded
        if (this.activeUtteranceId !== utteranceId || hasTerminated) return;
        hasStarted = true;
        if (this.watchdogTimer) {
          clearTimeout(this.watchdogTimer);
          this.watchdogTimer = null;
        }
        onStart?.();
      };

      utterance.onboundary = (e: SpeechSynthesisEvent) => {
        if (this.activeUtteranceId !== utteranceId || hasTerminated) return;
        const charLength = e.charLength || 4;
        const word = text.slice(e.charIndex, e.charIndex + charLength);
        onBoundary?.(e.charIndex, charLength, word);
      };

      utterance.onend = () => {
        // Discard event if this utterance was already cancelled or superseded
        if (this.activeUtteranceId !== utteranceId || hasTerminated) return;
        hasTerminated = true;
        if (this.watchdogTimer) {
          clearTimeout(this.watchdogTimer);
          this.watchdogTimer = null;
        }
        this.currentUtterance = null;
        activeUtteranceHolder = null;
        onEnd?.();
      };

      utterance.onerror = (e) => {
        // Discard event if this utterance was already cancelled or superseded
        if (this.activeUtteranceId !== utteranceId || hasTerminated) return;
        hasTerminated = true;
        if (this.watchdogTimer) {
          clearTimeout(this.watchdogTimer);
          this.watchdogTimer = null;
        }
        this.currentUtterance = null;
        activeUtteranceHolder = null;

        // If error was caused by intentional user cancellation / interruption, do not trigger error fallback
        if (e.error === "interrupted" || e.error === "canceled") {
          return;
        }
        console.warn("Speech synthesis utterance error:", e);
        onError?.(e);
      };

      this.currentUtterance = utterance;
      activeUtteranceHolder = utterance;

      window.speechSynthesis.speak(utterance);
      return true;
    } catch (err) {
      if (this.watchdogTimer) {
        clearTimeout(this.watchdogTimer);
        this.watchdogTimer = null;
      }
      console.warn("Failed to invoke speech synthesis speak:", err);
      onError?.(err);
      return false;
    }
  }

  public stop(): void {
    // Invalidate active utterance ID so any subsequent async callbacks from cancelled speech are discarded
    this.activeUtteranceId++;

    if (this.watchdogTimer) {
      clearTimeout(this.watchdogTimer);
      this.watchdogTimer = null;
    }
    if (this.currentUtterance) {
      // Detach listeners to prevent stale closures from running when cancel() fires
      this.currentUtterance.onstart = null;
      this.currentUtterance.onboundary = null;
      this.currentUtterance.onend = null;
      this.currentUtterance.onerror = null;
    }
    if (this.isBrowserSupported && typeof window !== "undefined" && window.speechSynthesis) {
      try {
        window.speechSynthesis.cancel();
      } catch (err) {
        console.warn("Speech synthesis cancel warning:", err);
      }
    }
    this.currentUtterance = null;
    activeUtteranceHolder = null;
  }
}
