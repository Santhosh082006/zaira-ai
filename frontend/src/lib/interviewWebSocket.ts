import { Question } from "./interviewApi";

export type WebSocketServerEventType = 
  | "connected"
  | "question_ready"
  | "processing"
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
  payload?: { stage?: string; progress?: number };
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

export type WebSocketServerEvent =
  | WSServerConnectedEvent
  | WSServerQuestionReadyEvent
  | WSServerProcessingEvent
  | WSServerAnswerResultEvent
  | WSServerInterviewCompletedEvent
  | WSServerErrorEvent
  | WSServerStateEvent
  | WSServerLiveFeedbackEvent;

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

export type WebSocketClientEventType = "submit_answer" | "get_state";

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

  constructor(
    sessionId: string, 
    onMessage: (event: WebSocketServerEvent) => void,
    onError: (error: string) => void,
    onClose: () => void
  ) {
    this.sessionId = sessionId;
    this.onMessage = onMessage;
    this.onError = onError;
    this.onClose = onClose;
  }

  public connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return; // Prevent duplicate connections
    }

    const host = typeof window !== "undefined" ? window.location.hostname || "127.0.0.1" : "127.0.0.1";
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || `ws://${host}:8000`;
    this.ws = new WebSocket(`${wsUrl}/ws/interview/${this.sessionId}`);

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
      this.onClose();
    };
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
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
