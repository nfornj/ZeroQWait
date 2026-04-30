import { useCallback, useEffect, useRef, useState } from "react";

import {
  buildStreamToolResultFeedEvent,
  buildStreamToolResultInsight,
} from "../approvalOutcome";
import { nowIso, normalizePendingApproval, toId } from "../agentInboxShared";
import type { AgentChatSendPayload } from "../AgentChat";
import type { AgentFeedEvent, ChatMessage, InsightItem, PendingApproval, ThinkingStep } from "../types";

const apiBaseUrl = process.env.REACT_APP_API_URL || "/api";

const STREAM_INTERRUPTED_MESSAGE = "The response stream was interrupted before completion. Partial output may be shown below.";
const STREAM_RETRY_MESSAGE = "The response was interrupted before it finished. Please try again.";

const normalizeStreamErrorDetail = (error: unknown, fallback: string) => {
  const detail = typeof error === "string" ? error.trim() : error instanceof Error ? error.message.trim() : fallback;
  const lowered = detail.toLowerCase();

  if (
    lowered.includes("error in input stream") ||
    lowered.includes("failed to fetch") ||
    lowered.includes("networkerror") ||
    lowered.includes("body stream")
  ) {
    return STREAM_INTERRUPTED_MESSAGE;
  }

  return detail || fallback;
};

type FeedEventInput = Omit<AgentFeedEvent, "id" | "timestamp">;

interface UseAgentStreamOptions {
  shopId?: number;
  addFeedEvent: (event: FeedEventInput) => void;
  addPendingApproval: (approval: PendingApproval) => void;
  prependInsightItem: (item: InsightItem) => void;
  refreshPendingApprovals: () => Promise<void>;
  refreshBriefing: () => Promise<void>;
}

export const useAgentStream = ({
  shopId,
  addFeedEvent,
  addPendingApproval,
  prependInsightItem,
  refreshPendingApprovals,
  refreshBriefing,
}: UseAgentStreamOptions) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  // ─── Voice / TTS state ────────────────────────────────────────────────────
  const [isVoiceEnabled, setIsVoiceEnabled] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);

  // Refs so audio callbacks always read the latest values without stale closures.
  const isVoiceEnabledRef = useRef(false);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const currentAudioSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const audioQueueRef = useRef<ArrayBuffer[]>([]);
  const isPlayingAudioRef = useRef(false);
  const cancelAudioRef = useRef(false);
  const ttsSentenceBufferRef = useRef("");

  useEffect(() => {
    isVoiceEnabledRef.current = isVoiceEnabled;
  }, [isVoiceEnabled]);

  const getAudioCtx = useCallback(() => {
    if (!audioCtxRef.current || audioCtxRef.current.state === "closed") {
      audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    }
    return audioCtxRef.current;
  }, []);

  const stopVoice = useCallback(() => {
    cancelAudioRef.current = true;
    audioQueueRef.current = [];
    isPlayingAudioRef.current = false;
    try {
      currentAudioSourceRef.current?.stop();
      currentAudioSourceRef.current = null;
    } catch {}
    setIsSpeaking(false);
  }, []);

  const drainAudioQueue = useCallback(async () => {
    if (isPlayingAudioRef.current) return;
    isPlayingAudioRef.current = true;
    cancelAudioRef.current = false;

    while (audioQueueRef.current.length > 0) {
      if (cancelAudioRef.current) break;
      const arrayBuffer = audioQueueRef.current.shift()!;
      try {
        const ctx = getAudioCtx();
        if (ctx.state === "suspended") await ctx.resume();
        const decoded = await ctx.decodeAudioData(arrayBuffer.slice(0));
        await new Promise<void>((resolve) => {
          if (cancelAudioRef.current) { resolve(); return; }
          const src = ctx.createBufferSource();
          src.buffer = decoded;
          src.connect(ctx.destination);
          currentAudioSourceRef.current = src;
          setIsSpeaking(true);
          src.onended = () => {
            currentAudioSourceRef.current = null;
            resolve();
          };
          src.start(0);
        });
      } catch {
        // skip undecodable chunk
      }
    }
    isPlayingAudioRef.current = false;
    if (!cancelAudioRef.current) setIsSpeaking(false);
  }, [getAudioCtx]);

  const speakSentence = useCallback(async (sentence: string) => {
    const clean = sentence.trim();
    if (!clean || clean.length < 2) return;
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${apiBaseUrl}/voice/tts`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ text: clean, voice: "female", speed: 1.0 }),
      });
      if (!res.ok) return;
      const ab = await res.arrayBuffer();
      audioQueueRef.current.push(ab);
      if (!isPlayingAudioRef.current) drainAudioQueue();
    } catch {
      // TTS failure is non-fatal
    }
  }, [drainAudioQueue]);

  const toggleVoice = useCallback(() => {
    setIsVoiceEnabled((prev) => {
      if (prev) stopVoice();
      return !prev;
    });
  }, [stopVoice]);
  // ─────────────────────────────────────────────────────────────────────────

  useEffect(() => {
    setIsStreaming(messages.some((message) => message.status === "sending" || message.status === "streaming"));
  }, [messages]);

  const appendSystemMessage = useCallback((content: string, agent?: string) => {
    setMessages((prev) => [
      ...prev,
      {
        id: toId("msg_system"),
        role: "system",
        content,
        status: "done",
        timestamp: nowIso(),
        agent,
      },
    ]);
  }, []);

  const processStreamEvent = useCallback(
    (event: Record<string, any>, assistantMessageId?: string) => {
      const eventType = String(event.type || "");

      if (eventType === "text") {
        const content = String(event.content || "");
        if (!assistantMessageId || !content) return;

        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantMessageId
              ? {
                  ...message,
                  content: `${message.content}${content}`,
                  status: "streaming",
                }
              : message,
          ),
        );
        return;
      }

      if (eventType === "approval_required") {
        const approval = normalizePendingApproval((event.details || event) as Record<string, any>, shopId || 0);
        addPendingApproval(approval);
        addFeedEvent({
          type: "approval_required",
          title: "Approval required",
          description: `Action '${approval.action}' is waiting for your decision.`,
          payload: approval,
        });
        return;
      }

      if (eventType === "agent_switch") {
        addFeedEvent({
          type: "agent_switch",
          title: "Agent switched",
          description: `Supervisor delegated to ${String(event.agent || "sub-agent")}.`,
          payload: event,
        });
        return;
      }

      if (eventType === "tool_call") {
        addFeedEvent({
          type: "tool_call",
          title: `Tool call: ${String(event.tool || "unknown")}`,
          description: "Tool execution started.",
          payload: event,
        });
        if (assistantMessageId) {
          const newStep: ThinkingStep = {
            id: `tool-${String(event.tool || "unknown")}-${Date.now()}`,
            label: `Calling ${String(event.tool || "unknown")}...`,
            status: "active",
          };
          setMessages((prev) =>
            prev.map((message) =>
              message.id === assistantMessageId
                ? {
                    ...message,
                    thinkingSteps: [
                      ...(message.thinkingSteps || []).map((step) =>
                        step.status === "active" ? { ...step, status: "completed" as const } : step,
                      ),
                      newStep,
                    ],
                    thinkingComplete: false,
                  }
                : message,
            ),
          );
        }
        return;
      }

      if (eventType === "tool_result") {
        const eventTimestamp = String(event.timestamp || nowIso());
        const outcomeEvent = buildStreamToolResultFeedEvent(
          {
            tool: event.tool,
            result: event.result,
            agent: event.agent,
          },
          eventTimestamp,
        );

        if (outcomeEvent) {
          addFeedEvent({
            type: outcomeEvent.type,
            title: outcomeEvent.title,
            description: outcomeEvent.description,
            payload: outcomeEvent.payload,
          });
        } else {
          addFeedEvent({
            type: "tool_result",
            title: `Tool result: ${String(event.tool || "unknown")}`,
            description: "Tool execution completed.",
            payload: event,
          });
        }

        const outcomeInsight = buildStreamToolResultInsight(
          {
            tool: event.tool,
            result: event.result,
            agent: event.agent,
          },
          eventTimestamp,
        );
        if (outcomeInsight) {
          prependInsightItem(outcomeInsight);
        }

        if (assistantMessageId) {
          setMessages((prev) =>
            prev.map((message) =>
              message.id === assistantMessageId
                ? {
                    ...message,
                    thinkingSteps: (message.thinkingSteps || []).map((step) =>
                      step.label === `Calling ${String(event.tool || "unknown")}...`
                        ? { ...step, status: event.error ? ("error" as const) : ("completed" as const) }
                        : step,
                    ),
                  }
                : message,
            ),
          );
        }
        return;
      }

      if (eventType === "chart" && event._parsed_chart) {
        const chart = event._parsed_chart;
        prependInsightItem({ id: chart.id, type: "chart", chart, timestamp: chart.timestamp });
        return;
      }

      if (eventType === "file" && event._parsed_file) {
        const file = event._parsed_file;
        prependInsightItem({ id: file.id, type: "file", file, timestamp: file.timestamp });
      }
    },
    [addFeedEvent, addPendingApproval, prependInsightItem, shopId],
  );

  const handleSend = useCallback(
    async ({ text: messageText, attachments }: AgentChatSendPayload) => {
      if (!shopId) {
        setError("No active shop selected for agent inbox");
        return;
      }

      setError(null);

      const userMessage: ChatMessage = {
        id: toId("msg_user"),
        role: "user",
        content: messageText,
        status: "done",
        timestamp: nowIso(),
        attachments: attachments && attachments.length > 0 ? attachments : undefined,
      };
      const assistantMessageId = toId("msg_assistant");
      const assistantPlaceholder: ChatMessage = {
        id: assistantMessageId,
        role: "assistant",
        content: "",
        status: "streaming",
        retryMessage: messageText,
        timestamp: nowIso(),
        thinkingSteps: [],
        thinkingComplete: false,
      };

      setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
      addFeedEvent({
        type: "chat",
        title: "Owner message sent",
        description: messageText,
      });

      // Reset TTS sentence buffer for this response
      ttsSentenceBufferRef.current = "";
      if (isVoiceEnabledRef.current) stopVoice();

      let streamEndedWithDone = false;
      let streamTerminalStatus: "completed" | "error" | null = null;
      let streamErrorDetail: string | null = null;
      let sawRenderableAssistantContent = false;

      try {
        const token = localStorage.getItem("token");
        const response = await fetch(`${apiBaseUrl}/v2/agent/chat/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            message: messageText,
            shop_id: shopId,
            is_voice: isVoiceEnabledRef.current,
            attachments:
              attachments && attachments.length > 0
                ? attachments.map((a) => {
                    const dataContent = (a.content ?? []).find(
                      (c) => c.type === "data" && (c as { name?: string }).name === "attachment",
                    );
                    const data = dataContent
                      ? (dataContent as { data?: { filename?: string; contentType?: string; textContent?: string } }).data ?? {}
                      : {};
                    return {
                      filename: data.filename ?? (a as { name?: string }).name ?? "",
                      content_type: data.contentType ?? "",
                      text_content: data.textContent ?? "",
                    };
                  })
                : undefined,
          }),
        });

        if (!response.ok || !response.body) {
          throw new Error(`Streaming request failed with status ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data:")) continue;

            const payload = trimmed.slice(5).trim();
            if (payload === "[DONE]") {
              // Flush any remaining TTS sentence buffer
              const remaining = ttsSentenceBufferRef.current.trim();
              if (isVoiceEnabledRef.current && remaining.length > 2) {
                speakSentence(remaining);
                ttsSentenceBufferRef.current = "";
              }
              streamEndedWithDone = true;
              setMessages((prev) =>
                prev.map((message) =>
                  message.id === assistantMessageId
                    ? { ...message, status: "done", thinkingComplete: true }
                    : message,
                ),
              );
              continue;
            }

            try {
              const event = JSON.parse(payload);
              const eventType = String(event.type || "");

              if (eventType === "stream_status") {
                const status = String(event.status || "");
                if (status === "completed") {
                  streamTerminalStatus = "completed";
                  addFeedEvent({
                    type: "system",
                    title: "Stream completed",
                    description: `Supervisor response completed via ${String(event.agent || "supervisor")}.`,
                    payload: event,
                  });
                } else if (status === "error") {
                  streamTerminalStatus = "error";
                  streamErrorDetail = normalizeStreamErrorDetail(event.message, STREAM_RETRY_MESSAGE);
                  setError(streamErrorDetail);
                  addFeedEvent({
                    type: "error",
                    title: "Stream error",
                    description: streamErrorDetail,
                    payload: event,
                  });
                }
                continue;
              }

              if (eventType === "error") {
                streamTerminalStatus = "error";
                streamErrorDetail = normalizeStreamErrorDetail(event.message, STREAM_RETRY_MESSAGE);
                setError(streamErrorDetail);
                addFeedEvent({
                  type: "error",
                  title: "Stream error",
                  description: streamErrorDetail,
                  payload: event,
                });
                continue;
              }

              if (eventType === "text" && String(event.content || "")) {
                sawRenderableAssistantContent = true;
                // Real-time TTS: buffer tokens into sentences
                if (isVoiceEnabledRef.current) {
                  ttsSentenceBufferRef.current += String(event.content || "");
                  // Split on sentence endings followed by whitespace
                  const parts = ttsSentenceBufferRef.current.split(/(?<=[.!?])\s+/);
                  if (parts.length > 1) {
                    const toSpeak = parts.slice(0, -1).join(" ");
                    ttsSentenceBufferRef.current = parts[parts.length - 1] || "";
                    if (toSpeak.trim().length > 2) speakSentence(toSpeak.trim());
                  }
                }
              }

              if (eventType === "chart" || eventType === "file") {
                sawRenderableAssistantContent = true;
              }

              processStreamEvent(event, assistantMessageId);
            } catch {
              continue;
            }
          }
        }

        await refreshPendingApprovals();
        await refreshBriefing();
      } catch (err: any) {
        const detail = normalizeStreamErrorDetail(err, STREAM_RETRY_MESSAGE);
        streamTerminalStatus = "error";
        streamErrorDetail = streamErrorDetail || detail;
        setError(detail);
        addFeedEvent({
          type: "error",
          title: "Chat stream failed",
          description: detail,
        });
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantMessageId
              ? { ...message, status: "error", thinkingComplete: true }
              : message,
          ),
        );
      } finally {
        if (!streamEndedWithDone && streamTerminalStatus === null) {
          streamTerminalStatus = "error";
          streamErrorDetail = sawRenderableAssistantContent ? STREAM_INTERRUPTED_MESSAGE : STREAM_RETRY_MESSAGE;
          setError(streamErrorDetail);
          addFeedEvent({
            type: "error",
            title: "Stream interrupted",
            description: streamErrorDetail,
            payload: { endedWithDone: false },
          });
        }

        setMessages((prev) => {
          const target = prev.find((message) => message.id === assistantMessageId);
          if (!target) return prev;

          const contentEmpty = !String(target.content || "").trim();
          if (streamTerminalStatus === "error") {
            return prev.map((message) =>
              message.id === assistantMessageId
                ? {
                    ...message,
                    content: contentEmpty ? (streamErrorDetail || STREAM_RETRY_MESSAGE) : message.content,
                    status: "error",
                  }
                : message,
            );
          }

          return prev.map((message) =>
            message.id === assistantMessageId && message.status !== "error"
              ? { ...message, status: "done", thinkingComplete: true }
              : message,
          );
        });
      }
    },
    [addFeedEvent, processStreamEvent, refreshBriefing, refreshPendingApprovals, shopId, speakSentence, stopVoice],
  );

  return {
    messages,
    setMessages,
    isStreaming,
    handleSend,
    error,
    setError,
    appendSystemMessage,
    isVoiceEnabled,
    isSpeaking,
    toggleVoice,
  };
};

export default useAgentStream;