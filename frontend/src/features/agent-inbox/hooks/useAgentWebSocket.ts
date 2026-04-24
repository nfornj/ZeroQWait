import { useCallback, useEffect, useState } from "react";

import type { AgentFeedEvent } from "../types";
import { nowIso, toId } from "../agentInboxShared";

const buildWebSocketUrl = (shopId: number): string => {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}/api/ws/${shopId}`;
};

type FeedEventInput = Omit<AgentFeedEvent, "id" | "timestamp">;

export const useAgentWebSocket = (shopId?: number) => {
  const [feedEvents, setFeedEvents] = useState<AgentFeedEvent[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<"idle" | "connecting" | "connected" | "disconnected">(
    "idle",
  );

  const addFeedEvent = useCallback((event: FeedEventInput) => {
    setFeedEvents((prev) => [
      {
        id: toId("feed"),
        timestamp: nowIso(),
        ...event,
      },
      ...prev,
    ]);
  }, []);

  useEffect(() => {
    setFeedEvents([]);

    if (!shopId) {
      setConnectionStatus("idle");
      return;
    }

    setConnectionStatus("connecting");
    const socket = new WebSocket(buildWebSocketUrl(shopId));
    let connected = false;

    socket.onopen = () => {
      connected = true;
      setConnectionStatus("connected");
      addFeedEvent({
        type: "system",
        title: "Feed connected",
        description: "Real-time shop updates are active.",
      });
    };

    socket.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        const queueSize = Array.isArray(parsed.queue_items) ? parsed.queue_items.length : undefined;
        addFeedEvent({
          type: "queue_update",
          title: "Shop live snapshot",
          description:
            typeof queueSize === "number"
              ? `Current active queue size: ${queueSize}`
              : "Received a real-time queue update.",
          payload: parsed,
        });
      } catch {
        addFeedEvent({
          type: "system",
          title: "WebSocket update",
          description: String(event.data),
        });
      }
    };

    socket.onerror = () => {
      setConnectionStatus((prev) => (prev === "connected" ? prev : "disconnected"));
    };

    socket.onclose = () => {
      setConnectionStatus("disconnected");
      if (connected) {
        addFeedEvent({
          type: "system",
          title: "Feed disconnected",
          description: "WebSocket connection closed.",
        });
      }
    };

    return () => {
      socket.close();
    };
  }, [addFeedEvent, shopId]);

  return { feedEvents, addFeedEvent, connectionStatus };
};

export default useAgentWebSocket;