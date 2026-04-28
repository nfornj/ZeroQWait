import React, { type FC, type ReactNode } from "react";
import CreateNewFolderRoundedIcon from "@mui/icons-material/CreateNewFolderRounded";
import NorthRoundedIcon from "@mui/icons-material/NorthRounded";
import StopRoundedIcon from "@mui/icons-material/StopRounded";
import { alpha, Box, IconButton, Typography, useTheme } from "@mui/material";
import {
  AuiIf,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  type ThreadMessage,
} from "@assistant-ui/react";
import {
  ComposerAddAttachment,
  ComposerAttachments,
  UserMessageAttachments,
} from "./attachment";

export interface ComposerProps {
  placeholder?: string;
  disabled?: boolean;
  isRunning?: boolean;
  onOpenFolderPicker?: () => void;
  dictationControl?: ReactNode;
}

interface ThreadProps {
  welcome?: ReactNode;
  footer?: ReactNode;
}

export const Composer: FC<ComposerProps> = ({
  placeholder = "Ask a follow-up",
  disabled = false,
  isRunning = false,
  onOpenFolderPicker,
  dictationControl,
}) => {
  const muiTheme = useTheme();

  return (
    <ComposerPrimitive.Root
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 0,
        padding: 0,
        border: `1px solid ${
          muiTheme.palette.mode === "dark"
            ? alpha("#f5f3ef", 0.08)
            : alpha("#1f1d1a", 0.08)
        }`,
        borderRadius: 24,
        background:
          muiTheme.palette.mode === "dark"
            ? alpha("#17181b", 0.98)
            : alpha("#fcfbf9", 0.98),
        boxShadow:
          muiTheme.palette.mode === "dark"
            ? "0 10px 28px rgba(0, 0, 0, 0.22)"
            : "0 8px 24px rgba(28, 23, 16, 0.06)",
        overflow: "hidden",
      }}
    >
      <Box
        sx={{
          display: "flex",
          flexWrap: "wrap",
          gap: 0.75,
          px: 1.25,
          pt: 1,
          "&:empty": {
            display: "none",
          },
        }}
      >
        <ComposerAttachments />
      </Box>

      <ComposerPrimitive.Input asChild>
        <textarea
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          style={{
            flex: 1,
            minHeight: 40,
            maxHeight: 220,
            border: "none",
            outline: "none",
            resize: "none",
            background: "transparent",
            color: muiTheme.palette.text.primary,
            fontFamily: "inherit",
            fontSize: "1rem",
            lineHeight: 1.45,
            padding: "12px 14px 10px",
            letterSpacing: "0.01em",
          }}
        />
      </ComposerPrimitive.Input>

      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 1,
          px: 0.75,
          py: 0.5,
          borderTop: "1px solid",
          borderColor:
            muiTheme.palette.mode === "dark"
              ? alpha("#f5f3ef", 0.08)
              : alpha("#1f1d1a", 0.08),
          backgroundColor:
            muiTheme.palette.mode === "dark"
              ? alpha("#ffffff", 0.02)
              : alpha("#1f1d1a", 0.015),
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.25 }}>
          <ComposerAddAttachment disabled={disabled} />

          <IconButton
            size="small"
            disabled={disabled}
            onClick={onOpenFolderPicker}
            sx={{
              width: 34,
              height: 34,
              color: muiTheme.palette.mode === "dark" ? alpha("#f5f3ef", 0.82) : "#6f6a63",
              borderRadius: 2.5,
              "&:hover": {
                backgroundColor:
                  muiTheme.palette.mode === "dark"
                    ? alpha("#f5f3ef", 0.08)
                    : alpha("#1f1d1a", 0.06),
              },
              "&.Mui-disabled": {
                color: alpha(muiTheme.palette.text.secondary, 0.4),
              },
            }}
          >
            <CreateNewFolderRoundedIcon fontSize="small" />
          </IconButton>
        </Box>

        <Box sx={{ flex: 1 }} />

        <Box sx={{ display: "flex", alignItems: "center", gap: 0.25 }}>
          {dictationControl}

          {isRunning ? (
            <ComposerPrimitive.Cancel asChild>
              <IconButton
                size="small"
                sx={{
                  width: 34,
                  height: 34,
                  bgcolor: muiTheme.palette.mode === "dark" ? "#f5f3ef" : "#5f5a53",
                  color: muiTheme.palette.mode === "dark" ? "#1f1f21" : "#ffffff",
                  boxShadow: "none",
                  "&:hover": {
                    bgcolor: muiTheme.palette.mode === "dark" ? "#ffffff" : "#4f4a43",
                  },
                }}
              >
                <StopRoundedIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </ComposerPrimitive.Cancel>
          ) : (
            <ComposerPrimitive.Send asChild>
              <IconButton
                size="small"
                sx={{
                  width: 34,
                  height: 34,
                  bgcolor: muiTheme.palette.mode === "dark" ? "#f5f3ef" : "#5f5a53",
                  color: muiTheme.palette.mode === "dark" ? "#1f1f21" : "#ffffff",
                  boxShadow: "none",
                  "&:hover": {
                    bgcolor: muiTheme.palette.mode === "dark" ? "#ffffff" : "#4f4a43",
                  },
                  "&.Mui-disabled": {
                    bgcolor: muiTheme.palette.mode === "dark" ? alpha("#f5f3ef", 0.22) : "#c9c3ba",
                    color: muiTheme.palette.mode === "dark" ? alpha("#1f1f21", 0.55) : "#f7f4ef",
                  },
                }}
              >
                <NorthRoundedIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </ComposerPrimitive.Send>
          )}
        </Box>
      </Box>
    </ComposerPrimitive.Root>
  );
};

export const ThreadWelcome: FC<{ title?: string; subtitle?: string }> = ({
  title = "Hello there!",
  subtitle = "How can I help you today?",
}) => {
  const muiTheme = useTheme();

  return (
    <Box
      sx={{
        my: "auto",
        display: "flex",
        flex: 1,
        flexDirection: "column",
        justifyContent: "center",
        px: 2,
      }}
    >
      <Typography
        variant="h2"
        sx={{
          fontWeight: 700,
          letterSpacing: "-0.035em",
          color: "text.primary",
        }}
      >
        {title}
      </Typography>
      <Typography
        variant="h5"
        sx={{
          fontWeight: 400,
          color: muiTheme.palette.text.secondary,
          letterSpacing: "-0.02em",
        }}
      >
        {subtitle}
      </Typography>
    </Box>
  );
};

export const AssistantMessage: FC = () => {
  return (
    <MessagePrimitive.Root data-role="assistant">
      <Box sx={{ width: "100%", color: "text.primary" }}>
        <MessagePrimitive.Parts />
      </Box>
    </MessagePrimitive.Root>
  );
};

export const UserMessage: FC = () => {
  return (
    <MessagePrimitive.Root data-role="user">
      <UserMessageAttachments />
      <Box sx={{ display: "flex", justifyContent: "flex-end", width: "100%" }}>
        <Box
          sx={{
            maxWidth: "85%",
            px: 2,
            py: 1.25,
            borderRadius: 3,
            bgcolor: "action.hover",
            color: "text.primary",
          }}
        >
          <MessagePrimitive.Parts />
        </Box>
      </Box>
    </MessagePrimitive.Root>
  );
};

export const Thread: FC<ThreadProps> = ({
  welcome = <ThreadWelcome />,
  footer = <Composer />,
}) => {
  return (
    <ThreadPrimitive.Root
      style={{
        display: "flex",
        flexDirection: "column",
        flex: 1,
        minHeight: 0,
      }}
    >
      <ThreadPrimitive.Viewport
        autoScroll
        style={{
          display: "flex",
          flex: 1,
          flexDirection: "column",
          minHeight: 0,
          overflowX: "hidden",
          overflowY: "auto",
        }}
      >
        <AuiIf condition={(state: any) => state.thread.isEmpty}>{welcome}</AuiIf>
        <ThreadPrimitive.Messages>
          {({ message }: { message: ThreadMessage }) =>
            message.role === "user" ? <UserMessage /> : <AssistantMessage />
          }
        </ThreadPrimitive.Messages>
        <ThreadPrimitive.ViewportFooter>{footer}</ThreadPrimitive.ViewportFooter>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
};