import React, { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Fade,
  Stack,
  TextField,
  Typography,
  useTheme,
} from "@mui/material";
import SendRoundedIcon from "@mui/icons-material/SendRounded";
import SmartToyRoundedIcon from "@mui/icons-material/SmartToyRounded";
import type { ChatMessage } from "./types";
import { useShop } from "../../contexts/ShopContext";

interface AgentChatProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  onSend: (message: string) => Promise<void>;
}

const AgentChat: React.FC<AgentChatProps> = ({ messages, isStreaming, onSend }) => {
  const muiTheme = useTheme();
  const { shop } = useShop();
  const [input, setInput] = useState("");
  const brandPrimary = shop?.primary_color || muiTheme.palette.primary.main;
  const brandSecondary = shop?.secondary_color || brandPrimary;
  const userBubbleText = muiTheme.palette.getContrastText(brandPrimary);

  const quickPrompts = [
    "Give me today's queue summary",
    "Show this week's revenue trend",
    "Who is on shift now?",
  ];

  const submit = async (event?: React.FormEvent) => {
    event?.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;

    setInput("");
    await onSend(trimmed);
  };

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
      <CardContent sx={{ display: "flex", flexDirection: "column", height: "100%", p: { xs: 2, md: 2.5 } }}>
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
          Your AI operating console for queue, team, finance, and approval workflows.
        </Typography>

        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" mb={1.5}>
          {quickPrompts.map((prompt) => (
            <Chip
              key={prompt}
              label={prompt}
              variant="outlined"
              size="small"
              clickable
              onClick={() => setInput(prompt)}
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

        <Stack spacing={1.5} sx={{ flex: 1, minHeight: 420, maxHeight: { xs: 460, md: 720 }, overflowY: "auto", pr: 0.5, mb: 2 }}>
          {messages.length === 0 ? (
            <Box
              sx={{
                borderRadius: 3,
                border: "1px dashed",
                borderColor: `${brandPrimary}66`,
                bgcolor: `${brandPrimary}0A`,
                px: 2,
                py: 3,
              }}
            >
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 0.75 }}>
                Start with a request
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Try something like “Close the queue for today”, “Who is on shift now?”, or “Summarize today’s performance”.
              </Typography>
            </Box>
          ) : (
            messages.map((msg) => (
              <Fade in key={msg.id} timeout={220}>
                <Box
                  sx={{
                    width: "100%",
                    display: "flex",
                    justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                    opacity: msg.role === "system" ? 0.86 : 1,
                  }}
                >
                  <Box
                    sx={{
                      maxWidth: { xs: "88%", sm: "85%" },
                      px: { xs: 2, md: 2.5 },
                      py: { xs: 1.5, md: 1.75 },
                      borderRadius:
                        msg.role === "user"
                          ? "20px 20px 4px 20px"
                          : "20px 20px 20px 4px",
                      bgcolor:
                        msg.role === "user"
                          ? brandPrimary
                          : muiTheme.palette.mode === "dark"
                            ? "rgba(255,255,255,0.04)"
                            : "rgba(255,255,255,0.88)",
                      color:
                        msg.role === "user"
                          ? userBubbleText
                          : muiTheme.palette.text.primary,
                      border:
                        msg.role === "user"
                          ? "none"
                          : `1px solid ${muiTheme.palette.divider}`,
                      boxShadow:
                        msg.role === "user"
                          ? "0 2px 10px rgba(0,0,0,0.1)"
                          : "0 2px 12px rgba(0,0,0,0.06)",
                    }}
                  >
                    <Stack direction="row" spacing={0.75} alignItems="center" mb={0.5}>
                      {msg.role !== "user" && (
                        <SmartToyRoundedIcon sx={{ fontSize: 16, color: brandSecondary }} />
                      )}
                      <Typography variant="caption" sx={{ opacity: 0.82, fontWeight: 600 }}>
                        {msg.role === "user" ? "You" : msg.role === "assistant" ? "Supervisor" : "System"}
                      </Typography>
                    </Stack>
                    <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", lineHeight: 1.55 }}>
                      <Box component="span" sx={{ color: msg.status === "error" ? "text.secondary" : "inherit" }}>
                        {msg.content || (msg.role === "assistant" ? "..." : "")}
                      </Box>
                      {msg.status === "streaming" && (
                        <Box
                          component="span"
                          sx={{
                            ml: 0.4,
                            opacity: 0.8,
                            animation: "agentInboxBlink 1s step-end infinite",
                          }}
                        >
                          ...
                        </Box>
                      )}
                    </Typography>
                    {msg.status === "error" && msg.retryMessage && (
                      <Button
                        size="small"
                        variant="text"
                        onClick={() => void onSend(msg.retryMessage || "")}
                        disabled={isStreaming}
                        sx={{
                          mt: 0.75,
                          px: 0,
                          minWidth: 0,
                          textTransform: "none",
                          color: "text.secondary",
                          fontWeight: 600,
                          alignSelf: "flex-start",
                        }}
                      >
                        Retry
                      </Button>
                    )}
                    <Typography variant="caption" sx={{ opacity: 0.72, mt: 0.5, display: "block" }}>
                      {new Date(msg.timestamp).toLocaleTimeString()}
                    </Typography>
                  </Box>
                </Box>
              </Fade>
            ))
          )}
        </Stack>

        <Box component="form" onSubmit={submit}>
          <Stack direction="row" spacing={1} alignItems="center">
            <TextField
              fullWidth
              placeholder="Ask your supervisor agent anything about shop operations..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isStreaming}
              size="small"
              slotProps={{
                input: {
                  sx: {
                    borderRadius: "28px",
                    bgcolor:
                      muiTheme.palette.mode === "dark"
                        ? "rgba(255,255,255,0.03)"
                        : "rgba(255,255,255,0.82)",
                    "& fieldset": {
                      borderColor: `${brandPrimary}55`,
                    },
                    "&:hover fieldset": {
                      borderColor: brandPrimary,
                    },
                  },
                },
              }}
            />
            <Button
              type="submit"
              variant="contained"
              disabled={isStreaming || !input.trim()}
              endIcon={isStreaming ? <CircularProgress size={14} color="inherit" /> : <SendRoundedIcon />}
              sx={{
                px: 2,
                borderRadius: "999px",
                textTransform: "none",
                fontWeight: 700,
                bgcolor: brandPrimary,
                "&:hover": {
                  bgcolor: brandPrimary,
                  filter: "brightness(0.95)",
                },
              }}
            >
              Send
            </Button>
          </Stack>
        </Box>
      </CardContent>
      <style>{`
        @keyframes agentInboxBlink {
          0%, 100% { opacity: 0.2; }
          50% { opacity: 1; }
        }
      `}</style>
    </Card>
  );
};

export default AgentChat;
