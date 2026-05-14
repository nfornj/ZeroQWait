import React, { useState, useRef } from "react";
import {
  Box,
  Button,
  TextField,
  Typography,
  IconButton,
  CircularProgress,
  Stack,
  Chip,
} from "@mui/material";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import ImageRoundedIcon from "@mui/icons-material/ImageRounded";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import FeedbackRoundedIcon from "@mui/icons-material/FeedbackRounded";
import axios from "axios";

interface InlineFeedbackFormProps {
  sessionId?: string;
  pageContext?: string;
  onDismiss?: () => void;
}

const InlineFeedbackForm: React.FC<InlineFeedbackFormProps> = ({
  sessionId,
  pageContext = "landing_page",
  onDismiss,
}) => {
  const [description, setDescription] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [screenshot, setScreenshot] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [ticketId, setTicketId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      setError("Screenshot must be under 10 MB.");
      return;
    }
    setScreenshot(file);
    setPreviewUrl(URL.createObjectURL(file));
    setError(null);
  };

  const removeScreenshot = () => {
    setScreenshot(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleSubmit = async () => {
    if (!description.trim()) {
      setError("Please describe the issue.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("description", description.trim());
      if (name.trim()) fd.append("name", name.trim());
      if (email.trim()) fd.append("email", email.trim());
      if (sessionId) fd.append("session_id", sessionId);
      fd.append("page_context", pageContext);
      if (screenshot) fd.append("screenshot", screenshot);

      const res = await axios.post("/api/chat-feedback/submit", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setTicketId(res.data.ticket_id);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Submission failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (ticketId) {
    return (
      <Box
        sx={{
          mt: 1.5,
          p: 2.5,
          borderRadius: "16px",
          bgcolor: (t) =>
            t.palette.mode === "dark"
              ? "rgba(76,175,80,0.15)"
              : "rgba(76,175,80,0.08)",
          border: "1px solid",
          borderColor: "success.main",
          maxWidth: 480,
        }}
      >
        <Stack direction="row" spacing={1.5} alignItems="center">
          <CheckCircleRoundedIcon sx={{ color: "success.main", fontSize: 28 }} />
          <Box>
            <Typography variant="subtitle2" fontWeight={700} color="success.main">
              Feedback submitted — thank you!
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
              Ticket ID:{" "}
              <Box
                component="span"
                sx={{
                  fontFamily: "monospace",
                  fontWeight: 700,
                  color: "text.primary",
                  letterSpacing: 0.5,
                }}
              >
                {ticketId}
              </Box>
            </Typography>
            <Typography variant="caption" color="text.disabled">
              We review all submissions and will reach out if needed.
            </Typography>
          </Box>
        </Stack>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        mt: 1.5,
        p: 2.5,
        borderRadius: "16px",
        bgcolor: (t) =>
          t.palette.mode === "dark" ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.03)",
        border: "1px solid",
        borderColor: "divider",
        maxWidth: 480,
      }}
    >
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
        <FeedbackRoundedIcon color="primary" fontSize="small" />
        <Typography variant="subtitle2" fontWeight={700}>
          Submit Feedback
        </Typography>
      </Stack>

      <TextField
        label="Describe the issue *"
        placeholder="What happened? What did you expect?"
        multiline
        minRows={3}
        maxRows={6}
        fullWidth
        size="small"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        sx={{ mb: 1.5 }}
        inputProps={{ maxLength: 2000 }}
      />

      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} sx={{ mb: 1.5 }}>
        <TextField
          label="Your name (optional)"
          size="small"
          fullWidth
          value={name}
          onChange={(e) => setName(e.target.value)}
          inputProps={{ maxLength: 100 }}
        />
        <TextField
          label="Email (optional)"
          size="small"
          fullWidth
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          type="email"
          inputProps={{ maxLength: 200 }}
        />
      </Stack>

      {/* Screenshot area */}
      {previewUrl ? (
        <Box sx={{ position: "relative", display: "inline-block", mb: 1.5 }}>
          <Box
            component="img"
            src={previewUrl}
            alt="Screenshot preview"
            sx={{
              maxWidth: 200,
              maxHeight: 120,
              borderRadius: "10px",
              objectFit: "contain",
              border: "1px solid",
              borderColor: "divider",
              display: "block",
            }}
          />
          <IconButton
            size="small"
            onClick={removeScreenshot}
            sx={{
              position: "absolute",
              top: -8,
              right: -8,
              bgcolor: "background.paper",
              border: "1px solid",
              borderColor: "divider",
              width: 22,
              height: 22,
              "&:hover": { bgcolor: "error.light" },
            }}
          >
            <CloseRoundedIcon sx={{ fontSize: 14 }} />
          </IconButton>
        </Box>
      ) : (
        <Button
          variant="outlined"
          size="small"
          startIcon={<ImageRoundedIcon />}
          onClick={() => fileInputRef.current?.click()}
          sx={{ mb: 1.5, borderRadius: "10px", textTransform: "none", fontSize: "0.8rem" }}
        >
          Attach screenshot (optional)
        </Button>
      )}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        style={{ display: "none" }}
        onChange={handleFileChange}
      />

      {error && (
        <Typography color="error" variant="caption" display="block" sx={{ mb: 1 }}>
          {error}
        </Typography>
      )}

      <Stack direction="row" spacing={1} alignItems="center">
        <Button
          variant="contained"
          size="small"
          onClick={handleSubmit}
          disabled={submitting || !description.trim()}
          sx={{ borderRadius: "10px", textTransform: "none", fontWeight: 700 }}
        >
          {submitting ? <CircularProgress size={16} sx={{ mr: 1 }} /> : null}
          {submitting ? "Submitting…" : "Submit feedback"}
        </Button>
        {onDismiss && (
          <Button
            variant="text"
            size="small"
            onClick={onDismiss}
            sx={{ borderRadius: "10px", textTransform: "none", color: "text.secondary" }}
          >
            Cancel
          </Button>
        )}
      </Stack>
    </Box>
  );
};

export default InlineFeedbackForm;
