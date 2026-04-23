import React, { useCallback, useMemo, useState } from "react";
import {
  alpha,
  Box,
  Card,
  CardContent,
  Chip,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import { BarChart } from "@mui/x-charts/BarChart";
import { LineChart } from "@mui/x-charts/LineChart";
import { PieChart } from "@mui/x-charts/PieChart";
import { SparkLineChart } from "@mui/x-charts/SparkLineChart";
import {
  ChatBox,
  chatBoxClasses,
  chatComposerClasses,
  chatMessageClasses,
} from "@mui/x-chat";
import type {
  ChatAdapter,
  ChatConversation,
  ChatMessage as MuiChatMessage,
  ChatPartRendererMap,
  ChatUser,
} from "@mui/x-chat-headless";
import type { AgentChart, AgentFile, ChatMessage } from "./types";
import ThinkingSteps from "./ThinkingSteps";
import { useShop } from "../../contexts/ShopContext";

interface AgentChatProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  onSend: (message: string) => Promise<void>;
}

const OWNER_CONVERSATION_ID = "owner-supervisor";

const OWNER_USER: ChatUser = {
  id: "owner",
  displayName: "You",
  role: "user",
};

const SYSTEM_USER: ChatUser = {
  id: "system",
  displayName: "System",
  role: "system",
};

const noopChatAdapter: ChatAdapter = {
  sendMessage: async () =>
    new ReadableStream({
      start(controller) {
        controller.close();
      },
    }),
};

const formatAgentName = (agent?: string) => {
  if (!agent) return "Supervisor";

  return agent
    .split(/[_-]/g)
    .filter(Boolean)
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(" ");
};

const mapStatus = (status: ChatMessage["status"]): MuiChatMessage["status"] => {
  switch (status) {
    case "sending":
      return "sending";
    case "streaming":
      return "streaming";
    case "error":
      return "error";
    default:
      return "sent";
  }
};

type ChartMessagePart = {
  type: "data-chart";
  id?: string;
  data: AgentChart;
  transient?: boolean;
};

type ThinkingMessagePart = {
  type: "data-thinking";
  id?: string;
  data: {
    steps: NonNullable<ChatMessage["thinkingSteps"]>;
    isComplete: boolean;
  };
  transient?: boolean;
};

const toFilePartUrl = (file: AgentFile) =>
  file.content.startsWith("http://") || file.content.startsWith("https://")
    ? file.content
    : `data:${file.mimeType};base64,${file.content}`;

const InlineChart: React.FC<{ chart: AgentChart; accent: string }> = ({ chart, accent }) => {
  const labels = chart.data.map((point) => point.label);
  const values = chart.data.map((point) => point.value);

  return (
    <Box
      sx={{
        mt: 1,
        p: 1.25,
        borderRadius: 2,
        border: "1px solid",
        borderColor: alpha(accent, 0.16),
        bgcolor: alpha(accent, 0.04),
        width: "100%",
        minWidth: { xs: 240, sm: 320 },
        maxWidth: "100%",
      }}
    >
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
        {chart.title}
      </Typography>
      {chart.chartType === "sparkline" ? (
        <SparkLineChart data={values} height={56} curve="natural" area color={accent} />
      ) : chart.chartType === "pie" ? (
        <PieChart
          series={[{ data: chart.data.map((point, index) => ({ id: index, value: point.value, label: point.label })) }]}
          height={180}
          margin={{ top: 8, right: 8, bottom: 8, left: 8 }}
        />
      ) : chart.chartType === "line" ? (
        <LineChart
          xAxis={[{ data: labels, scaleType: "band" }]}
          series={[{ data: values, color: accent }]}
          height={180}
          margin={{ top: 8, right: 12, bottom: 28, left: 36 }}
        />
      ) : (
        <BarChart
          xAxis={[{ data: labels, scaleType: "band" }]}
          series={[{ data: values, color: accent }]}
          height={180}
          margin={{ top: 8, right: 12, bottom: 28, left: 36 }}
        />
      )}
    </Box>
  );
};

const InlineThinking: React.FC<{
  steps: NonNullable<ChatMessage["thinkingSteps"]>;
  isComplete: boolean;
  accent: string;
}> = ({ steps, isComplete, accent }) => (
  <Box
    sx={{
      mt: 0.25,
      width: "100%",
      minWidth: { xs: 220, sm: 280 },
      maxWidth: "100%",
    }}
  >
    <ThinkingSteps
      steps={steps}
      isComplete={isComplete}
      accentColor={accent}
      showWhenEmpty
      embedded
    />
  </Box>
);

const AgentChat: React.FC<AgentChatProps> = ({ messages, isStreaming, onSend }) => {
  const muiTheme = useTheme();
  const { shop } = useShop();
  const [composerValue, setComposerValue] = useState("");

  const brandPrimary = shop?.primary_color || muiTheme.palette.primary.main;
  const brandSecondary = shop?.secondary_color || brandPrimary;
  const userBubbleText = muiTheme.palette.getContrastText(brandPrimary);
  const panelBorder = alpha(brandPrimary, muiTheme.palette.mode === "dark" ? 0.24 : 0.16);

  const quickPrompts = [
    "Give me today's queue summary",
    "Show this week's revenue trend",
    "Who is on shift now?",
    "Show my CRM pipeline summary",
  ];

  const assistantUser = useMemo<ChatUser>(
    () => ({
      id: "supervisor",
      displayName: shop?.name ? `${shop.name} Supervisor` : "Supervisor",
      role: "assistant",
    }),
    [shop?.name],
  );

  const chatMessages = useMemo<MuiChatMessage[]>(
    () =>
      messages.map((message) => {
        const author =
          message.role === "user"
            ? OWNER_USER
            : message.role === "system"
              ? SYSTEM_USER
              : {
                  ...assistantUser,
                  displayName: formatAgentName(message.agent) || assistantUser.displayName,
                };

        const parts: MuiChatMessage["parts"] = [];
        const hasRenderableAssistantResponse = Boolean(
          message.content.trim() || (message.charts && message.charts.length > 0) || (message.files && message.files.length > 0),
        );

        if (
          message.role === "assistant" &&
          message.status === "streaming" &&
          !hasRenderableAssistantResponse
        ) {
          parts.push({
            type: "data-thinking",
            id: `${message.id}_thinking`,
            data: {
              steps: message.thinkingSteps || [],
              isComplete: Boolean(message.thinkingComplete),
            },
          } as MuiChatMessage["parts"][number]);
        }

        if (message.content) {
          parts.push({
            type: "text",
            text: message.content,
            state: message.status === "streaming" ? "streaming" : "done",
          });
        }

        for (const chart of message.charts || []) {
          parts.push({
            type: "data-chart",
            id: chart.id,
            data: chart,
          } as MuiChatMessage["parts"][number]);
        }

        for (const file of message.files || []) {
          parts.push({
            type: "file",
            mediaType: file.mimeType,
            url: toFilePartUrl(file),
            filename: file.filename,
          });
        }

        return {
          id: message.id,
          conversationId: OWNER_CONVERSATION_ID,
          role: message.role,
          author,
          status: mapStatus(message.status),
          createdAt: message.timestamp,
          parts,
        };
      }),
    [assistantUser, messages],
  );

  const partRenderers = useMemo<ChatPartRendererMap>(
    () => ({
      "data-thinking": ({ part }) => {
        const thinking = (part as ThinkingMessagePart).data;
        return (
          <InlineThinking
            steps={thinking.steps}
            isComplete={thinking.isComplete}
            accent={brandPrimary}
          />
        );
      },
      "data-chart": ({ part }) => (
        <InlineChart chart={(part as ChartMessagePart).data} accent={brandPrimary} />
      ),
    }),
    [brandPrimary],
  );

  const conversation = useMemo<ChatConversation>(
    () => ({
      id: OWNER_CONVERSATION_ID,
      title: "Supervisor Chat",
      subtitle: isStreaming ? "Streaming response" : "Owner operations workspace",
      participants: [OWNER_USER, assistantUser],
    }),
    [assistantUser, isStreaming],
  );

  const submit = useCallback(
    async (event?: React.FormEvent) => {
      event?.preventDefault();

      const trimmed = composerValue.trim();
      if (!trimmed || isStreaming) return;

      setComposerValue("");
      await onSend(trimmed);
    },
    [composerValue, isStreaming, onSend],
  );

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        height: "100%",
        borderColor: "divider",
        background:
          muiTheme.palette.mode === "dark"
            ? "linear-gradient(170deg, rgba(17,19,26,0.92) 0%, rgba(12,14,22,0.88) 100%)"
            : "linear-gradient(170deg, rgba(255,255,255,0.96) 0%, rgba(250,252,255,0.92) 100%)",
      }}
    >
      <CardContent
        sx={{
          display: "flex",
          flexDirection: "column",
          height: "100%",
          p: { xs: 2, md: 2.5 },
          pb: "0 !important",
        }}
      >
        <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1}>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>
            Supervisor Chat
          </Typography>
          <Chip
            size="small"
            label={isStreaming ? "Streaming" : "Ready"}
            sx={{
              bgcolor: isStreaming ? "warning.main" : brandSecondary,
              color: muiTheme.palette.getContrastText(
                isStreaming ? muiTheme.palette.warning.main : brandSecondary,
              ),
              fontWeight: 700,
            }}
          />
        </Stack>

        <Typography variant="body2" color="text.secondary" mb={1.5}>
          Your AI operating console for queue, team, finance, CRM, and approval workflows.
        </Typography>

        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" mb={1.5}>
          {quickPrompts.map((prompt) => (
            <Chip
              key={prompt}
              label={prompt}
              variant="outlined"
              size="small"
              clickable
              onClick={() => setComposerValue(prompt)}
              disabled={isStreaming}
              sx={{
                borderColor: `${brandPrimary}80`,
                color: brandPrimary,
                fontWeight: 600,
                "&:hover": {
                  bgcolor: `${brandPrimary}14`,
                },
              }}
            />
          ))}
        </Stack>

        <Box sx={{ flex: 1, minHeight: 0, mb: 2 }}>
          <ChatBox
            adapter={noopChatAdapter}
            messages={chatMessages}
            conversations={[conversation]}
            activeConversationId={OWNER_CONVERSATION_ID}
            members={[OWNER_USER, assistantUser, SYSTEM_USER]}
            currentUser={OWNER_USER}
            composerValue={composerValue}
            onComposerValueChange={setComposerValue}
            partRenderers={partRenderers}
            variant="default"
            density="standard"
            features={{
              attachments: false,
              conversationHeader: false,
              helperText: true,
              suggestions: false,
              scrollToBottom: true,
            }}
            slotProps={{
              composerRoot: {
                slotProps: {
                  root: {
                    onSubmit: submit,
                  },
                },
              },
              composerInput: {
                placeholder: "Ask your supervisor agent anything about shop operations...",
                disabled: isStreaming,
                maxRows: 6,
              },
              composerSendButton: {
                disabled: isStreaming || !composerValue.trim(),
              },
              composerHelperText: {
                children: isStreaming
                  ? "Thinking appears inline and is replaced as soon as the response lands."
                  : "Finance charts and image/file previews appear inline here. Uploads stay off until the backend accepts inbound files.",
              },
            }}
            sx={{
              height: "100%",
              borderRadius: 3,
              border: "1px solid",
              borderColor: panelBorder,
              bgcolor:
                muiTheme.palette.mode === "dark"
                  ? alpha(muiTheme.palette.common.black, 0.1)
                  : alpha(muiTheme.palette.common.white, 0.82),
              overflow: "hidden",
              [`& .${chatBoxClasses.layout}`]: {
                height: "100%",
              },
              [`& .${chatBoxClasses.threadPane}`]: {
                minHeight: 0,
                height: "100%",
                gap: 0,
              },
              [`& .${chatMessageClasses.root}`]: {
                px: { xs: 1.25, md: 1.5 },
              },
              [`& .${chatMessageClasses.content}`]: {
                maxWidth: { xs: "90%", sm: "82%" },
              },
              [`& .${chatMessageClasses.content} > *`]: {
                width: "100%",
              },
              [`& .${chatMessageClasses.content} a`]: {
                color: "inherit",
              },
              [`& .${chatMessageClasses.content} img`]: {
                display: "block",
                maxWidth: "100%",
                maxHeight: 240,
                borderRadius: 12,
                marginBottom: 8,
                objectFit: "cover",
              },
              [`& .${chatMessageClasses.bubble}`]: {
                display: "flex",
                flexDirection: "column",
                alignItems: "stretch",
                gap: 0.5,
                borderRadius: 3,
                border: "1px solid",
                borderColor: alpha(brandPrimary, 0.12),
                boxShadow: "none",
              },
              [`& .${chatMessageClasses.roleUser} .${chatMessageClasses.bubble}`]: {
                bgcolor: brandPrimary,
                color: userBubbleText,
                borderColor: "transparent",
                borderRadius: "20px 20px 6px 20px",
              },
              [`& .${chatMessageClasses.roleAssistant} .${chatMessageClasses.bubble}`]: {
                bgcolor:
                  muiTheme.palette.mode === "dark"
                    ? alpha(brandSecondary, 0.14)
                    : alpha(brandSecondary, 0.08),
                borderColor: alpha(brandPrimary, 0.12),
              },
              [`& [data-role='system'] .${chatMessageClasses.bubble}`]: {
                bgcolor: alpha(brandPrimary, 0.05),
                borderStyle: "dashed",
                color: muiTheme.palette.text.secondary,
              },
              [`& .${chatMessageClasses.meta}`]: {
                color: alpha(muiTheme.palette.text.secondary, 0.9),
              },
              [`& .${chatComposerClasses.root}`]: {
                borderTop: "1px solid",
                borderColor: alpha(brandPrimary, 0.12),
                px: { xs: 1.25, md: 1.5 },
                py: 1.5,
                bgcolor:
                  muiTheme.palette.mode === "dark"
                    ? alpha(muiTheme.palette.common.black, 0.08)
                    : alpha(muiTheme.palette.common.white, 0.75),
              },
              [`& .${chatComposerClasses.textArea}`]: {
                borderRadius: "24px",
                borderColor: `${brandPrimary}55`,
                bgcolor:
                  muiTheme.palette.mode === "dark"
                    ? alpha(muiTheme.palette.common.white, 0.04)
                    : alpha(muiTheme.palette.common.white, 0.88),
                "&:hover": {
                  borderColor: brandPrimary,
                },
                "&:focus-within": {
                  borderColor: brandPrimary,
                  boxShadow: `0 0 0 3px ${alpha(brandPrimary, 0.16)}`,
                },
              },
              [`& .${chatComposerClasses.sendButton}`]: {
                borderRadius: 999,
                bgcolor: brandPrimary,
                color: userBubbleText,
                "&:hover": {
                  bgcolor: brandPrimary,
                  filter: "brightness(0.95)",
                },
                "&.Mui-disabled": {
                  bgcolor: alpha(brandPrimary, 0.38),
                  color: alpha(userBubbleText, 0.72),
                },
              },
              [`& .${chatComposerClasses.helperText}`]: {
                color: muiTheme.palette.text.secondary,
                px: 0.25,
              },
            }}
          />
        </Box>
      </CardContent>
    </Card>
  );
};

export default AgentChat;
