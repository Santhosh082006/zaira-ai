import { Question } from "./interviewApi";
import { getWsBase } from "./apiConfig";

export type WebSocketServerEventType = 
  | "connected"
  | "question_ready"
  | "processing"
  | "eval_stream_chunk"
  | "answer_result"
  | "interview_completed"
  | "error"
  | "state"
  | "live_feedback";

export interface WSServerLiveFeedbackEvent {
  type: "live_feedback";
  question_id: string;
  word_count: number;
  concepts_covered: string[];
  concepts_missing: string[];
  pacing_status: string;
  coaching_hint: string;
  is_provisional: boolean;
}

export interface WSServerConnectedEvent {
  type: "connected";
  session_id: string;
}

export interface WSServerQuestionReadyEvent {
  type: "question_ready";
  question: Question;
  payload?: { question?: Question };
}

export interface WSServerProcessingEvent {
  type: "processing";
  stage: string;
  progress: number;
  message?: string;
  payload?: { stage?: string; progress?: number; message?: string };
}

export interface WSServerEvalStreamChunkEvent {
  type: "eval_stream_chunk";
  stage: string;
  chunk: string;
  progress?: number;
  payload?: { stage?: string; chunk?: string; progress?: number };
}

export interface WSServerAnswerResultEvent {
  type: "answer_result";
  answer_id: string;
  question_id: string;
  next_question?: Question | null;
  decision: string;
  decision_reason: string;
  interview_progress: number;
  completion_status: string;
  payload?: {
    next_question?: Question | null;
    completion_status?: string;
    [key: string]: unknown;
  };
}

export interface WSServerInterviewCompletedEvent {
  type: "interview_completed";
  reason: string;
  payload?: { reason?: string };
}

export interface WSServerErrorEvent {
  type: "error";
  code: string;
  message: string;
  payload?: { code?: string; message?: string };
}

export interface WSServerStateEvent {
  type: "state";
  session_id: string;
  completion_status: string;
  current_question_id?: string | null;
  interview_progress: number;
  competency_coverage_status: Record<string, string>;
  payload?: Record<string, unknown>;
}

export interface WSServerPongEvent {
  type: "pong";
}

export type WebSocketServerEvent =
  | WSServerConnectedEvent
  | WSServerQuestionReadyEvent
  | WSServerProcessingEvent
  | WSServerEvalStreamChunkEvent
  | WSServerAnswerResultEvent
  | WSServerInterviewCompletedEvent
  | WSServerErrorEvent
  | WSServerStateEvent
  | WSServerLiveFeedbackEvent
  | WSServerPongEvent;

export interface WSClientSubmitAnswer {
  type: "submit_answer";
  question_id: string;
  transcript: string;
  duration?: number;
  media_reference?: string;
  speech_metrics?: Record<string, number>;
  language_metrics?: Record<string, number>;
  visual_metrics?: Record<string, number>;
  content_analysis?: Record<string, unknown>;
}

export type WebSocketClientEventType = "submit_answer" | "get_state" | "ping";

export interface WebSocketClientEvent {
  type: WebSocketClientEventType;
  payload: WSClientSubmitAnswer | Record<string, unknown>;
}

export class InterviewWebSocketClient {
  private ws: WebSocket | null = null;
  private sessionId: string;
  private onMessage: (event: WebSocketServerEvent) => void;
  private onError: (error: string) => void;
  private onClose: () => void;
  private onOpen?: () => void;

  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private intentionalClose = false;

  constructor(
    sessionId: string, 
    onMessage: (event: WebSocketServerEvent) => void,
    onError: (error: string) => void,
    onClose: () => void,
    onOpen?: () => void
  ) {
    this.sessionId = sessionId;
    this.onMessage = onMessage;
    this.onError = onError;
    this.onClose = onClose;
    this.onOpen = onOpen;
  }

  public connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return; // Prevent duplicate connections
    }

    this.intentionalClose = false;
    const wsUrl = getWsBase();
    this.ws = new WebSocket(`${wsUrl}/ws/interview/${this.sessionId}`);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.startHeartbeat();
      if (this.onOpen) {
        this.onOpen();
      }
    };

    this.ws.onmessage = (event) => {
      let parsed: WebSocketServerEvent;
      try {
        parsed = JSON.parse(event.data);
      } catch (err) {
        this.onError("Malformed server message: Invalid JSON");
        console.error("Failed to parse WS JSON", err, event.data);
        return;
      }

      try {
        if (!parsed || typeof parsed !== "object" || typeof parsed.type !== "string") {
          this.onError("Malformed server message: Missing event type");
          return;
        }

        // Handle pong heartbeat response
        if (parsed.type === "pong") {
          return;
        }

        this.onMessage(parsed);
      } catch (err) {
        console.error("Error in onMessage handler", err);
        this.onError(err instanceof Error ? err.message : "Error processing server message");
      }
    };

    this.ws.onerror = () => {
      this.onError("WebSocket connection error");
    };

    this.ws.onclose = () => {
      this.stopHeartbeat();
      this.onClose();

      // Attempt automatic reconnection if not intentionally disconnected
      if (!this.intentionalClose && this.reconnectAttempts < this.maxReconnectAttempts) {
        const backoffDelay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
        this.reconnectAttempts++;
        console.warn(`WebSocket disconnected. Reconnecting in ${backoffDelay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
        this.reconnectTimer = setTimeout(() => {
          this.connect();
        }, backoffDelay);
      }
    };
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify({ type: "ping" }));
        } catch {
          // Send failure will trigger onerror/onclose
        }
      }
    }, 30000);
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  public sendAnswer(answer: Omit<WSClientSubmitAnswer, "type">) {
    this.send({ type: "submit_answer", ...answer });
  }

  public sendLiveTranscriptUpdate(update: {
    question_id: string;
    transcript: string;
    duration?: number;
    is_final?: boolean;
  }) {
    this.send({ type: "live_transcript_update", ...update });
  }

  public getState() {
    this.send({ type: "get_state" });
  }

  private send(event: Record<string, any>) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(event));
    } else {
      this.onError("Cannot send message: WebSocket is not open");
    }
  }

  public disconnect() {
    this.intentionalClose = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
