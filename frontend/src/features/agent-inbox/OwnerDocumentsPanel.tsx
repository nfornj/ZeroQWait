import React, { useRef } from "react";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import DescriptionRoundedIcon from "@mui/icons-material/DescriptionRounded";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import UploadFileRoundedIcon from "@mui/icons-material/UploadFileRounded";
import {
  alpha,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Stack,
  Tooltip,
  Typography,
  useTheme,
} from "@mui/material";

import type { OwnerDocumentRecord } from "./types";

const UPLOAD_ACCEPT = ".txt,.md,.pdf,.csv,.json,.yaml,.yml,.html,.htm,.rst,.doc,.docx";
const UPLOAD_MAX_MB = 25;

interface OwnerDocumentsPanelProps {
  documents: OwnerDocumentRecord[];
  isLoading?: boolean;
  actingDocumentId?: number | null;
  actingType?: "reindex" | "delete" | null;
  isUploading?: boolean;
  onReindex: (document: OwnerDocumentRecord) => void;
  onDelete: (document: OwnerDocumentRecord) => void;
  onUpload?: (files: File[]) => Promise<void>;
}

const formatBytes = (sizeBytes: number): string => {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`;
  }
  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`;
  }
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
};

const formatTimestamp = (value?: string | null): string => {
  if (!value) {
    return "Unknown";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
};

const OwnerDocumentsPanel: React.FC<OwnerDocumentsPanelProps> = ({
  documents,
  isLoading = false,
  actingDocumentId = null,
  actingType = null,
  isUploading = false,
  onReindex,
  onDelete,
  onUpload,
}) => {
  const muiTheme = useTheme();
  const primary = muiTheme.palette.primary.main;
  const secondary = muiTheme.palette.secondary.main;
  const cardBg =
    muiTheme.palette.mode === "dark"
      ? "rgba(255, 255, 255, 0.05)"
      : alpha("#ffffff", 0.72);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUploadClick = () => {
    if (!isUploading && onUpload) fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []);
    e.target.value = "";
    if (!selected.length || !onUpload) return;
    const oversized = selected.filter((f) => f.size > UPLOAD_MAX_MB * 1024 * 1024);
    if (oversized.length) {
      // Just skip — AgentInbox will surface the error from the backend too
      const ok = selected.filter((f) => f.size <= UPLOAD_MAX_MB * 1024 * 1024);
      if (!ok.length) return;
      await onUpload(ok);
    } else {
      await onUpload(selected);
    }
  };

  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        borderColor: alpha(primary, 0.16),
        bgcolor: cardBg,
        backdropFilter: "blur(20px)",
        boxShadow: `0 18px 50px ${alpha(primary, 0.08)}`,
      }}
    >
      <CardContent sx={{ py: 1.5 }}>
        <Stack spacing={1.25}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
            <Box>
              <Typography variant="h6">Knowledge documents</Typography>
              <Typography variant="body2" color="text.secondary">
                Private owner files stored securely and indexed into shared shop context.
              </Typography>
            </Box>
            <Stack direction="row" spacing={0.75} alignItems="center" flexShrink={0}>
              <Chip
                size="small"
                icon={<DescriptionRoundedIcon />}
                label={documents.length}
                sx={{ bgcolor: alpha(primary, 0.12), color: primary, fontWeight: 700 }}
              />
              {onUpload && (
                <Tooltip title={`Upload documents (${UPLOAD_ACCEPT.replaceAll(",", ", ")}, max ${UPLOAD_MAX_MB} MB each)`}>
                  <span>
                    <Button
                      size="small"
                      variant="contained"
                      disableElevation
                      startIcon={isUploading ? <CircularProgress size={14} sx={{ color: "inherit" }} /> : <UploadFileRoundedIcon />}
                      disabled={isUploading || Boolean(actingDocumentId)}
                      onClick={handleUploadClick}
                      sx={{ borderRadius: 999, textTransform: "none", fontWeight: 700, whiteSpace: "nowrap" }}
                    >
                      {isUploading ? "Uploading…" : "Upload"}
                    </Button>
                  </span>
                </Tooltip>
              )}
            </Stack>
          </Stack>

          <input
            ref={fileInputRef}
            type="file"
            hidden
            multiple
            accept={UPLOAD_ACCEPT}
            onChange={handleFileChange}
          />

          <Divider sx={{ borderColor: alpha(primary, 0.12) }} />

          {isLoading ? (
            <Stack direction="row" spacing={1} alignItems="center" py={1}>
              <CircularProgress size={16} />
              <Typography variant="body2" color="text.secondary">
                Loading uploaded documents...
              </Typography>
            </Stack>
          ) : documents.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              {onUpload
                ? "No documents yet. Click Upload to add files to the shop knowledge base."
                : "Upload files from the chat composer to build a shop-specific knowledge base."}
            </Typography>
          ) : (
            <Stack spacing={1} sx={{ maxHeight: 360, overflowY: "auto", pr: 0.5 }}>
              {documents.map((document, index) => {
                const isReindexing = actingDocumentId === document.id && actingType === "reindex";
                const isDeleting = actingDocumentId === document.id && actingType === "delete";

                return (
                  <React.Fragment key={document.id}>
                    <Stack spacing={1}>
                      <Stack direction="row" spacing={1.25} alignItems="flex-start">
                        <Box
                          sx={{
                            width: 36,
                            height: 36,
                            borderRadius: 2,
                            display: "grid",
                            placeItems: "center",
                            bgcolor: alpha(primary, 0.12),
                            color: primary,
                            flexShrink: 0,
                          }}
                        >
                          <DescriptionRoundedIcon fontSize="small" />
                        </Box>
                        <Box sx={{ minWidth: 0, flex: 1 }}>
                          <Typography variant="subtitle2" sx={{ color: secondary }} noWrap>
                            {document.relative_path || document.filename}
                          </Typography>
                          <Typography variant="caption" color="text.secondary" display="block">
                            {formatBytes(document.size_bytes)} • {document.chunk_count} chunk{document.chunk_count === 1 ? "" : "s"}
                          </Typography>
                          <Typography variant="caption" color="text.secondary" display="block">
                            Updated {formatTimestamp(document.updated_at || document.created_at)}
                          </Typography>
                        </Box>
                        <Chip
                          size="small"
                          label={document.knowledge_status.replace(/_/g, " ")}
                          sx={{
                            textTransform: "capitalize",
                            bgcolor: alpha(primary, 0.08),
                            color: primary,
                            border: `1px solid ${alpha(primary, 0.16)}`,
                          }}
                        />
                      </Stack>

                      <Stack direction="row" spacing={1} justifyContent="flex-end">
                        <Button
                          size="small"
                          variant="outlined"
                          startIcon={isReindexing ? <CircularProgress size={14} /> : <RefreshRoundedIcon />}
                          disabled={Boolean(actingDocumentId)}
                          onClick={() => onReindex(document)}
                          sx={{ borderRadius: 999, textTransform: "none", fontWeight: 700 }}
                        >
                          {isReindexing ? "Re-indexing..." : "Re-index"}
                        </Button>
                        <Button
                          size="small"
                          color="error"
                          variant="text"
                          startIcon={isDeleting ? <CircularProgress size={14} /> : <DeleteOutlineRoundedIcon />}
                          disabled={Boolean(actingDocumentId)}
                          onClick={() => onDelete(document)}
                          sx={{ borderRadius: 999, textTransform: "none", fontWeight: 700 }}
                        >
                          {isDeleting ? "Removing..." : "Delete"}
                        </Button>
                      </Stack>
                    </Stack>
                    {index < documents.length - 1 && <Divider sx={{ borderColor: alpha(primary, 0.08) }} />}
                  </React.Fragment>
                );
              })}
            </Stack>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};

export default OwnerDocumentsPanel;