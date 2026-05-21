import React, { useEffect, useMemo, useState } from "react";
import AddRoundedIcon from "@mui/icons-material/AddRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import DescriptionOutlinedIcon from "@mui/icons-material/DescriptionOutlined";
import ImageOutlinedIcon from "@mui/icons-material/ImageOutlined";
import InsertDriveFileOutlinedIcon from "@mui/icons-material/InsertDriveFileOutlined";
import {
  alpha,
  Avatar,
  Box,
  Dialog,
  DialogContent,
  IconButton,
  Tooltip,
  Typography,
  useTheme,
} from "@mui/material";
import {
  AttachmentPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  useAttachment,
} from "@assistant-ui/react";

const useFileSrc = (file: File | undefined) => {
  const [src, setSrc] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!file) {
      setSrc(undefined);
      return;
    }

    const objectUrl = URL.createObjectURL(file);
    setSrc(objectUrl);

    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [file]);

  return src;
};

const useAttachmentPreviewSrc = () => {
  const attachment = useAttachment();
  const isImage = attachment.type === "image" || attachment.contentType?.startsWith("image/");
  const fileSrc = useFileSrc(attachment.file);
  const contentPreview = useMemo(() => {
    if (!isImage) {
      return undefined;
    }

    if (!Array.isArray(attachment.content)) {
      return undefined;
    }

    for (const item of attachment.content) {
      if (item?.type === "image" && typeof item.image === "string") {
        return item.image;
      }

      if (item?.type === "file" && typeof item.data === "string" && item.mimeType?.startsWith("image/")) {
        return item.data;
      }
    }

    return undefined;
  }, [attachment.content, isImage]);

  return (isImage ? fileSrc : undefined) ?? contentPreview;
};

const AttachmentPreviewDialog: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [open, setOpen] = useState(false);
  const src = useAttachmentPreviewSrc();

  if (!src) {
    return <>{children}</>;
  }

  return (
    <>
      <Box component="button" type="button" onClick={() => setOpen(true)} sx={{ all: "unset", cursor: "pointer" }}>
        {children}
      </Box>
      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="md" fullWidth>
        <DialogContent
          sx={{
            p: 1.5,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            bgcolor: "background.default",
          }}
        >
          <Box
            component="img"
            src={src}
            alt="Attachment preview"
            sx={{ maxWidth: "100%", maxHeight: "80vh", objectFit: "contain", borderRadius: 2 }}
          />
        </DialogContent>
      </Dialog>
    </>
  );
};

const AttachmentThumb: React.FC = () => {
  const attachment = useAttachment();
  const muiTheme = useTheme();
  const src = useAttachmentPreviewSrc();
  const isImage = attachment.type === "image" || attachment.contentType?.startsWith("image/");

  return (
    <Avatar
      variant="rounded"
      sx={{
        width: "100%",
        height: "100%",
        borderRadius: 2.5,
        bgcolor: alpha(muiTheme.palette.text.primary, muiTheme.palette.mode === "dark" ? 0.14 : 0.06),
        color: alpha(muiTheme.palette.text.secondary, 0.9),
      }}
    >
      {src ? (
        <Box component="img" src={src} alt="Attachment preview" sx={{ width: "100%", height: "100%", objectFit: "cover" }} />
      ) : isImage ? (
        <ImageOutlinedIcon sx={{ fontSize: 26 }} />
      ) : attachment.type === "document" ? (
        <DescriptionOutlinedIcon sx={{ fontSize: 26 }} />
      ) : (
        <InsertDriveFileOutlinedIcon sx={{ fontSize: 26 }} />
      )}
    </Avatar>
  );
};

const AttachmentRemove: React.FC = () => {
  return (
    <AttachmentPrimitive.Remove asChild>
      <IconButton
        size="small"
        aria-label="Remove file"
        sx={{
          position: "absolute",
          top: 4,
          right: 4,
          width: 18,
          height: 18,
          bgcolor: "common.white",
          color: "text.secondary",
          boxShadow: "0 1px 4px rgba(0,0,0,0.18)",
          '&:hover': {
            bgcolor: "common.white",
            color: "error.main",
          },
        }}
      >
        <CloseRoundedIcon sx={{ fontSize: 12 }} />
      </IconButton>
    </AttachmentPrimitive.Remove>
  );
};

const AttachmentUI: React.FC<{ removable?: boolean }> = ({ removable = false }) => {
  const attachment = useAttachment();
  const muiTheme = useTheme();
  const isImage = attachment.type === "image" || attachment.contentType?.startsWith("image/");
  const typeLabel = attachment.type === "image" ? "Image" : attachment.type === "document" ? "Document" : "File";
  const previewLabel = `${typeLabel} attachment: ${attachment.name}`;
  const icon = isImage ? (
    <ImageOutlinedIcon sx={{ fontSize: 26 }} />
  ) : attachment.type === "document" ? (
    <DescriptionOutlinedIcon sx={{ fontSize: 26 }} />
  ) : (
    <InsertDriveFileOutlinedIcon sx={{ fontSize: 26 }} />
  );

  if (isImage) {
    return (
      <AttachmentPrimitive.Root>
        <Box
          sx={{
            position: "relative",
            width: 56,
            height: 56,
            flex: "0 0 auto",
          }}
        >
          <Tooltip title={attachment.name} arrow>
            <Box>
              <AttachmentPreviewDialog>
                <Box
                  role="button"
                  tabIndex={0}
                  aria-label={previewLabel}
                  sx={{
                    width: "100%",
                    height: "100%",
                    overflow: "hidden",
                    borderRadius: 2.5,
                    border: "1px solid",
                    borderColor: alpha(muiTheme.palette.text.primary, muiTheme.palette.mode === "dark" ? 0.18 : 0.1),
                    bgcolor: "action.hover",
                    transition: "opacity 160ms ease, transform 160ms ease",
                    '&:hover': {
                      opacity: 0.78,
                      transform: "translateY(-1px)",
                    },
                  }}
                >
                  <AttachmentThumb />
                </Box>
              </AttachmentPreviewDialog>
            </Box>
          </Tooltip>
          {removable ? <AttachmentRemove /> : null}
        </Box>
      </AttachmentPrimitive.Root>
    );
  }

  return (
    <AttachmentPrimitive.Root>
      <Tooltip title={attachment.name} arrow>
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1,
            minWidth: 0,
            maxWidth: 240,
            px: 1,
            py: 0.75,
            borderRadius: 3,
            border: "1px solid",
            borderColor: alpha(muiTheme.palette.text.primary, muiTheme.palette.mode === "dark" ? 0.18 : 0.1),
            bgcolor: "action.hover",
          }}
        >
          <Avatar
            variant="rounded"
            sx={{
              width: 34,
              height: 34,
              borderRadius: 2,
              bgcolor: alpha(muiTheme.palette.text.primary, muiTheme.palette.mode === "dark" ? 0.14 : 0.06),
              color: alpha(muiTheme.palette.text.secondary, 0.9),
              flex: "0 0 auto",
            }}
          >
            {icon}
          </Avatar>
          <Typography
            variant="body2"
            sx={{
              minWidth: 0,
              flex: 1,
              fontWeight: 600,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              color: "text.primary",
            }}
          >
            {attachment.name}
          </Typography>
          {removable ? (
            <AttachmentPrimitive.Remove asChild>
              <IconButton
                size="small"
                aria-label="Remove file"
                sx={{
                  width: 24,
                  height: 24,
                  color: "text.secondary",
                  flex: "0 0 auto",
                }}
              >
                <CloseRoundedIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </AttachmentPrimitive.Remove>
          ) : null}
        </Box>
      </Tooltip>
    </AttachmentPrimitive.Root>
  );
};

export const UserMessageAttachments: React.FC = () => {
  return (
    <Box sx={{ display: "flex", width: "100%", justifyContent: "flex-end", gap: 1, flexWrap: "wrap" }}>
      <MessagePrimitive.Attachments>
        {() => <AttachmentUI />}
      </MessagePrimitive.Attachments>
    </Box>
  );
};

export const ComposerAttachments: React.FC = () => {
  return (
    <Box sx={{ display: "flex", width: "100%", alignItems: "center", gap: 1, overflowX: "auto", flexWrap: "wrap" }}>
      <ComposerPrimitive.Attachments>
        {() => <AttachmentUI removable />}
      </ComposerPrimitive.Attachments>
    </Box>
  );
};

export const ComposerAddAttachment: React.FC<{ disabled?: boolean }> = ({ disabled = false }) => {
  const muiTheme = useTheme();

  return (
    <ComposerPrimitive.AddAttachment asChild>
      <IconButton
        size="small"
        disabled={disabled}
        aria-label="Add Attachment"
        sx={{
          width: 34,
          height: 34,
          borderRadius: 2.5,
          color: muiTheme.palette.mode === "dark" ? alpha("#f5f3ef", 0.82) : "#6f6a63",
          '&:hover': {
            bgcolor: muiTheme.palette.mode === "dark" ? alpha("#f5f3ef", 0.08) : alpha("#1f1d1a", 0.06),
          },
          '&.Mui-disabled': {
            color: alpha(muiTheme.palette.text.secondary, 0.4),
          },
        }}
      >
        <AddRoundedIcon fontSize="small" />
      </IconButton>
    </ComposerPrimitive.AddAttachment>
  );
};
