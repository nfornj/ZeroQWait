import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import {
  Bot,
  Download,
  Loader2,
  MapPin,
  Mic,
  MicOff,
  Moon,
  Search,
  Send,
  Sun,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart as RechartsBarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart as RechartsLineChart,
  Pie,
  PieChart as RechartsPieChart,
  XAxis,
  YAxis,
} from "recharts";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useAudioRecorder } from "../../hooks/useAudioRecorder";
import { useAudioVisualizer } from "../../hooks/useAudioVisualizer";
import ParticleSphere from "../../components/agent/ParticleSphere";
import ThinkingSteps, { ThinkingStep } from "../../features/agent-inbox/ThinkingSteps";
import Pricing from "./Pricing";
import Features from "./Features";
import FAQ from "./FAQ";
import Testimonials from "./Testimonials";
import InlineRegistrationForm, { FormDoneData, FormStepData } from "./InlineRegistrationForm";
import InlineQueueJoinForm from "./InlineQueueJoinForm";
import InlineAppointmentForm from "./InlineAppointmentForm";
import InlinePaymentForm, { PaymentFormData } from "./InlinePaymentForm";
import InlineCheckoutCard, { CheckoutCardData } from "./InlineCheckoutCard";
import InlineFeedbackForm from "./InlineFeedbackForm";
import { constructShopUrl, isLocalhost } from "../../utils/domainUtils";
import { createAgentChartFromPayload, resolveAgentChart } from "../../features/agent-inbox/types";
import type { AgentChart, AgentFile, ResolvedAgentChart } from "../../features/agent-inbox/types";

type ActionCommand = {
  label: string;
  payload: string;
  relatedViewer?: "pricing" | "features" | "faq" | "shops" | null;
};

type ExternalActionRequest = {
  id: string;
  label?: string;
  payload: string;
  relatedViewer?: "pricing" | "features" | "faq" | "shops" | null;
};

type ChatHistoryEntry = {
  role: "ai" | "user";
  text: string;
  status?: "sending" | "streaming" | "done" | "error";
  _retryText?: string;
  shops?: any[];
  formStep?: FormStepData | null;
  formDone?: FormDoneData | null;
  formCompleted?: boolean;
  queueJoinFormData?: any | null;
  queueJoinFormSubmitted?: boolean;
  appointmentFormData?: any | null;
  appointmentFormSubmitted?: boolean;
  paymentFormData?: PaymentFormData | null;
  paymentComplete?: boolean;
  checkoutCardData?: CheckoutCardData | null;
  checkoutPaid?: boolean;
  checkoutPickerItems?: CheckoutCardData[];
  relatedViewer?: "shops" | "pricing" | "features" | "faq" | "register" | null;
  quickActions?: ActionCommand[];
  suggestedFollowups?: string[];
  charts?: AgentChart[];
  files?: AgentFile[];
  thinkingSteps?: ThinkingStep[];
  thinkingComplete?: boolean;
  feedbackFormData?: { session_id: string } | null;
  feedbackDismissed?: boolean;
};

type ShopContext = {
  id: number;
  slug?: string;
  name: string;
  city?: string;
  shopType?: string;
};

type MasterAIAgentProps = {
  forceOpen?: boolean;
  initialOpen?: boolean;
  hideCloseButton?: boolean;
  shopContext?: ShopContext | null;
  initialInteractionMode?: "voice" | "chat";
  embedded?: boolean;
  streamEndpoint?: string;
  requestHeaders?: Record<string, string>;
  extraRequestBody?: Record<string, unknown>;
  initialChatHistory?: ChatHistoryEntry[];
  disableVoiceMode?: boolean;
  hideUtilityControls?: boolean;
  compactEmbedded?: boolean;
  brandPrimaryColor?: string;
  brandSecondaryColor?: string;
  embeddedFooter?: React.ReactNode;
  onStreamEvent?: (event: Record<string, any>) => void;
  onChatHistoryChange?: (history: ChatHistoryEntry[]) => void;
  externalActionRequest?: ExternalActionRequest | null;
  onExternalActionHandled?: (actionId: string) => void;
};

const DEFAULT_QUICK_ACTIONS: ActionCommand[] = [
  { label: "Register a Shop", payload: "I want to register a shop" },
  { label: "Search for Shops", payload: "I want to search for shops", relatedViewer: "shops" },
  { label: "Ask about our Products", payload: "Tell me about your products and pricing", relatedViewer: "pricing" },
];

const getShopQuickActions = (shopName: string): ActionCommand[] => [
  { label: "Join Queue", payload: `I want to join the queue at ${shopName}` },
  { label: "Show Services", payload: `What services does ${shopName} offer today?` },
  { label: "Book Appointment", payload: `I want to book an appointment at ${shopName}` },
  { label: "Check Wait Time", payload: `What is the current wait time at ${shopName}?` },
  { label: "Queue Status", payload: "How can I check my queue status?" },
  { label: "Pay for Service", payload: "__pay_for_service__" },
];

const ACTIONABLE_PHRASES: Array<ActionCommand & { phrase: string }> = [
  { phrase: "cancel registration", label: "Cancel Registration", payload: "cancel registration" },
  { phrase: "register a shop", label: "Register a Shop", payload: "I want to register a shop" },
  { phrase: "search for shops", label: "Search for Shops", payload: "I want to search for shops", relatedViewer: "shops" },
  { phrase: "ask about our products", label: "Ask about our Products", payload: "Tell me about your products and pricing", relatedViewer: "pricing" },
  { phrase: "pricing", label: "Pricing", payload: "Show me pricing", relatedViewer: "pricing" },
  { phrase: "features", label: "Features", payload: "Show me features", relatedViewer: "features" },
  { phrase: "faq", label: "FAQ", payload: "Show me FAQ", relatedViewer: "faq" },
  { phrase: "testimonials", label: "Testimonials", payload: "Show me testimonials" },
];

const extractNodeText = (node: React.ReactNode): string => {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(extractNodeText).join("");
  if (React.isValidElement(node) && "children" in node.props) return extractNodeText(node.props.children);
  return "";
};

const getQuickActionFromListItem = (children: React.ReactNode): ActionCommand | null => {
  const text = extractNodeText(children).toLowerCase();
  return DEFAULT_QUICK_ACTIONS.find((action) => text.includes(action.label.toLowerCase())) || null;
};

const getActionableCommandFromText = (text: string): ActionCommand | null => {
  const normalized = text.trim().toLowerCase();
  const match = ACTIONABLE_PHRASES.find((item) => normalized.includes(item.phrase));
  return match ? { label: match.label, payload: match.payload, relatedViewer: match.relatedViewer ?? null } : null;
};

const buildChartPalette = (chart: ResolvedAgentChart, accent: string) => {
  const explicit = Array.isArray(chart.colors) ? chart.colors.filter((value) => typeof value === "string" && value.trim()) : [];
  return explicit.length > 0 ? explicit : [accent, "#0284c7", "#0f766e", "#ca8a04", "#be123c"];
};

const chartValue = (value: unknown) => (typeof value === "number" ? value : Number(value ?? 0));

function AgentChartView({ chart, accent }: { chart: AgentChart; accent: string }) {
  const resolvedChart = resolveAgentChart(chart);
  if (!resolvedChart) return null;

  const palette = buildChartPalette(resolvedChart, accent);
  const config = resolvedChart.series.reduce<ChartConfig>((acc, series, index) => {
    acc[series.key] = {
      label: series.label,
      color: series.color || palette[index % palette.length],
    };
    return acc;
  }, {});

  const data = resolvedChart.data.map((point) => ({
    ...point,
    [resolvedChart.xKey]: String(point[resolvedChart.xKey] ?? ""),
    ...Object.fromEntries(resolvedChart.series.map((series) => [series.key, chartValue(point[series.key])])),
  }));

  const primarySeries = resolvedChart.series[0];

  return (
    <Card className="mt-3 overflow-hidden">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">{resolvedChart.title}</CardTitle>
        {resolvedChart.description && <p className="text-xs text-muted-foreground">{resolvedChart.description}</p>}
      </CardHeader>
      <CardContent className="p-3 pt-0">
        <ChartContainer config={config} className="h-[180px] w-full">
          {resolvedChart.chartType === "line" || resolvedChart.chartType === "sparkline" ? (
            <RechartsLineChart data={data} margin={{ top: 10, right: 12, bottom: resolvedChart.chartType === "sparkline" ? 0 : 20, left: 0 }}>
              {resolvedChart.showGrid && resolvedChart.chartType !== "sparkline" && <CartesianGrid vertical={false} />}
              {resolvedChart.chartType !== "sparkline" && <XAxis dataKey={resolvedChart.xKey} tickLine={false} axisLine={false} tickMargin={8} />}
              {resolvedChart.chartType !== "sparkline" && <YAxis tickLine={false} axisLine={false} width={32} />}
              <ChartTooltip content={<ChartTooltipContent />} />
              {resolvedChart.series.map((series, index) => (
                <Line
                  key={series.key}
                  type="monotone"
                  dataKey={series.key}
                  stroke={`var(--color-${series.key})`}
                  strokeWidth={2}
                  dot={resolvedChart.chartType !== "sparkline"}
                  isAnimationActive={false}
                />
              ))}
            </RechartsLineChart>
          ) : resolvedChart.chartType === "pie" && primarySeries ? (
            <RechartsPieChart>
              <ChartTooltip content={<ChartTooltipContent nameKey="name" />} />
              <Pie
                data={data.map((point, index) => ({
                  name: String(point[resolvedChart.xKey] ?? ""),
                  value: chartValue(point[primarySeries.key]),
                  fill: palette[index % palette.length],
                }))}
                dataKey="value"
                nameKey="name"
                innerRadius={38}
                outerRadius={70}
                isAnimationActive={false}
              >
                {data.map((_, index) => (
                  <Cell key={index} fill={palette[index % palette.length]} />
                ))}
              </Pie>
            </RechartsPieChart>
          ) : (
            <RechartsBarChart data={data} margin={{ top: 10, right: 12, bottom: 20, left: 0 }}>
              {resolvedChart.showGrid && <CartesianGrid vertical={false} />}
              <XAxis dataKey={resolvedChart.xKey} tickLine={false} axisLine={false} tickMargin={8} />
              <YAxis tickLine={false} axisLine={false} width={32} />
              <ChartTooltip content={<ChartTooltipContent />} />
              {resolvedChart.series.map((series) => (
                <Bar key={series.key} dataKey={series.key} fill={`var(--color-${series.key})`} radius={4} isAnimationActive={false} />
              ))}
            </RechartsBarChart>
          )}
        </ChartContainer>
      </CardContent>
    </Card>
  );
}

const MasterAIAgent: React.FC<MasterAIAgentProps> = ({
  forceOpen = false,
  initialOpen = false,
  hideCloseButton = false,
  shopContext = null,
  initialInteractionMode = "voice",
  embedded = false,
  streamEndpoint = "/api/agent/master/chat/stream",
  requestHeaders,
  extraRequestBody,
  initialChatHistory,
  disableVoiceMode = false,
  hideUtilityControls = false,
  compactEmbedded = false,
  brandPrimaryColor,
  brandSecondaryColor,
  embeddedFooter,
  onStreamEvent,
  onChatHistoryChange,
  externalActionRequest,
  onExternalActionHandled,
}) => {
  const [isOpen, setIsOpen] = useState(forceOpen || initialOpen);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isToggling, setIsToggling] = useState(false);
  const effectiveInitialMode = disableVoiceMode ? "chat" : initialInteractionMode;
  const [interactionMode, setInteractionMode] = useState<"voice" | "chat">(effectiveInitialMode);
  const interactionModeRef = useRef<"voice" | "chat">(effectiveInitialMode);
  const [location, setLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [sessionId, setSessionId] = useState("");
  const [activeViewer, setActiveViewer] = useState<"shops" | "pricing" | "features" | "faq" | "register" | null>(null);
  const [activeShops, setActiveShops] = useState<any[]>([]);
  const [registrationAccountType, setRegistrationAccountType] = useState<"customer" | "shop_owner" | null>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const lastExternalActionIdRef = useRef<string | null>(null);
  const postPaymentResetTimerRef = useRef<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<HTMLInputElement | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const currentSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const audioQueueRef = useRef<string[]>([]);
  const isPlayingAudioRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const lastUserSubmitRef = useRef({ text: "", at: 0 });
  const submitAudioRef = useRef<() => Promise<void>>(async () => undefined);
  const navigate = useNavigate();

  const resolvedPrimary = brandPrimaryColor || "#7c3aed";
  const resolvedSecondary = brandSecondaryColor || resolvedPrimary;
  const theme = {
    text: isDarkMode ? "#ffffff" : "#0f172a",
    textSecondary: isDarkMode ? "rgba(255,255,255,0.7)" : "rgba(15,23,42,0.68)",
    accent: resolvedPrimary,
    cardBg: isDarkMode ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.78)",
    cardBorder: isDarkMode ? "rgba(255,255,255,0.12)" : "rgba(15,23,42,0.12)",
    inputBg: isDarkMode ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.95)",
  };

  const [chatHistory, setChatHistory] = useState<ChatHistoryEntry[]>(() => {
    if (initialChatHistory && initialChatHistory.length > 0) return initialChatHistory;
    if (shopContext) {
      return [
        {
          role: "ai",
          text: `Welcome to ${shopContext.name}. I'm ZeroQ, your AI concierge. Tell me your name, phone, and what service you need, and I'll add you to the queue.`,
          quickActions: getShopQuickActions(shopContext.name),
        },
      ];
    }
    return [
      {
        role: "ai",
        text: "Welcome to ZeroQwait! I'm ZeroQ, your AI operations assistant. Here's what I can help you with:\n\n1. **Register a Shop** — Set up your business and get your own AI agent team\n2. **Search for Shops** — Find services nearby and join an AI-powered queue\n3. **Ask about our Products** — Pricing, features, and how it all works\n\nWhat would you like to do?",
        quickActions: DEFAULT_QUICK_ACTIONS,
      },
    ];
  });

  const getAudioContext = useCallback(() => {
    if (!audioCtxRef.current || audioCtxRef.current.state === "closed") {
      audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    }
    return audioCtxRef.current;
  }, []);

  const decodeBase64Audio = useCallback((base64Audio: string): ArrayBuffer => {
    const binaryStr = atob(base64Audio);
    const bytes = new Uint8Array(binaryStr.length);
    for (let index = 0; index < binaryStr.length; index += 1) {
      bytes[index] = binaryStr.charCodeAt(index);
    }
    return bytes.buffer.slice(0) as ArrayBuffer;
  }, []);

  const playAudio = useCallback(async (base64Audio: string) => {
    try {
      const audioCtx = getAudioContext();
      if (audioCtx.state === "suspended") await audioCtx.resume();
      const audioBuffer = await audioCtx.decodeAudioData(decodeBase64Audio(base64Audio));
      await new Promise<void>((resolve) => {
        const source = audioCtx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioCtx.destination);
        source.onended = () => {
          setIsSpeaking(false);
          currentSourceRef.current = null;
          resolve();
        };
        currentSourceRef.current = source;
        setIsSpeaking(true);
        source.start(0);
      });
    } catch (error) {
      console.warn("[TTS] Audio playback failed:", error);
      setIsSpeaking(false);
      currentSourceRef.current = null;
    }
  }, [decodeBase64Audio, getAudioContext]);

  const processAudioQueue = useCallback(async () => {
    if (isPlayingAudioRef.current) return;
    isPlayingAudioRef.current = true;
    while (audioQueueRef.current.length > 0) {
      const audio = audioQueueRef.current.shift();
      if (audio && interactionModeRef.current === "voice") {
        await playAudio(audio);
      }
    }
    isPlayingAudioRef.current = false;
  }, [playAudio]);

  const enqueueAudio = useCallback((audio: string | null) => {
    if (!audio || interactionModeRef.current !== "voice") return;
    audioQueueRef.current.push(audio);
    void processAudioQueue();
  }, [processAudioQueue]);

  const stopCurrentAudio = () => {
    audioQueueRef.current = [];
    isPlayingAudioRef.current = false;
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    try {
      currentSourceRef.current?.stop();
    } catch {
      // Ignore already-stopped audio sources.
    }
    currentSourceRef.current = null;
    setIsSpeaking(false);
  };

  const speak = useCallback(async (text: string) => {
    if (interactionModeRef.current === "chat") return;
    stopCurrentAudio();
    const plainText = text
      .replace(/\*\*(.*?)\*\*/g, "$1")
      .replace(/\*(.*?)\*/g, "$1")
      .replace(/#{1,6}\s/g, "")
      .replace(/`([^`]*)`/g, "$1")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .replace(/\n+/g, " ")
      .replace(/\s{2,}/g, " ")
      .trim();
    if (!plainText || plainText.length < 2) return;

    const controller = new AbortController();
    abortControllerRef.current = controller;
    setIsSpeaking(true);
    try {
      const response = await fetch("/api/voice/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: plainText, voice: "female", speed: 0.98 }),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`TTS ${response.status}`);
      const arrayBuffer = await response.arrayBuffer();
      const audioCtx = getAudioContext();
      if (audioCtx.state === "suspended") await audioCtx.resume();
      const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
      await new Promise<void>((resolve) => {
        const source = audioCtx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioCtx.destination);
        source.onended = () => {
          setIsSpeaking(false);
          currentSourceRef.current = null;
          resolve();
        };
        currentSourceRef.current = source;
        source.start(0);
      });
    } catch (error: any) {
      if (error?.name !== "AbortError") console.warn("[TTS] speak failed:", error);
      setIsSpeaking(false);
      currentSourceRef.current = null;
    }
  }, [getAudioContext]);

  const schedulePostPaymentWelcomeReset = useCallback(() => {
    if (postPaymentResetTimerRef.current) window.clearTimeout(postPaymentResetTimerRef.current);
    postPaymentResetTimerRef.current = window.setTimeout(() => {
      if (shopContext?.id) localStorage.removeItem(`queue_item_${shopContext.id}`);
      setChatHistory((prev) => [
        ...prev,
        {
          role: "ai",
          text: shopContext
            ? `Welcome to ${shopContext.name}. I'm ZeroQ, your AI concierge. Tell me your name, phone, and what service you need, and I'll add you to the queue.`
            : "Welcome to ZeroQwait! I'm ZeroQ, your AI operations assistant. Here's what I can help you with:\n\n1. **Register a Shop** — Set up your business and get your own AI agent team\n2. **Search for Shops** — Find services nearby and join an AI-powered queue\n3. **Ask about our Products** — Pricing, features, and how it all works\n\nWhat would you like to do?",
          quickActions: shopContext ? getShopQuickActions(shopContext.name) : DEFAULT_QUICK_ACTIONS,
          status: "done",
        },
      ]);
    }, 3500);
  }, [shopContext]);

  const handleFormResult = useCallback(
    (result: FormStepData | FormDoneData, sourceIndex: number) => {
      setChatHistory((prev) => {
        const next = [...prev];
        if (next[sourceIndex]) next[sourceIndex].formCompleted = true;
        return next;
      });

      if (result.type === "form_step") {
        const nextStep = result as FormStepData;
        const aiMessage = nextStep.message || nextStep.prompt || "Next step:";
        setChatHistory((prev) => [...prev, { role: "ai", text: aiMessage, formStep: nextStep }]);
        if (nextStep.prompt) void speak(nextStep.prompt);
      } else {
        const done = result as FormDoneData;
        const successText = done.success ? done.message : `Registration failed: ${done.message}`;
        setChatHistory((prev) => [...prev, { role: "ai", text: successText, formDone: done }]);
        void speak(successText);
      }
    },
    [speak],
  );

  const handleQueueJoinFormSubmit = useCallback(
    (result: { success: boolean; queueItemId?: number; position?: number; serviceCost?: number; error?: string }, sourceIndex: number) => {
      setChatHistory((prev) => {
        const next = [...prev];
        if (next[sourceIndex]) {
          next[sourceIndex].queueJoinFormSubmitted = true;
          next[sourceIndex].status = "done";
          next[sourceIndex]._retryText = undefined;
          if (result.success) {
            const costInfo = result.serviceCost && result.serviceCost > 0 ? ` Service cost: $${result.serviceCost.toFixed(2)}.` : "";
            next[sourceIndex].text += `\n\n✅ **Great!** You've been added to the queue. Your position: #${result.position}${costInfo}`;
            if (shopContext && result.queueItemId) {
              localStorage.setItem(`queue_item_${shopContext.id}`, String(result.queueItemId));
            }
            setTimeout(() => {
              if (shopContext) navigate(`/queue/${shopContext.id}`);
            }, 1500);
          } else {
            next[sourceIndex].text += `\n\n❌ Error: ${result.error || "Failed to join queue"}`;
          }
        }
        return next;
      });
    },
    [shopContext, navigate],
  );

  const handlePayForService = useCallback(async () => {
    if (!shopContext) return;
    setChatHistory((prev) => [
      ...prev,
      { role: "user", text: "Pay for Service" },
      { role: "ai", text: "Looking up recently completed services...", status: "streaming" },
    ]);
    try {
      const resp = await axios.get(`/queues/shop/${shopContext.id}/recently-completed`);
      const items: Array<{ id: number; customer_name: string; service_cost: number; service_name: string | null }> = resp.data;
      if (!items || items.length === 0) {
        setChatHistory((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last && last.status === "streaming") {
            last.text = "No recently completed services found. If your service was just finished, please ask the staff to mark it as complete.";
            last.status = "done";
          }
          return next;
        });
        return;
      }
      const checkoutOptions: CheckoutCardData[] = items.map((item) => ({
        queueItemId: item.id,
        customerName: item.customer_name || "Customer",
        serviceName: item.service_name,
        serviceCost: item.service_cost || 0,
        shopId: shopContext.id,
        shopName: shopContext.name,
      }));
      setChatHistory((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && last.status === "streaming") {
          last.text = "Select your name to proceed with payment:";
          last.status = "done";
          last.checkoutPickerItems = checkoutOptions;
        }
        return next;
      });
    } catch {
      setChatHistory((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && last.status === "streaming") {
          last.text = "Could not load completed services right now. Please try again.";
          last.status = "done";
        }
        return next;
      });
    }
  }, [shopContext]);

  const handleChat = useCallback(
    async (userText: string, requestedViewer?: "shops" | "pricing" | "features" | "faq" | null) => {
      if (!userText.trim()) return;

      if (interactionModeRef.current === "voice") {
        try {
          const ctx = getAudioContext();
          if (ctx.state === "suspended") void ctx.resume();
        } catch {
          // Audio context is best-effort.
        }
      }

      const normalized = userText.trim().toLowerCase();
      const now = Date.now();
      if (lastUserSubmitRef.current.text === normalized && now - lastUserSubmitRef.current.at < 900) return;
      lastUserSubmitRef.current = { text: normalized, at: now };

      const nextViewer = requestedViewer ?? activeViewer;
      const nextShops = nextViewer === "shops" ? activeShops : [];
      const aiMessageIndex = chatHistory.length + 1;

      stopCurrentAudio();
      setChatHistory((prev) => [
        ...prev,
        { role: "user", text: userText },
        {
          role: "ai",
          text: "",
          status: "streaming",
          _retryText: userText,
          shops: nextShops,
          relatedViewer: nextViewer,
          thinkingSteps: [],
          thinkingComplete: false,
        },
      ]);
      setIsProcessing(true);

      try {
        const response = await fetch(streamEndpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...(requestHeaders || {}) },
          body: JSON.stringify({
            message: userText,
            session_id: sessionId,
            latitude: location?.lat,
            longitude: location?.lng,
            history: chatHistory.map((h) => ({ role: h.role === "ai" ? "assistant" : "user", content: h.text })),
            context: {
              active_view: nextViewer,
              visible_shops: nextShops.map((shop) => shop.name),
              ...(shopContext
                ? {
                    shop_id: shopContext.id,
                    shop_slug: shopContext.slug,
                    shop_name: shopContext.name,
                    city: shopContext.city,
                    preferred_category: shopContext.shopType,
                  }
                : {}),
            },
            is_voice: interactionModeRef.current === "voice",
            ...(extraRequestBody || {}),
          }),
        });

        if (!response.ok) {
          const errText = await response.text();
          throw new Error(`Server error ${response.status}: ${errText}`);
        }
        if (!response.body) throw new Error("No response body");

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let sseBuffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          sseBuffer += decoder.decode(value, { stream: true });
          const lines = sseBuffer.split("\n");
          sseBuffer = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const dataStr = line.slice(6);
            if (dataStr === "[DONE]") {
              setChatHistory((prev) => {
                const next = [...prev];
                const idx = next.length - 1;
                if (idx >= 0 && next[idx].role === "ai") {
                  next[idx] = { ...next[idx], thinkingComplete: true, status: "done" };
                }
                return next;
              });
              continue;
            }

            try {
              const data = JSON.parse(dataStr);
              onStreamEvent?.(data);

              if (data.type === "sentence") {
                const sentenceText = data.text || "";
                const audioB64 = data.audio || null;
                setChatHistory((prev) => {
                  const next = [...prev];
                  if (next[aiMessageIndex]?.role === "ai") {
                    next[aiMessageIndex] = {
                      ...next[aiMessageIndex],
                      text: `${next[aiMessageIndex].text || ""}${sentenceText}\n\n`,
                    };
                  }
                  return next;
                });
                enqueueAudio(audioB64);
              } else if (data.type === "text") {
                setChatHistory((prev) => {
                  const next = [...prev];
                  const idx = next.length - 1;
                  if (idx >= 0 && next[idx].role === "ai") {
                    next[idx] = { ...next[idx], text: (next[idx].text || "") + (data.content || "") };
                  }
                  return next;
                });
              } else if (data.type === "thinking_step") {
                const incoming: ThinkingStep = {
                  id: `pipeline-${String(data.step || "step")}`,
                  label: data.label,
                  status: data.status === "done" ? "completed" : data.status,
                  agent: data.agent ?? null,
                };
                setChatHistory((prev) => {
                  const next = [...prev];
                  const idx = next.length - 1;
                  if (idx >= 0 && next[idx].role === "ai") {
                    const existing = next[idx].thinkingSteps ?? [];
                    const pos = existing.findIndex((step) => step.id === incoming.id);
                    const updated = pos >= 0 ? existing.map((step) => (step.id === incoming.id ? incoming : step)) : [...existing, incoming];
                    next[idx] = { ...next[idx], thinkingSteps: updated };
                  }
                  return next;
                });
              } else if (data.type === "tool_call") {
                const toolName = String(data.tool_name || data.tool || "unknown_tool");
                setChatHistory((prev) => {
                  const next = [...prev];
                  const idx = next.length - 1;
                  if (idx >= 0 && next[idx].role === "ai") {
                    const existing = [...(next[idx].thinkingSteps ?? [])].map((step, index, arr) =>
                      index === arr.length - 1 && step.status === "active" ? { ...step, status: "completed" as const } : step,
                    );
                    next[idx] = {
                      ...next[idx],
                      thinkingSteps: [...existing, { id: `tool-${toolName}-${Date.now()}`, label: `Calling ${toolName}...`, status: "active", toolName }],
                    };
                  }
                  return next;
                });
              } else if (data.type === "tool_result") {
                const toolName = String(data.tool_name || data.tool || "unknown_tool");
                const hasError = Boolean(data.error || data.result?.error);
                setChatHistory((prev) => {
                  const next = [...prev];
                  const idx = next.length - 1;
                  if (idx >= 0 && next[idx].role === "ai") {
                    const existing = [...(next[idx].thinkingSteps ?? [])];
                    const targetIndex = [...existing].map((step, index) => ({ step, index })).reverse().find(({ step }) => step.toolName === toolName && step.status === "active")?.index;
                    if (typeof targetIndex === "number") {
                      existing[targetIndex] = { ...existing[targetIndex], status: hasError ? "error" : "completed" };
                      next[idx] = { ...next[idx], thinkingSteps: existing };
                    }
                  }
                  return next;
                });
              } else if (data.type === "error") {
                const errText = data.content || data.message || "Something went wrong. Please try again.";
                setChatHistory((prev) => {
                  const next = [...prev];
                  const idx = next.length - 1;
                  if (idx >= 0 && next[idx].role === "ai") {
                    next[idx] = { ...next[idx], text: (next[idx].text || "") + errText };
                  }
                  return next;
                });
              } else if (data.type === "actions") {
                let currentShops = [...activeShops];
                let currentViewer = activeViewer;
                const actions = data.actions;
                if (actions && Array.isArray(actions) && actions.length > 0) {
                  actions.forEach((action: any) => {
                    if (action.tool === "navigate_to_page_section") {
                      currentViewer = action.result.target as any;
                      currentShops = [];
                    } else if (action.tool === "search_shops") {
                      const shops = Array.isArray(action.result) ? action.result : action.result?.shops || [];
                      if (shops.length > 0) {
                        currentShops = shops;
                        currentViewer = "shops";
                      }
                    } else if (action.tool === "start_registration") {
                      const accountType = action.result?.account_type;
                      setRegistrationAccountType(accountType === "shop_owner" || accountType === "customer" ? accountType : null);
                    } else if (action.tool === "join_queue" && action.result?.success) {
                      const queueItemId = action.result?.queue_item_id;
                      const joinedShopId = action.params?.shop_id || shopContext?.id;
                      if (queueItemId && joinedShopId) localStorage.setItem(`queue_item_${joinedShopId}`, String(queueItemId));
                      if (joinedShopId) setTimeout(() => navigate(`/queue/${joinedShopId}`), 1200);
                    }
                  });
                } else {
                  currentViewer = null;
                  currentShops = [];
                }
                setActiveShops(currentShops);
                setActiveViewer(currentViewer);
                setChatHistory((prev) => {
                  const next = [...prev];
                  if (next[aiMessageIndex]) {
                    next[aiMessageIndex].shops = currentShops;
                    next[aiMessageIndex].relatedViewer = currentViewer;
                  }
                  return next;
                });
              } else if (data.type === "form_step") {
                setChatHistory((prev) => {
                  const next = [...prev];
                  if (next[aiMessageIndex]) next[aiMessageIndex].formStep = data as FormStepData;
                  return next;
                });
              } else if (data.type === "feedback_form") {
                setChatHistory((prev) => {
                  const next = [...prev];
                  if (next[aiMessageIndex]) next[aiMessageIndex].feedbackFormData = { session_id: data.session_id ?? sessionId };
                  return next;
                });
              } else if (data.type === "queue_join_form") {
                setChatHistory((prev) => {
                  const next = [...prev];
                  if (next[aiMessageIndex]) next[aiMessageIndex].queueJoinFormData = data;
                  return next;
                });
              } else if (data.type === "appointment_form") {
                setChatHistory((prev) => {
                  const next = [...prev];
                  if (next[aiMessageIndex]) next[aiMessageIndex].appointmentFormData = data;
                  return next;
                });
              } else if (data.type === "payment_form") {
                setChatHistory((prev) => {
                  const next = [...prev];
                  if (next[aiMessageIndex]) next[aiMessageIndex].paymentFormData = data as PaymentFormData;
                  return next;
                });
              } else if (data.type === "suggestions") {
                const suggestions: string[] = Array.isArray(data.suggestions) ? data.suggestions : [];
                if (suggestions.length > 0) {
                  setChatHistory((prev) => {
                    const next = [...prev];
                    if (next[aiMessageIndex]) next[aiMessageIndex].suggestedFollowups = suggestions;
                    return next;
                  });
                }
              } else if (data.type === "chart") {
                const chart = createAgentChartFromPayload(data, new Date().toISOString());
                if (chart) {
                  setChatHistory((prev) => {
                    const next = [...prev];
                    if (next[aiMessageIndex]) {
                      const existing = next[aiMessageIndex].charts ?? [];
                      next[aiMessageIndex].charts = [...existing, chart];
                    }
                    return next;
                  });
                  onStreamEvent?.({ ...data, _parsed_chart: chart });
                }
              } else if (data.type === "file") {
                const file: AgentFile = {
                  id: `file_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
                  filename: data.filename || "download",
                  content: data.content || "",
                  mimeType: data.mimeType || "application/octet-stream",
                  timestamp: new Date().toISOString(),
                };
                setChatHistory((prev) => {
                  const next = [...prev];
                  if (next[aiMessageIndex]) {
                    const existing = next[aiMessageIndex].files ?? [];
                    next[aiMessageIndex].files = [...existing, file];
                  }
                  return next;
                });
                onStreamEvent?.({ ...data, _parsed_file: file });
              }
            } catch {
              console.warn("Failed to parse SSE data chunk:", dataStr);
            }
          }
        }
      } catch (error) {
        console.error("[MasterAIAgent] stream error:", error);
        setChatHistory((prev) => {
          const next = [...prev];
          if (next[aiMessageIndex]) {
            next[aiMessageIndex] = {
              ...next[aiMessageIndex],
              text: "I encountered an error trying to process that request.",
              status: "error",
            };
          }
          return next;
        });
      } finally {
        setIsProcessing(false);
        setChatHistory((prev) => {
          const next = [...prev];
          const idx = aiMessageIndex;
          if (idx >= 0 && next[idx]?.role === "ai" && next[idx].status === "streaming") {
            const hasInteractiveContent = Boolean(
              next[idx].text?.trim() ||
                next[idx].queueJoinFormData ||
                next[idx].appointmentFormData ||
                next[idx].paymentFormData ||
                next[idx].formStep ||
                next[idx].checkoutPickerItems?.length ||
                next[idx].checkoutCardData ||
                next[idx].charts?.length ||
                next[idx].files?.length,
            );
            next[idx] = {
              ...next[idx],
              text: hasInteractiveContent ? next[idx].text : "Something went wrong - please try again.",
              status: hasInteractiveContent ? "done" : "error",
            };
          }
          return next;
        });
      }
    },
    [
      activeShops,
      activeViewer,
      chatHistory,
      enqueueAudio,
      extraRequestBody,
      getAudioContext,
      location?.lat,
      location?.lng,
      navigate,
      onStreamEvent,
      requestHeaders,
      sessionId,
      shopContext,
      streamEndpoint,
    ],
  );

  const {
    isRecording,
    startRecording,
    stopRecording,
    hasPermission,
    transcript,
  } = useAudioRecorder(() => {
    void submitAudioRef.current?.();
  });

  const { volume } = useAudioVisualizer(isRecording);

  const submitAudio = useCallback(async () => {
    const audioBlob = await stopRecording();
    if (!audioBlob) return;
    setIsTranscribing(true);
    try {
      const formData = new FormData();
      formData.append("file", audioBlob, "recording.webm");
      const response = await axios.post("/voice/transcribe", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const text = response.data.text;
      if (text && text.trim()) void handleChat(text);
    } catch (error) {
      console.error("[MasterAIAgent] transcription failed:", error);
    } finally {
      setIsTranscribing(false);
    }
  }, [handleChat, stopRecording]);

  useEffect(() => {
    submitAudioRef.current = submitAudio;
  }, [submitAudio]);

  const handleVoiceToggle = async () => {
    if (isToggling || isProcessing || isTranscribing) return;
    setIsToggling(true);
    const safetyTimer = setTimeout(() => setIsToggling(false), 8000);
    try {
      if (isRecording) await submitAudio();
      else await startRecording();
    } catch (error) {
      console.error("Voice toggle failed:", error);
    } finally {
      clearTimeout(safetyTimer);
      setIsToggling(false);
    }
  };

  const handleActionCommand = useCallback(
    (action: ActionCommand) => {
      if (action.payload === "__pay_for_service__") {
        void handlePayForService();
        return;
      }
      if (action.relatedViewer) {
        setActiveViewer(action.relatedViewer);
        if (action.relatedViewer !== "shops") setActiveShops([]);
      }
      void handleChat(action.payload, action.relatedViewer ?? undefined);
    },
    [handleChat, handlePayForService],
  );

  useEffect(() => {
    interactionModeRef.current = interactionMode;
  }, [interactionMode]);

  useEffect(() => {
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        (err) => console.warn("[MasterAIAgent] Geolocation denied or unavailable:", err),
      );
    }
  }, []);

  useEffect(() => {
    const sessionKey = shopContext ? `zeroq_shop_session_${shopContext.id}` : "zeroq_session_id";
    let sid = sessionStorage.getItem(sessionKey);
    if (!sid) {
      sid = Math.random().toString(36).substring(2) + Date.now().toString(36);
      sessionStorage.setItem(sessionKey, sid);
    }
    setSessionId(sid);
  }, [shopContext]);

  useEffect(() => {
    if (forceOpen) {
      setIsOpen(true);
      return;
    }
    const handleToggle = () => setIsOpen((prev) => !prev);
    window.addEventListener("trigger-zeroq-assistant", handleToggle);
    return () => window.removeEventListener("trigger-zeroq-assistant", handleToggle);
  }, [forceOpen]);

  useEffect(() => {
    return () => {
      if (postPaymentResetTimerRef.current) window.clearTimeout(postPaymentResetTimerRef.current);
      stopCurrentAudio();
    };
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    const restoreRegistration = async () => {
      try {
        const res = await fetch(`/api/agent/registration/state?session_id=${encodeURIComponent(sessionId)}`);
        if (!res.ok) return;
        const state = await res.json();
        if (!state.active || !state.form_step) return;
        const stepLabel = state.form_step.prompt || state.form_step.message || `Step: ${state.step}`;
        setChatHistory((prev) => [
          ...prev,
          {
            role: "ai",
            text: `Continuing your registration (step: **${state.step}**). Please complete the form below, or say **cancel registration** to start over.\n\n${stepLabel}`,
            formStep: state.form_step as FormStepData,
          },
        ]);
      } catch (error) {
        console.warn("Could not check registration state:", error);
      }
    };
    void restoreRegistration();
  }, [sessionId]);

  useEffect(() => {
    if (!externalActionRequest?.id) return;
    if (externalActionRequest.id === lastExternalActionIdRef.current) return;
    lastExternalActionIdRef.current = externalActionRequest.id;
    handleActionCommand({
      label: externalActionRequest.label || "Quick Action",
      payload: externalActionRequest.payload,
      relatedViewer: externalActionRequest.relatedViewer ?? null,
    });
    onExternalActionHandled?.(externalActionRequest.id);
  }, [externalActionRequest, handleActionCommand, onExternalActionHandled]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [chatHistory]);

  useEffect(() => {
    onChatHistoryChange?.(chatHistory);
  }, [chatHistory, onChatHistoryChange]);

  if (!isOpen) return null;

  const shouldRenderVoiceOrb = !(embedded && compactEmbedded && disableVoiceMode);
  const shouldShowShopBadge = !(embedded && compactEmbedded && hideUtilityControls);
  const isPublicEmbedded = embedded && !compactEmbedded;

  const submitDraft = () => {
    const draft = chatInputRef.current?.value?.trim();
    if (!draft) return;
    void handleChat(draft);
    if (chatInputRef.current) chatInputRef.current.value = "";
  };

  return (
    <div
      id="immersive-ai-overlay"
      className={cn(
        "flex flex-col overflow-hidden text-foreground",
        embedded ? "relative h-full w-full rounded-2xl border" : "fixed inset-0 z-[10000] h-[100dvh] w-screen",
        isDarkMode ? "dark bg-[#05050a]" : "bg-background",
      )}
      style={{
        background: isDarkMode
          ? `radial-gradient(ellipse 80% 50% at 50% -20%, ${resolvedPrimary}38, #05050A)`
          : `radial-gradient(ellipse 80% 50% at 50% -20%, ${resolvedPrimary}28, ${resolvedSecondary}10 52%, #ffffff)`,
        borderColor: embedded ? theme.cardBorder : "transparent",
      }}
    >
      <div className="absolute right-3 top-3 z-20 flex items-center gap-2 md:right-8 md:top-8">
        {!hideUtilityControls && (
          <>
            <Button variant="outline" size="icon" onClick={() => setIsDarkMode((prev) => !prev)} aria-label="Toggle color mode">
              {isDarkMode ? <Sun /> : <Moon />}
            </Button>
            {!disableVoiceMode && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  const newMode = interactionMode === "voice" ? "chat" : "voice";
                  if (newMode === "chat") {
                    stopCurrentAudio();
                    if (isRecording) void stopRecording();
                  } else {
                    try {
                      const ctx = getAudioContext();
                      if (ctx.state === "suspended") void ctx.resume();
                    } catch {
                      // no-op
                    }
                  }
                  setInteractionMode(newMode);
                }}
              >
                {interactionMode === "voice" ? <Volume2 data-icon="inline-start" /> : <VolumeX data-icon="inline-start" />}
                {interactionMode === "voice" ? "Voice" : "Chat"}
              </Button>
            )}
          </>
        )}
        {!hideCloseButton && !forceOpen && (
          <Button variant="outline" size="icon" onClick={() => setIsOpen(false)} aria-label="Close assistant">
            <X />
          </Button>
        )}
      </div>

      {shopContext && shouldShowShopBadge && (
        <div className="absolute left-3 top-3 z-20 max-w-[62%] rounded-xl border bg-background/85 px-3 py-2 text-sm shadow-sm backdrop-blur md:left-8 md:top-8">
          <p className="text-xs font-semibold text-muted-foreground">Now chatting with</p>
          <p className="truncate font-bold text-primary">{shopContext.name}</p>
          {(shopContext.city || shopContext.shopType) && (
            <p className="truncate text-xs text-muted-foreground">{[shopContext.city, shopContext.shopType].filter(Boolean).join(" - ")}</p>
          )}
        </div>
      )}

      <div className="flex min-h-0 flex-1 overflow-hidden px-3 pb-3 pt-20 md:px-8 md:pb-8 md:pt-24">
        <div
          className={cn(
            "mx-auto flex w-full min-h-0 gap-4",
            activeViewer ? "max-w-[1400px] flex-col lg:flex-row" : "max-w-3xl flex-col items-center",
          )}
        >
          <section
            className={cn(
              "flex min-h-0 w-full flex-col items-center gap-3",
              activeViewer ? "lg:w-[420px] lg:shrink-0" : "",
              embedded && "h-full",
            )}
          >
            {shouldRenderVoiceOrb && (
              <button
                type="button"
                onClick={interactionMode === "voice" ? handleVoiceToggle : undefined}
                disabled={interactionMode !== "voice" || isTranscribing || isToggling}
                className={cn(
                  "relative shrink-0 rounded-full transition",
                  interactionMode === "chat" ? "size-20 opacity-65" : activeViewer ? "size-28" : isPublicEmbedded ? "size-36" : "size-48",
                  isRecording && "drop-shadow-[0_0_24px_var(--owner-primary,#7c3aed)]",
                )}
                aria-label="Toggle voice recording"
              >
                <ParticleSphere volume={volume} isListening={isRecording} color={resolvedPrimary} isProcessing={isProcessing || isSpeaking} />
                {interactionMode === "voice" && (
                  <span className="absolute inset-0 grid place-items-center text-foreground/55">
                    {isToggling || isTranscribing ? <Loader2 className="size-8 animate-spin" /> : isRecording ? <Mic className="size-8" /> : <MicOff className="size-8" />}
                  </span>
                )}
              </button>
            )}

            {shouldRenderVoiceOrb && (
              <button
                type="button"
                onClick={!disableVoiceMode && interactionMode === "voice" ? handleVoiceToggle : undefined}
                className="min-h-5 text-center text-xs font-semibold uppercase text-muted-foreground"
              >
                {interactionMode === "chat"
                  ? "Chat mode"
                  : isTranscribing
                    ? "Transcribing..."
                    : isRecording
                      ? transcript || "Listening..."
                      : hasPermission === false
                        ? "Microphone unavailable"
                        : "Tap orb to speak"}
              </button>
            )}

            <div
              ref={scrollRef}
              className={cn(
                "flex min-h-0 w-full flex-1 flex-col gap-3 overflow-y-auto rounded-2xl border bg-background/72 p-3 shadow-sm backdrop-blur",
                embedded ? "max-h-full" : "max-h-[52vh]",
              )}
            >
              {chatHistory.map((chat, index) => (
                <div key={index} className={cn("flex w-full flex-col gap-2", chat.role === "user" ? "items-end" : "items-start")}>
                  <div
                    className={cn(
                      "max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm",
                      chat.role === "user"
                        ? "rounded-br-md bg-primary text-primary-foreground"
                        : "rounded-bl-md border bg-card text-card-foreground",
                      chat.status === "error" && "border-destructive/40 text-destructive",
                    )}
                  >
                    {chat.role === "user" ? (
                      <p>{chat.text}</p>
                    ) : (
                      <>
                        {chat.thinkingSteps && chat.thinkingSteps.length > 0 && (
                          <ThinkingSteps steps={chat.thinkingSteps} isComplete={chat.thinkingComplete ?? false} accentColor={resolvedPrimary} />
                        )}
                        {chat.text && (
                          <div className="prose prose-sm max-w-none dark:prose-invert prose-p:my-1 prose-ul:my-1 prose-ol:my-1">
                            <ReactMarkdown
                              components={{
                                li: ({ children }) => {
                                  const action = getQuickActionFromListItem(children);
                                  if (!action) return <li>{children}</li>;
                                  return (
                                    <li>
                                      <button type="button" className="text-left hover:underline" disabled={isProcessing} onClick={() => handleActionCommand(action)}>
                                        {children}
                                      </button>
                                    </li>
                                  );
                                },
                                strong: ({ children }) => {
                                  const action = getActionableCommandFromText(extractNodeText(children));
                                  if (!action) return <strong>{children}</strong>;
                                  return (
                                    <button type="button" className="font-semibold text-primary underline-offset-2 hover:underline" disabled={isProcessing} onClick={() => handleActionCommand(action)}>
                                      {children}
                                    </button>
                                  );
                                },
                              }}
                            >
                              {chat.text}
                            </ReactMarkdown>
                          </div>
                        )}

                        {chat.status === "error" && chat._retryText && (
                          <Button size="sm" variant="outline" className="mt-2" onClick={() => handleChat(chat._retryText!)}>
                            Retry
                          </Button>
                        )}

                        {((chat.quickActions && chat.quickActions.length > 0) ||
                          (chat.role === "ai" &&
                            chat.text.includes("Register a Shop") &&
                            chat.text.includes("Search for Shops") &&
                            chat.text.includes("Ask about our Products"))) && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {(chat.quickActions && chat.quickActions.length > 0 ? chat.quickActions : DEFAULT_QUICK_ACTIONS).map((action) => (
                              <Button key={action.label} size="sm" variant="outline" disabled={isProcessing} onClick={() => handleActionCommand(action)}>
                                {action.label}
                              </Button>
                            ))}
                          </div>
                        )}

                        {chat.charts?.map((chart) => <AgentChartView key={chart.id} chart={chart} accent={resolvedPrimary} />)}

                        {chat.files && chat.files.length > 0 && (
                          <div className="mt-3 flex flex-col gap-2">
                            {chat.files.map((file) => (
                              <Button
                                key={file.id}
                                size="sm"
                                variant="outline"
                                className="justify-start"
                                onClick={() => {
                                  const link = document.createElement("a");
                                  link.href = file.content.startsWith("http") ? file.content : `data:${file.mimeType};base64,${file.content}`;
                                  link.download = file.filename;
                                  document.body.appendChild(link);
                                  link.click();
                                  document.body.removeChild(link);
                                }}
                              >
                                <Download data-icon="inline-start" />
                                {file.filename}
                              </Button>
                            ))}
                          </div>
                        )}

                        {chat.suggestedFollowups && chat.suggestedFollowups.length > 0 && chat.status === "done" && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {chat.suggestedFollowups.map((suggestion) => (
                              <Button key={suggestion} type="button" variant="outline" size="sm" disabled={isProcessing} onClick={() => handleChat(suggestion)}>
                                {suggestion}
                              </Button>
                            ))}
                          </div>
                        )}

                        {chat.formDone && chat.formDone.success && (
                          <Alert className="mt-3">
                            <AlertDescription>
                              Registration complete{chat.formDone.shop ? `: ${chat.formDone.shop.name} is live at /${chat.formDone.shop.slug}` : "."}
                            </AlertDescription>
                          </Alert>
                        )}
                      </>
                    )}
                  </div>

                  {chat.formStep && (
                    <div className="w-full max-w-[92%]">
                      <InlineRegistrationForm formStep={chat.formStep} sessionId={sessionId} theme={theme} isDarkMode={isDarkMode} disabled={!!chat.formCompleted} onFormResult={(result) => handleFormResult(result, index)} />
                    </div>
                  )}

                  {chat.feedbackFormData && !chat.feedbackDismissed && (
                    <div className="w-full max-w-[92%]">
                      <InlineFeedbackForm
                        sessionId={chat.feedbackFormData.session_id}
                        onDismiss={() =>
                          setChatHistory((prev) => {
                            const next = [...prev];
                            if (next[index]) next[index].feedbackDismissed = true;
                            return next;
                          })
                        }
                      />
                    </div>
                  )}

                  {chat.queueJoinFormData && !chat.queueJoinFormSubmitted && (
                    <div className="w-full max-w-[92%]">
                      <InlineQueueJoinForm
                        shopId={chat.queueJoinFormData.shop_id}
                        shopName={chat.queueJoinFormData.shop_name}
                        shopType={chat.queueJoinFormData.shop_type}
                        services={chat.queueJoinFormData.services}
                        sessionId={sessionId}
                        theme={theme}
                        isDarkMode={isDarkMode}
                        disabled={!!chat.queueJoinFormSubmitted}
                        onFormSubmit={(result) => handleQueueJoinFormSubmit(result, index)}
                      />
                    </div>
                  )}

                  {chat.appointmentFormData && !chat.appointmentFormSubmitted && (
                    <div className="w-full max-w-[92%]">
                      <InlineAppointmentForm
                        shopId={chat.appointmentFormData.shop_id}
                        shopName={chat.appointmentFormData.shop_name}
                        services={chat.appointmentFormData.services}
                        theme={theme}
                        isDarkMode={isDarkMode}
                        disabled={!!chat.appointmentFormSubmitted}
                        onFormSubmit={(result) => {
                          setChatHistory((prev) => {
                            const next = [...prev];
                            if (next[index]) next[index].appointmentFormSubmitted = true;
                            return next;
                          });
                          if (result.success) {
                            const time = result.scheduledStart
                              ? new Date(result.scheduledStart).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
                              : "";
                            setChatHistory((prev) => [...prev, { role: "ai", text: `Your appointment has been booked for ${time}. Appointment #${result.appointmentId}. We look forward to seeing you!`, status: "done" }]);
                          }
                        }}
                      />
                    </div>
                  )}

                  {chat.checkoutPickerItems && chat.checkoutPickerItems.length > 0 && !chat.checkoutCardData && (
                    <div className="flex flex-wrap gap-2">
                      {chat.checkoutPickerItems.map((item) => (
                        <Button
                          key={item.queueItemId}
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            setChatHistory((prev) => {
                              const next = [...prev];
                              if (next[index]) {
                                next[index].checkoutCardData = item;
                                next[index].checkoutPickerItems = undefined;
                              }
                              return next;
                            })
                          }
                        >
                          {item.customerName}
                        </Button>
                      ))}
                    </div>
                  )}

                  {chat.checkoutCardData && !chat.checkoutPaid && !chat.paymentFormData && (
                    <InlineCheckoutCard
                      data={chat.checkoutCardData}
                      compact
                      onPayNow={(paymentData) => {
                        if (paymentData.payment_intent_id === "free") {
                          if (chat.checkoutCardData?.queueItemId) {
                            void axios.post(`/queues/items/${chat.checkoutCardData.queueItemId}/checkout`).catch(() => {});
                          }
                          setChatHistory((prev) => {
                            const next = [...prev];
                            if (next[index]) {
                              next[index].paymentComplete = true;
                              next[index].checkoutPaid = true;
                              next[index].text += "\n\n✅ **Checkout complete!** No payment required - you're all set.";
                            }
                            return next;
                          });
                          schedulePostPaymentWelcomeReset();
                          return;
                        }
                        setChatHistory((prev) => {
                          const next = [...prev];
                          if (next[index]) next[index].paymentFormData = paymentData;
                          return next;
                        });
                      }}
                    />
                  )}

                  {chat.checkoutCardData && chat.checkoutPaid && <InlineCheckoutCard data={chat.checkoutCardData} paid compact />}

                  {chat.paymentFormData && (
                    <InlinePaymentForm
                      data={chat.paymentFormData}
                      submitted={!!chat.paymentComplete}
                      onPaymentComplete={(result) => {
                        if (result.success && chat.checkoutCardData?.queueItemId) {
                          void axios.post(`/queues/items/${chat.checkoutCardData.queueItemId}/checkout`).catch(() => {});
                        }
                        setChatHistory((prev) => {
                          const next = [...prev];
                          if (next[index]) {
                            next[index].paymentComplete = true;
                            if (next[index].checkoutCardData) next[index].checkoutPaid = true;
                            next[index].text += result.success
                              ? "\n\n✅ **Payment successful!** You are now checked out. Thank you for your payment."
                              : `\n\n❌ **Payment failed:** ${result.error || "Please try again."}`;
                          }
                          return next;
                        });
                        if (result.success) schedulePostPaymentWelcomeReset();
                      }}
                    />
                  )}
                </div>
              ))}

              {isProcessing && !(embedded && compactEmbedded) && (
                <div className="flex items-center gap-2 rounded-2xl border bg-card px-4 py-3 text-sm text-muted-foreground">
                  Thinking
                  <span className="inline-flex gap-1">
                    <span className="size-1.5 animate-pulse rounded-full bg-primary" />
                    <span className="size-1.5 animate-pulse rounded-full bg-primary [animation-delay:150ms]" />
                    <span className="size-1.5 animate-pulse rounded-full bg-primary [animation-delay:300ms]" />
                  </span>
                </div>
              )}

              {interactionMode === "voice" && (isRecording || isTranscribing) && (
                <div className="self-end rounded-2xl rounded-br-md bg-primary px-4 py-3 text-sm text-primary-foreground">
                  {transcript || (isTranscribing ? "Processing audio..." : "Listening...")}
                </div>
              )}
            </div>

            <div className="w-full rounded-2xl border bg-background/80 p-2 shadow-sm backdrop-blur">
              {(interactionMode === "chat" || (!isRecording && !isTranscribing)) && (
                <div className="flex gap-2">
                  <Input
                    ref={chatInputRef}
                    placeholder={interactionMode === "chat" ? "Type your message..." : "Type to ZeroQ..."}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && !event.shiftKey) {
                        event.preventDefault();
                        submitDraft();
                      }
                    }}
                  />
                  <Button size="icon" disabled={isProcessing} onClick={submitDraft} aria-label="Send message">
                    {compactEmbedded ? <Send /> : <Search />}
                  </Button>
                </div>
              )}
            </div>
          </section>

          {embeddedFooter && <div className="absolute bottom-2 right-3 z-10">{embeddedFooter}</div>}

          {activeViewer && (
            <aside className="min-h-0 flex-1 overflow-y-auto rounded-2xl border bg-background/90 p-4 shadow-sm backdrop-blur">
              {activeViewer === "shops" && (
                <div className="flex flex-col gap-4">
                  <h2 className="text-xl font-bold">Nearby Verified Queues</h2>
                  {activeShops.length === 0 ? (
                    <div className="flex flex-col items-center gap-2 py-12 text-center text-muted-foreground">
                      <Search className="size-10" />
                      <p>No shops found.</p>
                    </div>
                  ) : (
                    activeShops.map((shop: any) => (
                      <Card key={shop.id} className="cursor-pointer" onClick={() => {
                        const targetSlug = shop.slug || `shop-${shop.id}`;
                        if (isLocalhost()) navigate(`/shop-ai/${shop.id}`);
                        else window.location.href = constructShopUrl(targetSlug);
                      }}>
                        <CardContent className="flex items-center gap-4 p-4">
                          <Avatar className="size-14 rounded-xl">
                            <AvatarImage src={shop.logo_url} />
                            <AvatarFallback>{shop.name?.[0] || "S"}</AvatarFallback>
                          </Avatar>
                          <div className="min-w-0 flex-1">
                            <p className="truncate font-bold">{shop.name}</p>
                            <p className="truncate text-sm text-muted-foreground">
                              <MapPin className="mr-1 inline size-3" />
                              {[shop.address, shop.city].filter(Boolean).join(", ")}
                            </p>
                          </div>
                          <Button
                            onClick={(event) => {
                              event.stopPropagation();
                              const targetSlug = shop.slug || `shop-${shop.id}`;
                              if (isLocalhost()) navigate(`/shop-ai/${shop.id}`);
                              else window.location.href = constructShopUrl(targetSlug, "/ai");
                            }}
                          >
                            Join
                          </Button>
                        </CardContent>
                      </Card>
                    ))
                  )}
                </div>
              )}
              {activeViewer === "pricing" && <Pricing embedded />}
              {(activeViewer as string) === "testimonials" && <Testimonials embedded />}
              {activeViewer === "features" && <Features embedded />}
              {activeViewer === "faq" && <FAQ embedded />}
              {activeViewer === "register" && (
                <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
                  <Bot className="size-10 text-primary" />
                  <p className="font-bold">Registration runs inline in chat.</p>
                  <p className="max-w-sm text-sm text-muted-foreground">
                    {registrationAccountType ? `Continuing ${registrationAccountType.replace("_", " ")} registration.` : "Ask ZeroQ to register a shop to continue."}
                  </p>
                </div>
              )}
            </aside>
          )}
        </div>
      </div>
    </div>
  );
};

export default MasterAIAgent;
