import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  alpha,
  Box,
  Typography,
  IconButton,
  Fade,
  Stack,
  CircularProgress,
  Card,
  CardContent,
  Button,
  Avatar,
  TextField,
  Chip,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import MicIcon from "@mui/icons-material/Mic";
import MicOffIcon from "@mui/icons-material/MicOff";
import SearchIcon from "@mui/icons-material/Search";
import LocationOnIcon from "@mui/icons-material/LocationOn";
import VolumeUpIcon from "@mui/icons-material/VolumeUp";
import VolumeOffIcon from "@mui/icons-material/VolumeOff";
import axios from "axios";
import { useAudioRecorder } from "../../hooks/useAudioRecorder";
import { useAudioVisualizer } from "../../hooks/useAudioVisualizer";
import ParticleSphere from "../../components/agent/ParticleSphere";
import { useNavigate } from "react-router-dom";
import LightModeIcon from "@mui/icons-material/LightMode";
import DarkModeIcon from "@mui/icons-material/DarkMode";
import ReactMarkdown from "react-markdown";
import ThinkingSteps, { ThinkingStep } from "../../features/agent-inbox/ThinkingSteps";

import Pricing from "./Pricing";
import Features from "./Features";
import FAQ from "./FAQ";
import Testimonials from "./Testimonials";
import VoiceRegistrationFlow from "./VoiceRegistrationFlow";
import InlineRegistrationForm, {
  FormStepData,
  FormDoneData,
} from "./InlineRegistrationForm";
import InlineQueueJoinForm from "./InlineQueueJoinForm";
import { constructShopUrl, isLocalhost } from "../../utils/domainUtils";

type ActionCommand = {
  label: string;
  payload: string;
  relatedViewer?: "pricing" | "features" | "faq" | "shops" | null;
};

type ChatHistoryEntry = {
  role: "ai" | "user";
  text: string;
  shops?: any[];
  formStep?: FormStepData | null;
  formDone?: FormDoneData | null;
  formCompleted?: boolean;
  queueJoinFormData?: any | null;
  queueJoinFormSubmitted?: boolean;
  relatedViewer?: "shops" | "pricing" | "features" | "faq" | "register" | null;
  quickActions?: ActionCommand[];
  thinkingSteps?: ThinkingStep[];
  thinkingComplete?: boolean;
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
  onStreamEvent?: (event: Record<string, any>) => void;
  onChatHistoryChange?: (history: ChatHistoryEntry[]) => void;
};

const PROFESSIONAL_VOICE_INSTRUCT =
  "Speak clearly and naturally with a warm, confident North American English accent. Keep a steady, professional tone and consistent pacing. Enunciate each word precisely.";

const DEFAULT_QUICK_ACTIONS: ActionCommand[] = [
  { label: "Register a Shop", payload: "I want to register a shop" },
  {
    label: "Search for Shops",
    payload: "I want to search for shops",
    relatedViewer: "shops",
  },
  {
    label: "Ask about our Products",
    payload: "Tell me about your products and pricing",
    relatedViewer: "pricing",
  },
];

const getShopQuickActions = (shopName: string): ActionCommand[] => [
  {
    label: "Join Queue",
    payload: `I want to join the queue at ${shopName}`,
  },
  {
    label: "Check Wait Time",
    payload: `What is the current wait time at ${shopName}?`,
  },
  {
    label: "Queue Status",
    payload: "How can I check my queue status?",
  },
];

const ACTIONABLE_PHRASES: Array<ActionCommand & { phrase: string }> = [
  {
    phrase: "cancel registration",
    label: "Cancel Registration",
    payload: "cancel registration",
  },
  {
    phrase: "register a shop",
    label: "Register a Shop",
    payload: "I want to register a shop",
  },
  {
    phrase: "search for shops",
    label: "Search for Shops",
    payload: "I want to search for shops",
    relatedViewer: "shops",
  },
  {
    phrase: "ask about our products",
    label: "Ask about our Products",
    payload: "Tell me about your products and pricing",
    relatedViewer: "pricing",
  },
  {
    phrase: "pricing",
    label: "Pricing",
    payload: "Show me pricing",
    relatedViewer: "pricing",
  },
  {
    phrase: "features",
    label: "Features",
    payload: "Show me features",
    relatedViewer: "features",
  },
  {
    phrase: "faq",
    label: "FAQ",
    payload: "Show me FAQ",
    relatedViewer: "faq",
  },
  {
    phrase: "testimonials",
    label: "Testimonials",
    payload: "Show me testimonials",
  },
];

const extractNodeText = (node: React.ReactNode): string => {
  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }
  if (Array.isArray(node)) {
    return node.map(extractNodeText).join("");
  }
  if (React.isValidElement(node) && "children" in node.props) {
    return extractNodeText(node.props.children);
  }
  return "";
};

const getQuickActionFromListItem = (
  children: React.ReactNode,
): ActionCommand | null => {
  const text = extractNodeText(children).toLowerCase();
  return (
    DEFAULT_QUICK_ACTIONS.find((action) =>
      text.includes(action.label.toLowerCase()),
    ) || null
  );
};

const getActionableCommandFromText = (text: string): ActionCommand | null => {
  const normalized = text.trim().toLowerCase();
  const match = ACTIONABLE_PHRASES.find((item) =>
    normalized.includes(item.phrase),
  );
  return match
    ? {
        label: match.label,
        payload: match.payload,
        relatedViewer: match.relatedViewer ?? null,
      }
    : null;
};

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
  onStreamEvent,
  onChatHistoryChange,
}) => {
  const [isOpen, setIsOpen] = useState(forceOpen || initialOpen);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isToggling, setIsToggling] = useState(false);
  // "voice" = TTS enabled + orb prominent, "chat" = text-only, no TTS audio
  const effectiveInitialMode = disableVoiceMode ? "chat" : initialInteractionMode;
  const [interactionMode, setInteractionMode] = useState<"voice" | "chat">(effectiveInitialMode);
  const interactionModeRef = useRef<"voice" | "chat">(effectiveInitialMode);
  const [location, setLocation] = useState<{ lat: number; lng: number } | null>(
    null,
  );

  // Capture Geolocation
  useEffect(() => {
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) =>
          setLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        (err) =>
          console.warn(
            "[MasterAIAgent] Geolocation denied or unavailable:",
            err,
          ),
      );
    }
  }, []);

  // Session Management
  const [sessionId, setSessionId] = useState<string>("");

  useEffect(() => {
    const sessionKey = shopContext
      ? `zeroq_shop_session_${shopContext.id}`
      : "zeroq_session_id";
    let sid = sessionStorage.getItem(sessionKey);
    if (!sid) {
      sid = Math.random().toString(36).substring(2) + Date.now().toString(36);
      sessionStorage.setItem(sessionKey, sid);
    }
    setSessionId(sid);
  }, [shopContext]);

  // Updated State Type for Dynamic Layout
  const [chatHistory, setChatHistory] = useState<ChatHistoryEntry[]>(() => {
    if (initialChatHistory && initialChatHistory.length > 0) {
      return initialChatHistory;
    }

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
        text: "Welcome to ZeroQwait! I'm ZeroQ. Here's what I can do for you:\n\n1. **Register a Shop** — Set up your business on our platform\n2. **Search for Shops** — Find services nearby and join an AI-powered queue\n3. **Ask about our Products** — Pricing, features, and how it all works\n\nWhat would you like to do?",
        quickActions: DEFAULT_QUICK_ACTIONS,
      },
    ];
  });

  const [activeViewer, setActiveViewer] = useState<
    "shops" | "pricing" | "features" | "faq" | "register" | null
  >(null);
  const [registrationAccountType, setRegistrationAccountType] = useState<
    "customer" | "shop_owner" | null
  >(null);
  const [activeShops, setActiveShops] = useState<any[]>([]);

  // --- Restore active registration on page load/refresh ---
  useEffect(() => {
    if (!sessionId) return;
    const restoreRegistration = async () => {
      try {
        const res = await fetch(
          `/api/agent/registration/state?session_id=${encodeURIComponent(sessionId)}`,
        );
        if (!res.ok) return;
        const state = await res.json();
        if (!state.active || !state.form_step) return;

        // Inject a resumption message + form into chat history
        const stepLabel = state.form_step.prompt || state.form_step.message || `Step: ${state.step}`;
        setChatHistory((prev) => [
          ...prev,
          {
            role: "ai" as const,
            text: `Continuing your registration (step: **${state.step}**). Please complete the form below, or say **cancel registration** to start over.`,
            formStep: state.form_step as FormStepData,
          },
        ]);
      } catch (e) {
        // Silently fail — not critical
        console.warn("Could not check registration state:", e);
      }
    };
    restoreRegistration();
  }, [sessionId]);

  const scrollRef = useRef<HTMLDivElement>(null);
  const latestAIResponse = chatHistory[chatHistory.length - 1];
  const navigate = useNavigate();

  // Ref to hold the submit function (solves circular dependency)
  const submitAudioRef = useRef<() => Promise<void>>();

  // Voice Recorder (Server-Side ASR + Browser Preview + Auto-Submit)
  // Pass wrapper that calls the ref
  const {
    isRecording,
    startRecording,
    stopRecording,
    hasPermission,
    transcript,
  } = useAudioRecorder(() => {
    if (submitAudioRef.current) {
      submitAudioRef.current();
    }
  });

  // Audio Submission Logic (Extracted for Auto-Submit)
  const submitAudio = useCallback(async () => {
    console.log("[MasterAIAgent] submitAudio called.");
    const audioBlob = await stopRecording();
    if (audioBlob) {
      console.log(
        `[MasterAIAgent] Audio blob captured. Size: ${audioBlob.size} bytes. Type: ${audioBlob.type}`,
      );

      // Warn if blob is suspiciously small
      if (audioBlob.size < 1000) {
        console.warn(
          "[MasterAIAgent] Audio blob is very small, might be silence or error.",
        );
      }

      setIsTranscribing(true);
      try {
        const formData = new FormData();
        formData.append("file", audioBlob, "recording.webm");

        console.log("[MasterAIAgent] Sending to /api/voice/transcribe...");
        const response = await axios.post("/voice/transcribe", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });

        console.log("[MasterAIAgent] Transcription response:", response.data);
        const text = response.data.text;

        if (text && text.trim()) {
          console.log("[MasterAIAgent] Valid text received, handling chat...");
          handleChat(text);
        } else {
          console.warn("[MasterAIAgent] No text returned from transcription.");
        }
      } catch (error) {
        console.error("[MasterAIAgent] Transcription request failed:", error);
      } finally {
        setIsTranscribing(false);
      }
    } else {
      console.warn("[MasterAIAgent] stopRecording returned null blob.");
    }
  }, [stopRecording]); // handleChat is stable

  // Update ref whenever submitAudio changes
  useEffect(() => {
    submitAudioRef.current = submitAudio;
  }, [submitAudio]);

  // Audio Visualizer
  const { volume } = useAudioVisualizer(isRecording);

  // Keep interaction mode ref in sync with state
  useEffect(() => {
    interactionModeRef.current = interactionMode;
  }, [interactionMode]);

  // --- Paired-Streaming TTS: synchronized text + audio playback ---
  const audioCtxRef = useRef<AudioContext | null>(null);
  const currentSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);
  // Media queue for paired sentence events: {text, audio}
  const mediaQueueRef = useRef<Array<{ text: string; audio: string | null }>>(
    [],
  );
  const isPlayingQueueRef = useRef(false);
  const cancelQueueRef = useRef(false);
  const lastUserSubmitRef = useRef<{ text: string; at: number }>({
    text: "",
    at: 0,
  });

  const getAudioContext = () => {
    if (!audioCtxRef.current || audioCtxRef.current.state === "closed") {
      audioCtxRef.current = new (
        window.AudioContext || (window as any).webkitAudioContext
      )();
    }
    return audioCtxRef.current;
  };

  /** Decode base64 audio to ArrayBuffer for pre-buffering. */
  const decodeBase64Audio = (base64Audio: string): ArrayBuffer => {
    const binaryStr = atob(base64Audio);
    const bytes = new Uint8Array(binaryStr.length);
    for (let i = 0; i < binaryStr.length; i++) {
      bytes[i] = binaryStr.charCodeAt(i);
    }
    return bytes.buffer.slice(0) as ArrayBuffer;
  };

  /** Play audio from an ArrayBuffer (already base64-decoded). Resolves when playback ends. */
  const playAudio = (base64Audio: string): Promise<void> => {
    return new Promise<void>((resolve) => {
      const safetyTimeout = setTimeout(() => {
        console.warn("[TTS] Audio safety timeout");
        setIsSpeaking(false);
        currentSourceRef.current = null;
        resolve();
      }, 60000);

      try {
        const arrayBuf = decodeBase64Audio(base64Audio);
        const audioCtx = getAudioContext();
        if (audioCtx.state === "suspended") audioCtx.resume();

        audioCtx.decodeAudioData(
          arrayBuf,
          (audioBuffer) => {
            if (cancelQueueRef.current) {
              clearTimeout(safetyTimeout);
              resolve();
              return;
            }
            const source = audioCtx.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioCtx.destination);

            source.onended = () => {
              clearTimeout(safetyTimeout);
              setIsSpeaking(false);
              currentSourceRef.current = null;
              resolve();
            };

            setIsSpeaking(true);
            source.start(0);
            currentSourceRef.current = source;
          },
          (err) => {
            clearTimeout(safetyTimeout);
            console.warn("[TTS] Audio decode error:", err);
            resolve();
          },
        );
      } catch (err) {
        clearTimeout(safetyTimeout);
        console.warn("[TTS] playAudio error:", err);
        resolve();
      }
    });
  };

  /** Typewriter effect: reveal text char-by-char. Resolves when done but does NOT block audio. */
  const typeText = (
    text: string,
    updateFn: (textSoFar: string) => void,
    previousText: string,
  ): Promise<void> => {
    return new Promise<void>((resolve) => {
      let charIndex = 0;
      // 8ms/char = fast enough to keep up with natural speech (~150 WPM)
      const speed = 8;
      const timer = setInterval(() => {
        if (cancelQueueRef.current) {
          clearInterval(timer);
          updateFn(previousText + text);
          resolve();
          return;
        }
        // Reveal 2 chars per tick for long sentences to keep up with audio
        const step = text.length > 80 ? 3 : 2;
        charIndex = Math.min(charIndex + step, text.length);
        updateFn(previousText + text.slice(0, charIndex));
        if (charIndex >= text.length) {
          clearInterval(timer);
          resolve();
        }
      }, speed);
    });
  };

  /** Process the paired media queue: play audio + typewrite text simultaneously per sentence.
   *  Audio drives the pace — typewriter catches up but never blocks next audio. */
  const processMediaQueue = async (aiMsgIndexFn: () => number) => {
    if (isPlayingQueueRef.current) return;
    isPlayingQueueRef.current = true;
    cancelQueueRef.current = false;
    let displayedText = "";

    while (mediaQueueRef.current.length > 0) {
      if (cancelQueueRef.current) break;

      const item = mediaQueueRef.current.shift()!;

      const updateUI = (textSoFar: string) => {
        setChatHistory((prev) => {
          const next = [...prev];
          const idx = next.length - 1;
          if (idx >= 0 && next[idx].role === "ai") {
            next[idx] = { ...next[idx], text: textSoFar };
          }
          return next;
        });
      };

      const prevText = displayedText;

      if (item.audio && interactionModeRef.current === "voice") {
        // Audio-driven: start both, but only wait for audio.
        // Typewriter runs in background and finishes the remaining text
        // when audio ends (so next sentence audio starts without gap).
        const typePromise = typeText(item.text, updateUI, prevText);
        await playAudio(item.audio);
        // Flush remaining typewriter text instantly so display is complete
        updateUI(prevText + item.text);
        // Don't await typePromise — it will resolve on its own
      } else {
        // No audio or chat mode — just typewrite the text
        await typeText(item.text, updateUI, prevText);
      }

      // Add paragraph break between segments for display
      displayedText = prevText + item.text + "\n\n";
    }

    isPlayingQueueRef.current = false;
  };

  /** Stop any currently playing audio and cancel the media queue. */
  const stopCurrentAudio = () => {
    cancelQueueRef.current = true;
    mediaQueueRef.current = [];
    isPlayingQueueRef.current = false;
    // Abort any in-flight speak() TTS fetch
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    try {
      if (currentSourceRef.current) {
        currentSourceRef.current.stop();
        currentSourceRef.current = null;
      }
    } catch (_) {}
    setIsSpeaking(false);
  };

  /** Speak text via backend TTS API (used for welcome message only). */
  const speak = async (text: string) => {
    // Skip TTS in chat mode
    if (interactionModeRef.current === "chat") return;

    stopCurrentAudio();
    cancelQueueRef.current = false;

    // Strip markdown & emojis
    const plainText = text
      .replace(/\*\*(.*?)\*\*/g, "$1")
      .replace(/\*(.*?)\*/g, "$1")
      .replace(/#{1,6}\s/g, "")
      .replace(/`([^`]*)`/g, "$1")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .replace(
        /[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{FE00}-\u{FE0F}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{200D}\u{20E3}\u{E0020}-\u{E007F}]/gu,
        "",
      )
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
        body: JSON.stringify({
          text: plainText,
          voice: "Vivian",
          speed: 0.98,
          model: "tts-1-en",
          language: "English",
          instruct: PROFESSIONAL_VOICE_INSTRUCT,
        }),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`TTS ${response.status}`);
      const arrayBuffer = await response.arrayBuffer();
      const audioCtx = getAudioContext();
      if (audioCtx.state === "suspended") await audioCtx.resume();
      const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
      const source = audioCtx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioCtx.destination);
      await new Promise<void>((resolve) => {
        source.onended = () => {
          setIsSpeaking(false);
          currentSourceRef.current = null;
          resolve();
        };
        source.start(0);
        currentSourceRef.current = source;
      });
    } catch (err: any) {
      if (err?.name !== "AbortError")
        console.warn("[TTS] speak fallback failed:", err);
      setIsSpeaking(false);
      currentSourceRef.current = null;
    }
  };

  const handleVoiceToggle = async () => {
    if (isToggling || isProcessing || isTranscribing) return;

    setIsToggling(true);
    // Safety timeout to prevent infinite loading state if promises hang (e.g. permission prompt ignored)
    const safetyTimer = setTimeout(() => {
      console.warn("[MasterAIAgent] Voice toggle timed out, resetting state");
      setIsToggling(false);
    }, 8000);

    try {
      if (isRecording) {
        await submitAudio();
      } else {
        await startRecording();
      }
    } catch (error) {
      console.error("Voice toggle failed:", error);
    } finally {
      clearTimeout(safetyTimer);
      setIsToggling(false);
    }
  };

  // Theme & Visibility Configuration
  const resolvedPrimary = brandPrimaryColor || "#2563EB";
  const resolvedSecondary = brandSecondaryColor || resolvedPrimary;
  const theme = {
    bg: isDarkMode
      ? `radial-gradient(ellipse 80% 50% at 50% -20%, ${alpha(resolvedPrimary, 0.24)}, #05050A)`
      : `radial-gradient(ellipse 80% 50% at 50% -20%, ${alpha(resolvedPrimary, 0.22)}, ${alpha(resolvedSecondary, 0.08)} 50%, #FFFFFF)`,
    glass: isDarkMode ? "blur(20px)" : "blur(40px)", // Reduced blur for crisper bg visibility
    text: isDarkMode ? "#ffffff" : "#0f172a",
    textSecondary: isDarkMode
      ? "rgba(255, 255, 255, 0.7)"
      : "rgba(15, 23, 42, 0.7)",
    accent: resolvedPrimary,
    cardBg: isDarkMode
      ? "rgba(255, 255, 255, 0.05)"
      : "rgba(255, 255, 255, 0.6)",
    cardBorder: isDarkMode
      ? alpha(resolvedPrimary, 0.24)
      : alpha(resolvedPrimary, 0.16),
    inputBg: isDarkMode
      ? "rgba(255, 255, 255, 0.07)"
      : "rgba(255, 255, 255, 0.8)",
    iconColor: isDarkMode ? "#ffffff" : "#0f172a",
  };

  const shouldRenderVoiceOrb = !(embedded && compactEmbedded && disableVoiceMode);
  const shouldShowShopBadge = !(embedded && compactEmbedded && hideUtilityControls);

  // Visibility & Global Triggers
  useEffect(() => {
    if (forceOpen) {
      setIsOpen(true);
      return;
    }

    const handleToggle = () => {
      console.log("[DEBUG] AI Assistant trigger received");
      setIsOpen((prev) => !prev);
    };
    window.addEventListener("trigger-zeroq-assistant", handleToggle);

    return () => {
      window.removeEventListener("trigger-zeroq-assistant", handleToggle);
    };
  }, [forceOpen]);

  // Note: Initial greeting is NOT spoken here — it will be spoken via
  // paired streaming when user sends first message (avoids duplicate voice).
  // The welcome text is pre-set in chatHistory as a text-only bubble.

  // --- Registration Inline Form Result Handler ---
  const handleFormResult = useCallback(
    (result: FormStepData | FormDoneData, sourceIndex: number) => {
      // Mark the current form step as completed
      setChatHistory((prev) => {
        const next = [...prev];
        if (next[sourceIndex]) {
          next[sourceIndex].formCompleted = true;
        }
        return next;
      });

      if (result.type === "form_step") {
        // Next step — add a new AI message with the form
        const nextStep = result as FormStepData;
        const aiMessage = nextStep.message || nextStep.prompt || "Next step:";
        setChatHistory((prev) => [
          ...prev,
          {
            role: "ai" as const,
            text: aiMessage,
            formStep: nextStep,
          },
        ]);
        // Speak the prompt
        if (nextStep.prompt) {
          speak(nextStep.prompt);
        }
      } else if (result.type === "form_done") {
        // Registration complete
        const done = result as FormDoneData;
        const successText = done.success
          ? done.message
          : `Registration failed: ${done.message}`;
        setChatHistory((prev) => [
          ...prev,
          {
            role: "ai" as const,
            text: successText,
            formDone: done,
          },
        ]);
        speak(successText);
      }
    },
    [speak],
  );

  // --- Queue Join Form Result Handler ---
  const handleQueueJoinFormSubmit = useCallback(
    (result: { success: boolean; queueItemId?: number; position?: number; error?: string }, sourceIndex: number) => {
      // Mark the current form as submitted
      setChatHistory((prev) => {
        const next = [...prev];
        if (next[sourceIndex]) {
          next[sourceIndex].queueJoinFormSubmitted = true;
          
          if (result.success) {
            next[sourceIndex].text += `\n\n✅ **Great!** You've been added to the queue. Your position: #${result.position}`;
            if (shopContext && result.queueItemId) {
              localStorage.setItem(
                `queue_item_${shopContext.id}`,
                String(result.queueItemId),
              );
            }
            // Navigate to queue page after a short delay
            setTimeout(() => {
              if (shopContext) {
                navigate(`/queue/${shopContext.id}`);
              }
            }, 1500);
          } else {
            next[sourceIndex].text += `\n\n❌ Error: ${result.error || 'Failed to join queue'}`;
          }
        }
        return next;
      });
    },
    [shopContext, navigate],
  );

  const handleChat = async (
    userText: string,
    requestedViewer?: "shops" | "pricing" | "features" | "faq" | null,
  ) => {
    if (!userText.trim()) return;

    const normalized = userText.trim().toLowerCase();
    const now = Date.now();
    if (
      lastUserSubmitRef.current.text === normalized &&
      now - lastUserSubmitRef.current.at < 900
    ) {
      return;
    }
    lastUserSubmitRef.current = { text: normalized, at: now };

    const nextViewer = requestedViewer ?? activeViewer;
    const nextShops = nextViewer === "shops" ? activeShops : [];

    // Cancel any in-progress playback
    stopCurrentAudio();

    setChatHistory((prev) => [...prev, { role: "user", text: userText }]);
    setIsProcessing(true);

    const aiMessageIndex = chatHistory.length + 1;

    // Add empty AI message placeholder
    setChatHistory((prev) => [
      ...prev,
      {
        role: "ai",
        text: "",
        shops: nextShops,
        relatedViewer: nextViewer,
        thinkingSteps: [],
        thinkingComplete: false,
      },
    ]);

    try {
      const response = await fetch(streamEndpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(requestHeaders || {}),
        },
        body: JSON.stringify({
          message: userText,
          session_id: sessionId,
          latitude: location?.lat,
          longitude: location?.lng,
          history: chatHistory.map((h) => ({
            role: h.role === "ai" ? "assistant" : "user",
            content: h.text,
          })),
          context: {
            active_view: nextViewer,
            visible_shops: nextShops.map((s) => s.name),
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
          is_voice: interactionMode === "voice",
          ...(extraRequestBody || {}),
        }),
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(`Server error ${response.status}: ${errText}`);
      }
      if (!response.body) throw new Error("No response body");

      setIsProcessing(false);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      // Reset media queue for this response
      mediaQueueRef.current = [];
      cancelQueueRef.current = false;
      isPlayingQueueRef.current = false;

      let sseBuffer = ""; // Buffer for incomplete SSE lines

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        sseBuffer += decoder.decode(value, { stream: true });
        const lines = sseBuffer.split("\n");
        // Keep the last incomplete line in the buffer
        sseBuffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const dataStr = line.slice(6);
          if (dataStr === "[DONE]") {
            // Mark thinking pipeline complete
            setChatHistory((prev) => {
              const next = [...prev];
              const idx = next.length - 1;
              if (idx >= 0 && next[idx].role === "ai") {
                next[idx] = { ...next[idx], thinkingComplete: true };
              }
              return next;
            });
            continue;
          }

          try {
            const data = JSON.parse(dataStr);
            if (onStreamEvent) {
              onStreamEvent(data);
            }

            if (data.type === "sentence") {
              // --- Paired sentence event: {text, audio} ---
              const sentenceText = data.text || "";
              const audioB64 = data.audio || null;

              console.log(
                `[SSE] Sentence received: "${sentenceText.slice(0, 40)}..." audio=${audioB64 ? "yes" : "no"}`,
              );

              // Push to media queue
              mediaQueueRef.current.push({
                text: sentenceText,
                audio: audioB64,
              });

              // Start or restart the media queue processor
              // (it may have finished before this event arrived)
              if (!isPlayingQueueRef.current) {
                processMediaQueue(() => aiMessageIndex);
              }
            } else if (data.type === "text") {
              // Legacy text-only event (fallback compatibility)
              const newText = data.content;
              setChatHistory((prev) => {
                const next = [...prev];
                const idx = next.length - 1;
                if (idx >= 0 && next[idx].role === "ai") {
                  next[idx] = {
                    ...next[idx],
                    text: (next[idx].text || "") + newText,
                  };
                }
                return next;
              });
            } else if (data.type === "thinking_step") {
              // Real-time reasoning pipeline step from LangGraph astream_events
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
                  const pos = existing.findIndex((s) => s.id === incoming.id);
                  const updated =
                    pos >= 0
                      ? existing.map((s) => (s.id === incoming.id ? incoming : s))
                      : [...existing, incoming];
                  next[idx] = { ...next[idx], thinkingSteps: updated };
                }
                return next;
              });
            } else if (data.type === "tool_call") {
              const toolName = String(data.tool_name || data.tool || "unknown_tool");
              const toolStepId = `tool-${toolName}-${Date.now()}`;

              setChatHistory((prev) => {
                const next = [...prev];
                const idx = next.length - 1;
                if (idx >= 0 && next[idx].role === "ai") {
                  const existing = [...(next[idx].thinkingSteps ?? [])];
                  const updatedExisting = existing.map((s, i) => {
                    if (i === existing.length - 1 && s.status === "active") {
                      return { ...s, status: "completed" as const };
                    }
                    return s;
                  });

                  const toolStep: ThinkingStep = {
                    id: toolStepId,
                    label: `Calling ${toolName}...`,
                    status: "active",
                    toolName,
                  };

                  next[idx] = {
                    ...next[idx],
                    thinkingSteps: [...updatedExisting, toolStep],
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
                  const targetIndex = [...existing]
                    .map((s, i) => ({ s, i }))
                    .reverse()
                    .find(({ s }) => s.toolName === toolName && s.status === "active")?.i;

                  if (typeof targetIndex === "number") {
                    const target = existing[targetIndex];
                    existing[targetIndex] = {
                      ...target,
                      status: hasError ? "error" : "completed",
                      label: hasError
                        ? `${target.label.replace(/\.\.\.$/, "")} failed`
                        : target.label,
                    };
                    next[idx] = { ...next[idx], thinkingSteps: existing };
                  }
                }
                return next;
              });
            } else if (data.type === "error") {
              const errText =
                data.content || "Something went wrong. Please try again.";
              setChatHistory((prev) => {
                const next = [...prev];
                const idx = next.length - 1;
                if (idx >= 0 && next[idx].role === "ai") {
                  next[idx] = {
                    ...next[idx],
                    text: (next[idx].text || "") + errText,
                  };
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
                    const shops = Array.isArray(action.result)
                      ? action.result
                      : action.result?.shops || [];
                    if (shops.length > 0) {
                      currentShops = shops;
                      currentViewer = "shops";
                    }
                  } else if (action.tool === "start_registration") {
                    // Registration is now handled via inline form_step events.
                    // Don't open the side panel viewer anymore.
                    const accountType = action.result?.account_type;
                    setRegistrationAccountType(
                      accountType === "shop_owner" || accountType === "customer"
                        ? accountType
                        : null,
                    );
                    // Note: form_step SSE event (received separately) will add the inline form
                  } else if (
                    action.tool === "join_queue" &&
                    action.result?.success
                  ) {
                    const queueItemId = action.result?.queue_item_id;
                    const joinedShopId =
                      action.params?.shop_id || shopContext?.id;

                    if (queueItemId && joinedShopId) {
                      localStorage.setItem(
                        `queue_item_${joinedShopId}`,
                        String(queueItemId),
                      );
                    }

                    if (joinedShopId) {
                      setTimeout(() => navigate(`/queue/${joinedShopId}`), 1200);
                    }
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
              // --- Inline registration form step ---
              // Attach the form schema to the current AI message
              const formStepData = data as FormStepData;
              console.log(
                `[SSE] form_step received: step=${formStepData.step}`,
              );
              setChatHistory((prev) => {
                const next = [...prev];
                if (next[aiMessageIndex]) {
                  next[aiMessageIndex].formStep = formStepData;
                }
                return next;
              });
            } else if (data.type === "queue_join_form") {
              // --- Inline queue join form ---
              // Attach queue join form data to the current AI message
              console.log(`[SSE] queue_join_form received for shop: ${data.shop_id}`);
              setChatHistory((prev) => {
                const next = [...prev];
                if (next[aiMessageIndex]) {
                  next[aiMessageIndex].queueJoinFormData = data;
                }
                return next;
              });
            }
          } catch (e) {
            console.warn("Failed to parse SSE data chunk:", dataStr);
          }
        }
      } // end SSE loop

      // If queue has unprocessed items after SSE loop ends, ensure processing
      if (!isPlayingQueueRef.current && mediaQueueRef.current.length > 0) {
        processMediaQueue(() => aiMessageIndex);
      }
    } catch (error) {
      console.error("[DEBUG] MasterAgent API Stream Error:", error);
      setIsProcessing(false);
      setChatHistory((prev) => {
        const next = [...prev];
        if (next[aiMessageIndex]) {
          next[aiMessageIndex].text =
            "I encountered an error trying to process that request.";
        }
        return next;
      });
    }
  };

  const handleActionCommand = (action: ActionCommand) => {
    if (action.relatedViewer) {
      setActiveViewer(action.relatedViewer);
      if (action.relatedViewer !== "shops") {
        setActiveShops([]);
      }
    }

    void handleChat(action.payload, action.relatedViewer ?? undefined);
  };

  // Auto-scroll to bottom of chat
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [chatHistory]);

  useEffect(() => {
    if (onChatHistoryChange) {
      onChatHistoryChange(chatHistory);
    }
  }, [chatHistory, onChatHistoryChange]);

  return (
    <Fade in={isOpen}>
      <Box
        id="immersive-ai-overlay"
        sx={{
          position: embedded ? "relative" : "fixed",
          top: 0,
          left: 0,
          width: embedded ? "100%" : "100vw",
          height: embedded ? "100%" : { xs: "100dvh", md: "100vh" },
          zIndex: embedded ? 1 : 10000,
          background: theme.bg,
          backdropFilter: theme.glass,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "flex-start",
          color: theme.text,
          overflow: "hidden", // Changed to hidden - scrolling happens inside child
          transition: "all 0.5s ease",
          borderRadius: embedded ? "20px" : 0,
          border: embedded ? `1px solid ${theme.cardBorder}` : "none",
        }}
      >
        {/* Controls Top Right */}
        <Stack
          direction="row"
          spacing={2}
          sx={{
            position: "absolute",
            top: embedded ? { xs: 12, sm: 14 } : 40,
            right: embedded ? { xs: 12, sm: 14 } : 40,
            zIndex: 20000,
          }}
        >
          {!hideUtilityControls && (
            <>
              <IconButton
                onClick={() => setIsDarkMode(!isDarkMode)}
                sx={{
                  color: theme.iconColor,
                  bgcolor: isDarkMode
                    ? "rgba(255,255,255,0.05)"
                    : "rgba(15,23,42,0.05)",
                  "&:hover": {
                    bgcolor: isDarkMode
                      ? "rgba(255,255,255,0.1)"
                      : "rgba(15,23,42,0.1)",
                  },
                }}
              >
                {isDarkMode ? (
                  <LightModeIcon sx={{ fontSize: 24 }} />
                ) : (
                  <DarkModeIcon sx={{ fontSize: 24 }} />
                )}
              </IconButton>
              {!disableVoiceMode && (
                <Box
                  onClick={() => {
                    const newMode = interactionMode === "voice" ? "chat" : "voice";
                    if (newMode === "chat") {
                      stopCurrentAudio();
                      if (isRecording) stopRecording();
                    }
                    setInteractionMode(newMode);
                  }}
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 0.5,
                    px: 1.5,
                    py: 0.75,
                    borderRadius: "20px",
                    cursor: "pointer",
                    bgcolor: isDarkMode
                      ? "rgba(255,255,255,0.05)"
                      : "rgba(15,23,42,0.05)",
                    border: `1px solid ${interactionMode === "voice" ? theme.accent + "44" : theme.cardBorder}`,
                    transition: "all 0.2s ease",
                    "&:hover": {
                      bgcolor: isDarkMode
                        ? "rgba(255,255,255,0.1)"
                        : "rgba(15,23,42,0.1)",
                    },
                  }}
                >
                  {interactionMode === "voice" ? (
                    <VolumeUpIcon sx={{ fontSize: 18, color: theme.accent }} />
                  ) : (
                    <VolumeOffIcon sx={{ fontSize: 18, color: theme.textSecondary }} />
                  )}
                  <Typography
                    variant="caption"
                    sx={{
                      fontWeight: 600,
                      fontSize: "0.65rem",
                      letterSpacing: "0.05em",
                      color: interactionMode === "voice" ? theme.accent : theme.textSecondary,
                      userSelect: "none",
                    }}
                  >
                    {interactionMode === "voice" ? "VOICE" : "CHAT"}
                  </Typography>
                </Box>
              )}
            </>
          )}
          {!hideCloseButton && !forceOpen && (
            <IconButton
              onClick={() => setIsOpen(false)}
              sx={{
                color: theme.iconColor,
                bgcolor: isDarkMode
                  ? "rgba(255,255,255,0.05)"
                  : "rgba(15,23,42,0.05)",
                "&:hover": {
                  bgcolor: isDarkMode
                    ? "rgba(255,255,255,0.1)"
                    : "rgba(15,23,42,0.1)",
                },
              }}
            >
              <CloseIcon sx={{ fontSize: 32 }} />
            </IconButton>
          )}
        </Stack>

        {shopContext && shouldShowShopBadge && (
          <Box
            sx={{
              position: "absolute",
              top: embedded ? { xs: 12, sm: 14 } : { xs: 20, sm: 24, md: 28 },
              left: embedded ? { xs: 12, sm: 14 } : { xs: 16, sm: 20, md: 28 },
              zIndex: 20000,
              px: { xs: 1.5, sm: 2 },
              py: 1,
              borderRadius: "14px",
              border: `1px solid ${theme.cardBorder}`,
              bgcolor: isDarkMode
                ? "rgba(255,255,255,0.05)"
                : "rgba(255,255,255,0.85)",
              backdropFilter: "blur(8px)",
              maxWidth: embedded
                ? { xs: "62%", sm: "58%", md: "52%" }
                : { xs: "68vw", sm: "60vw", md: "40vw" },
            }}
          >
            <Typography
              variant="caption"
              sx={{
                display: "block",
                letterSpacing: "0.08em",
                fontWeight: 700,
                color: theme.textSecondary,
                mb: 0.25,
              }}
            >
              NOW CHATTING WITH
            </Typography>
            <Typography
              variant="subtitle2"
              sx={{
                fontWeight: 700,
                color: theme.accent,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {shopContext.name}
            </Typography>
            {(shopContext.city || shopContext.shopType) && (
              <Typography
                variant="caption"
                sx={{ color: theme.textSecondary }}
              >
                {[shopContext.city, shopContext.shopType]
                  .filter(Boolean)
                  .join(" • ")}
              </Typography>
            )}
          </Box>
        )}

        <Box
          sx={{
            flex: 1,
            width: "100%",
            overflowY: "auto",
            overflowX: "hidden",
            display: "flex",
            flexDirection: "column",
            position: "relative",
            zIndex: 1,
            "&::-webkit-scrollbar": { width: "6px" },
            "&::-webkit-scrollbar-track": { background: "transparent" },
            "&::-webkit-scrollbar-thumb": {
              background: isDarkMode
                ? "rgba(255,255,255,0.1)"
                : "rgba(0,0,0,0.1)",
              borderRadius: "10px",
            },
          }}
        >
          {/* Main Content Wrapper - Centers or Splits */}
          <Box
            sx={{
              flex: 1,
              display: "flex",
              flexDirection: activeViewer
                ? { xs: "column", md: "row" }
                : "column",
              // CHANGED: Center vertically in both single and split view
              alignItems: "center",
              justifyContent: "center",
              py: embedded && compactEmbedded ? { xs: 0.5, md: 1 } : { xs: 2, sm: 3, md: 4 },
              px: { xs: 2, sm: 3, md: 4, lg: 6 },
              gap: embedded && compactEmbedded ? { xs: 1, md: 1.5 } : { xs: 3, sm: 3, md: 4 },
              width: "100%",
              // WIDER CONTAINER for Split View (Monitor Mode)
              // Constrained to 1400px for better balance on large screens
              maxWidth: activeViewer ? "1400px" : "800px",
              m: "auto", // Safe centering that handles overflow correctly
              // Removed minHeight: '100%' which was causing clipping issues
              transition: "all 0.5s cubic-bezier(0.4, 0, 0.2, 1)",
            }}
          >
            {/* CHAT COLUMN: Agent, Transcript & Controls */}
            <Box
              sx={{
                // FIXED WIDTH for Chat in Split View
                flex: activeViewer
                  ? { xs: "1 1 auto", md: "0 0 400px" }
                  : "none",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "flex-start",
                gap: embedded && compactEmbedded ? { xs: 1, md: 1.25 } : { xs: 2, sm: 2.5, md: 3 },
                transition: "all 0.5s cubic-bezier(0.4, 0, 0.2, 1)",
                width: "100%",
                // Fixed width constraint
                maxWidth: activeViewer
                  ? { xs: "100%", md: "400px" }
                  : { xs: "100%", sm: "500px", md: "600px" },
                height: activeViewer
                  ? { xs: "calc(100dvh - 170px)", md: "70vh" }
                  : embedded && compactEmbedded
                    ? { xs: "calc(100dvh - 150px)", md: "72vh" }
                    : { xs: "calc(100dvh - 170px)", md: "78vh" },
                position: "relative",
                py: embedded && compactEmbedded ? { xs: 0, md: 0.5 } : { xs: 1, md: 2 },
                order: { xs: 0, md: activeViewer ? 1 : 0 },
              }}
            >
              {/* Clickable Orb for Voice Activation */}
              {shouldRenderVoiceOrb && (
              <Box
                onClick={interactionMode === "voice" ? handleVoiceToggle : undefined}
                sx={{
                  position: "relative",
                  width: interactionMode === "chat"
                    ? { xs: 60, sm: 70, md: 80 }
                    : activeViewer
                      ? { xs: 80, sm: 100, md: 120 }
                      : { xs: 150, sm: 180, md: 220 },
                  height: interactionMode === "chat"
                    ? { xs: 60, sm: 70, md: 80 }
                    : activeViewer
                      ? { xs: 80, sm: 100, md: 120 }
                      : { xs: 150, sm: 180, md: 220 },
                  transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
                  flexShrink: 0,
                  mb: interactionMode === "chat" ? 1 : activeViewer ? 1 : 2,
                  cursor: interactionMode === "chat"
                    ? "default"
                    : isTranscribing || isToggling ? "wait" : "pointer",
                  opacity: interactionMode === "chat" ? 0.6 : isToggling ? 0.7 : 1,
                  animation: isProcessing
                    ? "orbPulse 1.5s ease-in-out infinite"
                    : isRecording
                      ? "orbGlow 1s ease-in-out infinite"
                      : "none",
                  "@keyframes orbPulse": {
                    "0%, 100%": { transform: "scale(1)", opacity: 1 },
                    "50%": { transform: "scale(1.08)", opacity: 0.85 },
                  },
                  "@keyframes orbGlow": {
                    "0%, 100%": {
                      filter: `drop-shadow(0 0 20px ${theme.accent}66)`,
                    },
                    "50%": {
                      filter: `drop-shadow(0 0 40px ${theme.accent}aa)`,
                    },
                  },
                  "&:hover": {
                    transform:
                      isTranscribing || isToggling ? "none" : "scale(1.05)",
                    filter:
                      isTranscribing || isToggling
                        ? "none"
                        : `brightness(1.1) drop-shadow(0 0 25px ${theme.accent}55)`,
                  },
                  "&:active": {
                    transform:
                      isTranscribing || isToggling ? "none" : "scale(0.98)",
                  },
                }}
              >
                <Box
                  sx={{ pointerEvents: "none", width: "100%", height: "100%" }}
                >
                  <ParticleSphere
                    volume={volume}
                    isListening={isRecording}
                    color={theme.accent}
                    isProcessing={isProcessing}
                  />
                </Box>

                {/* Mic Icon Overlay - shows on hover or when idle (voice mode only) */}
                {!disableVoiceMode && interactionMode === "voice" && (
                <Box
                  sx={{
                    position: "absolute",
                    top: "50%",
                    left: "50%",
                    transform: "translate(-50%, -50%)",
                    opacity:
                      isRecording ||
                      isProcessing ||
                      isTranscribing ||
                      isToggling
                        ? 0
                        : 0.4,
                    transition: "opacity 0.3s ease",
                    pointerEvents: "none",
                    "& svg": {
                      fontSize: activeViewer
                        ? { xs: 24, md: 32 }
                        : { xs: 40, md: 56 },
                      color: theme.text,
                    },
                    ".MuiBox-root:hover > &": {
                      opacity:
                        isRecording ||
                        isProcessing ||
                        isTranscribing ||
                        isToggling
                          ? 0
                          : 0.7,
                    },
                  }}
                >
                  {isToggling ? (
                    <CircularProgress size={30} sx={{ color: theme.accent }} />
                  ) : isRecording ? (
                    <MicIcon />
                  ) : (
                    <MicOffIcon />
                  )}
                </Box>
                )}
              </Box>
              )}

              {/* Voice Status Indicator - below orb */}
              {shouldRenderVoiceOrb && (
              <Typography
                variant="caption"
                sx={{
                  opacity:
                    interactionMode === "chat" ? 0.4
                    : isRecording || isTranscribing || isToggling ? 1 : 0.5,
                  letterSpacing: "0.1em",
                  fontWeight: 600,
                  minHeight: "20px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color:
                    interactionMode === "chat" ? theme.textSecondary
                    : isRecording || isTranscribing || isToggling
                      ? theme.accent
                      : theme.textSecondary,
                  transition: "all 0.2s ease",
                  textAlign: "center",
                  fontSize: { xs: "0.65rem", sm: "0.7rem", md: "0.75rem" },
                  mb: 1,
                  cursor: interactionMode === "voice" ? "pointer" : "default",
                  "&:hover": {
                    opacity: 1,
                  },
                }}
                onClick={!disableVoiceMode && interactionMode === "voice" ? handleVoiceToggle : undefined}
              >
                {interactionMode === "chat"
                  ? "CHAT MODE"
                  : isTranscribing
                    ? "TRANSCRIBING..."
                    : isRecording
                      ? transcript || "LISTENING..."
                      : "TAP ORB TO SPEAK"}
              </Typography>
              )}

              <Box
                ref={scrollRef}
                sx={{
                  width: "100%",
                  flex: 1,
                  minHeight: 0,
                  overflowY: "auto",
                  display: "flex",
                  flexDirection: "column",
                  gap: 1.5,
                  px: { xs: 1, sm: 1.5, md: 2 },
                  py: 1,
                  maskImage:
                    "linear-gradient(to bottom, transparent, black 8%, black 92%, transparent)",
                  WebkitMaskImage:
                    "linear-gradient(to bottom, transparent, black 8%, black 92%, transparent)",
                  "&::-webkit-scrollbar": { width: "4px" },
                  "&::-webkit-scrollbar-thumb": {
                    background: isDarkMode
                      ? "rgba(255,255,255,0.2)"
                      : "rgba(0,0,0,0.15)",
                    borderRadius: "4px",
                  },
                }}
              >
                {chatHistory.map((chat, index) => (
                  <Box
                    key={index}
                    sx={{
                      width: "100%",
                      display: "flex",
                      flexDirection: "column",
                      alignItems:
                        chat.role === "user" ? "flex-end" : "flex-start",
                      opacity: index < chatHistory.length - 2 ? 0.75 : 1,
                      transition: "opacity 0.3s ease",
                    }}
                  >
                    <Box
                      sx={{
                        bgcolor:
                          chat.role === "user" ? theme.accent : theme.cardBg,
                        color:
                          chat.role === "user"
                            ? isDarkMode
                              ? "#000"
                              : "#fff"
                            : theme.text,
                        py: { xs: 1.5, md: 2 },
                        px: { xs: 2, md: 2.5 },
                        borderRadius:
                          chat.role === "user"
                            ? "20px 20px 4px 20px"
                            : "20px 20px 20px 4px",
                        maxWidth: { xs: "88%", sm: "85%", md: "85%" },
                        border:
                          chat.role === "user"
                            ? "none"
                            : `1px solid ${theme.cardBorder}`,
                        boxShadow:
                          chat.role === "user"
                            ? "0 2px 8px rgba(0,0,0,0.1)"
                            : "0 2px 12px rgba(0,0,0,0.05)",
                        "& p": {
                          m: 0,
                          mb: 0.75,
                          lineHeight: 1.5,
                          fontSize: { xs: "0.9rem", sm: "0.95rem", md: "1rem" },
                        },
                        "& p:last-child": { mb: 0 },
                        "& ul, & ol": { pl: 2, m: 0, mb: 0.75 },
                        "& li": {
                          mb: 0.25,
                          fontSize: {
                            xs: "0.85rem",
                            sm: "0.9rem",
                            md: "0.95rem",
                          },
                        },
                        "& strong": {
                          fontWeight: 600,
                          color:
                            chat.role === "user" ? "inherit" : theme.accent,
                        },
                      }}
                    >
                      {chat.role === "user" ? (
                        <Typography
                          variant="body1"
                          sx={{
                            fontSize: { xs: "0.9rem", md: "1rem" },
                            fontWeight: 500,
                          }}
                        >
                          {chat.text}
                        </Typography>
                      ) : (
                        <>
                          {chat.thinkingSteps && chat.thinkingSteps.length > 0 && (
                            <ThinkingSteps
                              steps={chat.thinkingSteps}
                              isComplete={chat.thinkingComplete ?? false}
                              accentColor={theme.accent}
                            />
                          )}
                          {chat.text && (
                            <ReactMarkdown
                              components={{
                                li: ({ children }) => {
                                  const action = getQuickActionFromListItem(children);
                                  if (!action) {
                                    return <li>{children}</li>;
                                  }
                                  return (
                                    <li>
                                      <Box
                                        component="button"
                                        type="button"
                                        onClick={() => {
                                          if (!isProcessing) {
                                            handleActionCommand(action);
                                          }
                                        }}
                                        sx={{
                                          border: "none",
                                          bgcolor: "transparent",
                                          p: 0,
                                          m: 0,
                                          textAlign: "left",
                                          width: "100%",
                                          cursor: isProcessing ? "not-allowed" : "pointer",
                                          color: "inherit",
                                          "&:hover": {
                                            opacity: 0.9,
                                          },
                                        }}
                                      >
                                        {children}
                                      </Box>
                                    </li>
                                  );
                                },
                                strong: ({ children }) => {
                                  const plain = extractNodeText(children);
                                  const action = getActionableCommandFromText(plain);

                                  if (!action) {
                                    return <strong>{children}</strong>;
                                  }

                                  return (
                                    <Box
                                      component="span"
                                      role="button"
                                      tabIndex={0}
                                      onClick={(event) => {
                                        event.preventDefault();
                                        event.stopPropagation();
                                        if (!isProcessing) {
                                          handleActionCommand(action);
                                        }
                                      }}
                                      onKeyDown={(event) => {
                                        if (event.key === "Enter" || event.key === " ") {
                                          event.preventDefault();
                                          event.stopPropagation();
                                          if (!isProcessing) {
                                            handleActionCommand(action);
                                          }
                                        }
                                      }}
                                      sx={{
                                        border: "none",
                                        bgcolor: "transparent",
                                        p: 0,
                                        m: 0,
                                        font: "inherit",
                                        fontWeight: 600,
                                        color: theme.accent,
                                        cursor: isProcessing ? "not-allowed" : "pointer",
                                        textDecoration: "underline",
                                        textDecorationThickness: "1px",
                                        textUnderlineOffset: "2px",
                                        "&:hover": {
                                          opacity: 0.85,
                                        },
                                      }}
                                    >
                                      {children}
                                    </Box>
                                  );
                                },
                              }}
                            >
                              {chat.text}
                            </ReactMarkdown>
                          )}
                          {((chat.quickActions && chat.quickActions.length > 0) ||
                            (chat.role === "ai" &&
                              chat.text.includes("Register a Shop") &&
                              chat.text.includes("Search for Shops") &&
                              chat.text.includes("Ask about our Products"))) && (
                            <Box
                              sx={{
                                display: "flex",
                                flexWrap: "wrap",
                                gap: 1,
                                mt: 1.5,
                              }}
                            >
                              {(chat.quickActions && chat.quickActions.length > 0
                                ? chat.quickActions
                                : DEFAULT_QUICK_ACTIONS
                              ).map((action) => (
                                <Chip
                                  key={action.label}
                                  label={action.label}
                                  onClick={() => handleActionCommand(action)}
                                  disabled={isProcessing}
                                  size="small"
                                  sx={{
                                    cursor: "pointer",
                                    fontWeight: 600,
                                    fontSize: "0.8rem",
                                    borderRadius: "20px",
                                    border: `1px solid ${theme.accent}`,
                                    color: theme.accent,
                                    bgcolor: "transparent",
                                    transition: "all 0.2s ease",
                                    "&:hover": {
                                      bgcolor: theme.accent,
                                      color: isDarkMode ? "#000" : "#fff",
                                    },
                                  }}
                                />
                              ))}
                            </Box>
                          )}
                          {chat.formDone && chat.formDone.success && (
                            <Box
                              sx={{
                                mt: 1.5,
                                p: 2,
                                bgcolor: isDarkMode
                                  ? "rgba(76,175,80,0.1)"
                                  : "rgba(76,175,80,0.08)",
                                borderRadius: "12px",
                                border: "1px solid rgba(76,175,80,0.3)",
                              }}
                            >
                              <Typography
                                variant="body2"
                                sx={{
                                  fontWeight: 600,
                                  color: "#4caf50",
                                  mb: 0.5,
                                }}
                              >
                                Registration Complete!
                              </Typography>
                              {chat.formDone.shop && (
                                <Typography
                                  variant="caption"
                                  sx={{ color: theme.textSecondary }}
                                >
                                  Shop "{chat.formDone.shop.name}" is live at /
                                  {chat.formDone.shop.slug}
                                </Typography>
                              )}
                            </Box>
                          )}
                        </>
                      )}
                    </Box>
                    {/* Inline registration form (rendered BELOW the message bubble, inside the same chat row) */}
                    {chat.formStep && (
                      <Box
                        sx={{
                          width: "100%",
                          maxWidth: { xs: "96%", sm: "90%", md: "85%" },
                          mt: 1,
                        }}
                      >
                        <InlineRegistrationForm
                          formStep={chat.formStep}
                          sessionId={sessionId}
                          theme={theme}
                          isDarkMode={isDarkMode}
                          disabled={!!chat.formCompleted}
                          onFormResult={(result) =>
                            handleFormResult(result, index)
                          }
                        />
                      </Box>
                    )}
                    {/* Inline queue join form (rendered BELOW the message bubble, inside the same chat row) */}
                    {chat.queueJoinFormData && !chat.queueJoinFormSubmitted && (
                      <Box
                        sx={{
                          width: "100%",
                          maxWidth: { xs: "96%", sm: "90%", md: "85%" },
                          mt: 1,
                        }}
                      >
                        <InlineQueueJoinForm
                          shopId={chat.queueJoinFormData.shop_id}
                          shopName={chat.queueJoinFormData.shop_name}
                          shopType={chat.queueJoinFormData.shop_type}
                          sessionId={sessionId}
                          theme={theme}
                          isDarkMode={isDarkMode}
                          disabled={!!chat.queueJoinFormSubmitted}
                          onFormSubmit={(result) =>
                            handleQueueJoinFormSubmit(result, index)
                          }
                        />
                      </Box>
                    )}
                  </Box>
                ))}
                {/* Thinking indicator - shows in chat while processing */}
                {isProcessing && (
                  <Box
                    sx={{
                      width: "100%",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "flex-start",
                      animation: "fadeIn 0.3s ease",
                    }}
                  >
                    <Box
                      sx={{
                        bgcolor: theme.cardBg,
                        color: theme.textSecondary,
                        py: { xs: 1.5, md: 2 },
                        px: { xs: 2, md: 2.5 },
                        borderRadius: "20px 20px 20px 4px",
                        maxWidth: { xs: "70%", sm: "60%" },
                        border: `1px solid ${theme.cardBorder}`,
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                      }}
                    >
                      <Typography
                        variant="body2"
                        sx={{
                          fontStyle: "italic",
                          fontSize: { xs: "0.85rem", md: "0.95rem" },
                          display: "flex",
                          alignItems: "center",
                          gap: 0.5,
                        }}
                      >
                        Thinking
                        <Box
                          component="span"
                          sx={{
                            display: "inline-flex",
                            gap: "2px",
                            "& span": {
                              width: 4,
                              height: 4,
                              borderRadius: "50%",
                              bgcolor: theme.accent,
                              animation: "dotBounce 1.4s ease-in-out infinite",
                            },
                            "& span:nth-of-type(1)": { animationDelay: "0s" },
                            "& span:nth-of-type(2)": { animationDelay: "0.2s" },
                            "& span:nth-of-type(3)": { animationDelay: "0.4s" },
                            "@keyframes dotBounce": {
                              "0%, 80%, 100%": { transform: "translateY(0)" },
                              "40%": { transform: "translateY(-6px)" },
                            },
                            "@keyframes fadeIn": {
                              from: {
                                opacity: 0,
                                transform: "translateY(8px)",
                              },
                              to: { opacity: 1, transform: "translateY(0)" },
                            },
                          }}
                        >
                          <span />
                          <span />
                          <span />
                        </Box>
                      </Typography>
                    </Box>
                  </Box>
                )}

                {/* Live Transcript Bubble - Shows during recording/transcribing in voice mode */}
                {interactionMode === "voice" && (isRecording || isTranscribing) && (
                  <Box
                    sx={{
                      width: "100%",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "flex-end",
                      animation: "fadeIn 0.3s ease",
                      opacity: isTranscribing ? 0.7 : 1,
                    }}
                  >
                    <Box
                      sx={{
                        bgcolor: theme.accent,
                        color: isDarkMode ? "#000" : "#fff",
                        py: { xs: 1.5, md: 2 },
                        px: { xs: 2, md: 2.5 },
                        borderRadius: "20px 20px 4px 20px",
                        maxWidth: { xs: "88%", sm: "85%", md: "85%" },
                        boxShadow: "0 2px 12px rgba(0,0,0,0.1)",
                        minWidth: "100px",
                      }}
                    >
                      <Typography
                        variant="body1"
                        sx={{
                          fontSize: { xs: "0.9rem", md: "1rem" },
                          fontWeight: 500,
                        }}
                      >
                        {transcript ||
                          (isTranscribing
                            ? "Processing audio..."
                            : "Listening...")}
                        {isRecording && !transcript && (
                          <span
                            style={{
                              display: "inline-block",
                              width: "4px",
                              height: "14px",
                              backgroundColor: "currentColor",
                              marginLeft: "4px",
                              animation: "blink 1s step-end infinite",
                              verticalAlign: "middle",
                            }}
                          />
                        )}
                      </Typography>
                      <style>{`@keyframes blink { 50% { opacity: 0; } }`}</style>
                    </Box>
                  </Box>
                )}
              </Box>

              {/* Text Input Section */}
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 2,
                  width: "100%",
                  maxWidth: "500px",
                  mt: "auto",
                  pt: 1.5,
                  borderTop: `1px solid ${theme.cardBorder}`,
                  bgcolor: isDarkMode
                    ? "rgba(15,15,25,0.68)"
                    : "rgba(255,255,255,0.78)",
                  backdropFilter: "blur(18px)",
                  position: "sticky",
                  bottom: 0,
                  zIndex: 2,
                }}
              >
                {/* INTEGRATED INPUT FIELD — always visible in chat mode, hidden during recording in voice mode */}
                {(interactionMode === "chat" || (!isRecording && !isTranscribing)) && (
                  <TextField
                    fullWidth
                    placeholder={interactionMode === "chat" ? "Type your message..." : "Type to ZeroQ..."}
                    variant="outlined"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        const target = e.target as HTMLInputElement;
                        if (target.value.trim()) {
                          handleChat(target.value);
                          target.value = "";
                        }
                      }
                    }}
                    sx={{ mt: interactionMode === "chat" ? 1 : 2 }}
                    slotProps={{
                      input: {
                        sx: {
                          borderRadius: "30px",
                          bgcolor: theme.inputBg,
                          color: theme.text,
                          backdropFilter: "blur(10px)",
                          border: `1px solid ${theme.cardBorder}`,
                        },
                        endAdornment: (
                          <SearchIcon
                            sx={{ color: theme.textSecondary, mr: 1 }}
                          />
                        ),
                      },
                    }}
                  />
                )}
              </Box>
            </Box>

            {/* RESULTS PANEL: Content Viewer - Only show when there's actual content */}
            {activeViewer && (
              <Fade in={true} timeout={600}>
                <Box
                  sx={{
                    // FLEXIBLE WIDTH for Content Panel to fill screen
                    flex: { xs: "1 1 auto", md: "1" },
                    width: "100%",
                    // UNCONSTRAINED width to allow horizonzal expansion (Monitor Mode)
                    maxWidth: { xs: "100%", md: "100%" },
                    // CHANGED: Fixed height to match chat column for symmetry
                    height: { xs: "60vh", md: "70vh" },
                    overflowY: "auto",
                    p: { xs: 2, sm: 2.5, md: 3 },
                    borderRadius: { xs: "16px", sm: "20px", md: "24px" },
                    bgcolor: isDarkMode
                      ? "rgba(15,15,25,0.85)"
                      : "rgba(255,255,255,0.95)",
                    border: `1px solid ${isDarkMode ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)"}`,
                    backdropFilter: "blur(24px)",
                    boxShadow: isDarkMode
                      ? "0 8px 32px rgba(0,0,0,0.4)"
                      : "0 8px 32px rgba(0,0,0,0.08)",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "stretch",
                    justifyContent: "flex-start",
                    transition: "all 0.4s cubic-bezier(0.4, 0, 0.2, 1)",
                    order: { xs: 1, md: 0 },
                    "&::-webkit-scrollbar": { width: "4px" },
                    "&::-webkit-scrollbar-thumb": {
                      background: isDarkMode
                        ? "rgba(255,255,255,0.12)"
                        : "rgba(0,0,0,0.1)",
                      borderRadius: "4px",
                    },
                  }}
                >
                  {activeViewer === "shops" && (
                    <Stack spacing={3} sx={{ width: "100%" }}>
                      <Typography variant="h5" sx={{ fontWeight: 600 }}>
                        Nearby Verified Queues
                      </Typography>
                      {activeShops.length === 0 ? (
                        <Box sx={{ textAlign: "center", py: 10, opacity: 0.6 }}>
                          <SearchIcon sx={{ fontSize: 60, mb: 2 }} />
                          <Typography variant="h6">No shops found.</Typography>
                        </Box>
                      ) : (
                        activeShops.map((shop: any) => (
                          <Card
                            key={shop.id}
                            onClick={() => {
                              const targetSlug = shop.slug || `shop-${shop.id}`;
                              if (isLocalhost()) {
                                navigate(`/shop-ai/${shop.id}`);
                              } else {
                                window.location.href = constructShopUrl(targetSlug);
                              }
                            }}
                            sx={{
                              bgcolor: theme.cardBg,
                              borderRadius: "24px",
                              border: `1px solid ${theme.cardBorder}`,
                              cursor: "pointer",
                            }}
                          >
                            <CardContent
                              sx={{
                                display: "flex",
                                alignItems: "center",
                                gap: 3,
                                p: 3,
                              }}
                            >
                              <Avatar
                                src={shop.logo_url}
                                sx={{
                                  width: 64,
                                  height: 64,
                                  borderRadius: "16px",
                                  bgcolor: theme.accent,
                                }}
                              >
                                {shop.name[0]}
                              </Avatar>
                              <Box sx={{ flex: 1 }}>
                                <Typography
                                  variant="h6"
                                  sx={{ fontWeight: 700 }}
                                >
                                  {shop.name}
                                </Typography>
                                <Typography
                                  variant="body2"
                                  sx={{ opacity: 0.7 }}
                                >
                                  {shop.address}, {shop.city}
                                </Typography>
                              </Box>
                              <Button
                                variant="contained"
                                onClick={() => {
                                  const targetSlug =
                                    shop.slug || `shop-${shop.id}`;

                                  if (isLocalhost()) {
                                    // Keeps dev flow simple (SPA routing)
                                    navigate(`/shop-ai/${shop.id}`);
                                  } else {
                                    // Full redirect to subdomain
                                    window.location.href = constructShopUrl(
                                      targetSlug,
                                      "/ai",
                                    );
                                  }
                                }}
                                sx={{
                                  bgcolor: theme.accent,
                                  color: isDarkMode ? "black" : "white",
                                  borderRadius: "12px",
                                  fontWeight: 700,
                                }}
                              >
                                JOIN
                              </Button>
                            </CardContent>
                          </Card>
                        ))
                      )}
                    </Stack>
                  )}

                  {activeViewer === "pricing" && <Pricing embedded={true} />}
                  {(activeViewer as string) === "testimonials" && (
                    <Testimonials embedded={true} />
                  )}
                  {activeViewer === "features" && <Features embedded={true} />}
                  {activeViewer === "faq" && <FAQ embedded={true} />}
                  {activeViewer === "register" && (
                    <VoiceRegistrationFlow
                      isDarkMode={isDarkMode}
                      theme={theme}
                      prefilledAccountType={registrationAccountType}
                      onAISpeak={(text) => {
                        // Append AI message to chat and speak it
                        speak(text);
                        setChatHistory((prev) => [
                          ...prev,
                          { role: "ai", text },
                        ]);
                      }}
                      onClose={(success) => {
                        setActiveViewer(null);
                        setRegistrationAccountType(null);
                        if (success) {
                          const msg =
                            'Your account is ready! Click "Sign In Now" to log in, or explore the platform first.';
                          speak(msg);
                          setChatHistory((prev) => [
                            ...prev,
                            { role: "ai", text: msg },
                          ]);
                        }
                      }}
                    />
                  )}
                </Box>
              </Fade>
            )}
          </Box>
        </Box>
      </Box>
    </Fade>
  );
};

export default MasterAIAgent;
