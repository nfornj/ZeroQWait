import React, { useCallback, useMemo, useRef, useState } from "react";
import {
  alpha,
  Box,
  Card,
  CardContent,
  Chip,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import CreateNewFolderRoundedIcon from "@mui/icons-material/CreateNewFolderRounded";
import UploadFileRoundedIcon from "@mui/icons-material/UploadFileRounded";
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
  isUploading?: boolean;
  onSend: (message: string) => Promise<void>;
  onUpload: (files: File[]) => Promise<void>;
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

const AgentChat: React.FC<AgentChatProps> = ({
  messages,
  isStreaming,
  isUploading = false,
  onSend,
  onUpload,
}) => {
  const muiTheme = useTheme();
  const { shop } = useShop();
  const [composerValue, setComposerValue] = useState("");
  const [uploadMenuAnchor, setUploadMenuAnchor] = useState<HTMLElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const folderInputRef = useRef<HTMLInputElement | null>(null);

  const brandPrimary = muiTheme.palette.primary.main;
  const brandSecondary = muiTheme.palette.secondary.main;
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

  const submit = useCallback(
    async (event?: React.FormEvent) => {
      event?.preventDefault();

      const trimmed = composerValue.trim();
      if (!trimmed || isStreaming || isUploading) return;

      setComposerValue("");
      await onSend(trimmed);
    },
    [composerValue, isStreaming, isUploading, onSend],
  );

  const closeUploadMenu = useCallback(() => {
    setUploadMenuAnchor(null);
  }, []);

  const handleUploadSelection = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFiles = Array.from(event.target.files || []);
      event.target.value = "";
      closeUploadMenu();
      if (selectedFiles.length === 0 || isUploading) {
        return;
      }
      await onUpload(selectedFiles);
    },
    [closeUploadMenu, isUploading, onUpload],
  );

  const openFilePicker = useCallback(() => {
    closeUploadMenu();
    fileInputRef.current?.click();
  }, [closeUploadMenu]);

  const openFolderPicker = useCallback(() => {
    closeUploadMenu();
    if (folderInputRef.current) {
      folderInputRef.current.setAttribute("webkitdirectory", "");
      folderInputRef.current.setAttribute("directory", "");
      folderInputRef.current.click();
    }
  }, [closeUploadMenu]);

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
            label={isUploading ? "Uploading" : isStreaming ? "Streaming" : "Ready"}
            sx={{
              bgcolor: isUploading
                ? alpha(brandPrimary, 0.18)
                : isStreaming
                  ? "warning.main"
                  : brandSecondary,
              color: isUploading
                ? brandPrimary
                : muiTheme.palette.getContrastText(
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
              disabled={isStreaming || isUploading}
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

        <Box sx={{ flex: 1, minHeight: 0, mb: 1.25, position: "relative" }}>
          <input
            ref={fileInputRef}
            type="file"
            hidden
            multiple
            accept=".txt,.md,.markdown,.csv,.json,.html,.htm,.xml,.yml,.yaml,.tsv,text/plain,text/markdown,text/csv,application/json,text/html,text/xml,application/xml,text/yaml,application/x-yaml"
            onChange={handleUploadSelection}
          />
          <input
            ref={folderInputRef}
            type="file"
            hidden
            multiple
            onChange={handleUploadSelection}
          />
          <ChatBox
            adapter={noopChatAdapter}
            messages={chatMessages}
            activeConversationId={OWNER_CONVERSATION_ID}
            members={[OWNER_USER, assistantUser, SYSTEM_USER]}
            currentUser={OWNER_USER}
            composerValue={composerValue}
            onComposerValueChange={setComposerValue}
            partRenderers={partRenderers}
            variant="default"
            density="standard"
            features={{
              attachments: true,
              conversationHeader: false,
              helperText: false,
              suggestions: false,
              scrollToBottom: true,
            }}
            slotProps={{
              composerRoot: {
                variant: "compact",
                slotProps: {
                  root: {
                    onSubmit: submit,
                  },
                },
              },
              composerInput: {
                placeholder: "Ask about queue, team, finance, or CRM...",
                disabled: isStreaming || isUploading,
                maxRows: undefined,
              },
              composerAttachButton: {
                disabled: isUploading,
                onClick: (event: React.MouseEvent<HTMLButtonElement>) => {
                  event.preventDefault();
                  setUploadMenuAnchor(event.currentTarget);
                },
              },
              composerSendButton: {
                disabled: isStreaming || isUploading || !composerValue.trim(),
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
                position: "sticky",
                bottom: 0,
                minHeight: "unset",
                mx: { xs: 0.5, md: 0.75 },
                mb: { xs: 0.5, md: 0.75 },
                mt: 0.35,
                px: 0,
                py: 0,
                border: "1px solid",
                borderColor:
                  muiTheme.palette.mode === "dark"
                    ? alpha(brandPrimary, 0.2)
                    : alpha(brandPrimary, 0.16),
                borderRadius: "28px",
                bgcolor:
                  muiTheme.palette.mode === "dark"
                    ? alpha(muiTheme.palette.common.black, 0.24)
                    : alpha(muiTheme.palette.common.white, 0.72),
                backdropFilter: "blur(22px)",
                overflow: "hidden",
                boxShadow:
                  muiTheme.palette.mode === "dark"
                    ? `0 18px 36px ${alpha(muiTheme.palette.common.black, 0.22)}`
                    : `0 14px 32px ${alpha(brandPrimary, 0.1)}`,
              },
              [`& .${chatComposerClasses.variantCompact}`]: {
                position: "relative",
                alignItems: "flex-end",
                flexWrap: "nowrap",
                gap: 0.5,
                minHeight: 82,
                px: { xs: 1.1, md: 1.25 },
                py: { xs: 0.55, md: 0.65 },
              },
              [`& .${chatComposerClasses.textArea}`]: {
                flex: 1,
                alignSelf: "stretch",
                minHeight: 68,
                maxHeight: 220,
                padding: "14px 8px 14px 48px",
                border: "none",
                backgroundColor: "transparent",
                lineHeight: 1.45,
                fontSize: "0.95rem",
                "&::placeholder": {
                  color: alpha(muiTheme.palette.text.secondary, 0.72),
                },
              },
              [`& .${chatComposerClasses.attachButton}`]: {
                position: "absolute",
                left: { xs: 14, md: 16 },
                bottom: { xs: 13, md: 14 },
                zIndex: 1,
                borderRadius: 999,
                minWidth: 34,
                width: 34,
                height: 34,
                marginBottom: 0,
                border: "1px solid",
                borderColor:
                  muiTheme.palette.mode === "dark"
                    ? alpha(brandPrimary, 0.3)
                    : alpha(brandPrimary, 0.18),
                bgcolor:
                  muiTheme.palette.mode === "dark"
                    ? alpha(brandPrimary, 0.14)
                    : alpha(brandPrimary, 0.08),
                color: brandPrimary,
                backdropFilter: "blur(10px)",
                boxShadow: "none",
                "&:hover": {
                  bgcolor:
                    muiTheme.palette.mode === "dark"
                      ? alpha(brandPrimary, 0.22)
                      : alpha(brandPrimary, 0.14),
                  color: brandPrimary,
                },
                "&:disabled": {
                  color: alpha(brandPrimary, 0.56),
                  borderColor: alpha(brandPrimary, 0.12),
                },
              },
              [`& .${chatComposerClasses.sendButton}`]: {
                borderRadius: 999,
                bgcolor: brandPrimary,
                color: userBubbleText,
                minWidth: 38,
                width: 38,
                height: 38,
                marginInlineStart: 0,
                marginBottom: 2,
                boxShadow: `0 10px 20px ${alpha(brandPrimary, 0.24)}`,
                "&:hover": {
                  bgcolor: brandPrimary,
                  filter: "brightness(0.95)",
                },
                "&.Mui-disabled": {
                  bgcolor: alpha(brandPrimary, 0.38),
                  color: alpha(userBubbleText, 0.72),
                },
              },
            }}
          />
          <Menu
            anchorEl={uploadMenuAnchor}
            open={Boolean(uploadMenuAnchor)}
            onClose={closeUploadMenu}
            anchorOrigin={{ vertical: "top", horizontal: "left" }}
            transformOrigin={{ vertical: "bottom", horizontal: "left" }}
          >
            <MenuItem onClick={openFilePicker}>
              <ListItemIcon>
                <UploadFileRoundedIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText primary="Upload files" secondary="Text, markdown, CSV, JSON, HTML, XML, YAML" />
            </MenuItem>
            <MenuItem onClick={openFolderPicker}>
              <ListItemIcon>
                <CreateNewFolderRoundedIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText primary="Upload folder" secondary="Imports supported documents from a selected folder" />
            </MenuItem>
          </Menu>
        </Box>
      </CardContent>
    </Card>
  );
};

export default AgentChat;
