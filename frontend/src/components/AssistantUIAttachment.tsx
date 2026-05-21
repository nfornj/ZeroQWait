import React, { useEffect, useMemo, useState } from "react";
import { Plus, X, FileText, ImageIcon, File } from "lucide-react";
import {
  AttachmentPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  useAttachment,
} from "@assistant-ui/react";
import {
  Dialog,
  DialogContent,
} from "./ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "./ui/tooltip";
import { cn } from "../lib/utils";

const useFileSrc = (file: File | undefined) => {
  const [src, setSrc] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!file) { setSrc(undefined); return; }
    const url = URL.createObjectURL(file);
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  return src;
};

const useAttachmentPreviewSrc = () => {
  const attachment = useAttachment();
  const isImage = attachment.type === "image" || attachment.contentType?.startsWith("image/");

  const contentPreview = useMemo(() => {
    if (!isImage || !Array.isArray(attachment.content)) return undefined;
    for (const item of attachment.content) {
      if (item?.type === "image" && typeof item.image === "string") return item.image;
      if (item?.type === "file" && typeof item.data === "string" && item.mimeType?.startsWith("image/")) return item.data;
    }
    return undefined;
  }, [attachment.content, isImage]);

  const fileSrc = useFileSrc(isImage ? attachment.file : undefined);
  return fileSrc ?? contentPreview;
};

const AttachmentPreviewDialog: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [open, setOpen] = useState(false);
  const src = useAttachmentPreviewSrc();

  if (!src) return <>{children}</>;

  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="cursor-pointer border-none bg-transparent p-0">
        {children}
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl">
          <div className="flex items-center justify-center p-2">
            <img src={src} alt="Attachment preview" className="max-h-[80vh] max-w-full rounded-xl object-contain" />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

const AttachmentThumb: React.FC = () => {
  const attachment = useAttachment();
  const src = useAttachmentPreviewSrc();
  const isImage = attachment.type === "image" || attachment.contentType?.startsWith("image/");

  return (
    <div className="flex h-full w-full items-center justify-center rounded-xl bg-white/10 text-muted-foreground">
      {src ? (
        <img src={src} alt="Attachment preview" className="h-full w-full rounded-xl object-cover" />
      ) : isImage ? (
        <ImageIcon className="h-6 w-6" />
      ) : attachment.type === "document" ? (
        <FileText className="h-6 w-6" />
      ) : (
        <File className="h-6 w-6" />
      )}
    </div>
  );
};

const AttachmentRemove: React.FC = () => {
  return (
    <AttachmentPrimitive.Remove asChild>
      <button
        type="button"
        aria-label="Remove file"
        className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-white text-gray-600 shadow hover:text-red-500"
      >
        <X className="h-3 w-3" />
      </button>
    </AttachmentPrimitive.Remove>
  );
};

const AttachmentUI: React.FC<{ removable?: boolean }> = ({ removable = false }) => {
  const attachment = useAttachment();
  const isImage = attachment.type === "image" || attachment.contentType?.startsWith("image/");
  const previewLabel = `${attachment.type ?? "File"} attachment: ${attachment.name}`;
  const Icon = isImage ? ImageIcon : attachment.type === "document" ? FileText : File;

  if (isImage) {
    return (
      <AttachmentPrimitive.Root>
        <div className="relative h-14 w-14 flex-shrink-0">
          <Tooltip>
            <TooltipTrigger asChild>
              <div>
                <AttachmentPreviewDialog>
                  <div
                    role="button"
                    tabIndex={0}
                    aria-label={previewLabel}
                    className="h-14 w-14 overflow-hidden rounded-xl border border-white/20 bg-muted transition-all hover:opacity-75 hover:-translate-y-px"
                  >
                    <AttachmentThumb />
                  </div>
                </AttachmentPreviewDialog>
              </div>
            </TooltipTrigger>
            <TooltipContent>{attachment.name}</TooltipContent>
          </Tooltip>
          {removable && <AttachmentRemove />}
        </div>
      </AttachmentPrimitive.Root>
    );
  }

  return (
    <AttachmentPrimitive.Root>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex min-w-0 max-w-[240px] items-center gap-2 rounded-2xl border border-white/20 bg-muted px-2.5 py-2">
            <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-white/10 text-muted-foreground">
              <Icon className="h-5 w-5" />
            </div>
            <span className="flex-1 truncate text-sm font-semibold text-foreground">
              {attachment.name}
            </span>
            {removable && (
              <AttachmentPrimitive.Remove asChild>
                <button
                  type="button"
                  aria-label="Remove file"
                  className="flex h-5 w-5 flex-shrink-0 items-center justify-center text-muted-foreground hover:text-foreground"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </AttachmentPrimitive.Remove>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent>{attachment.name}</TooltipContent>
      </Tooltip>
    </AttachmentPrimitive.Root>
  );
};

export const UserMessageAttachments: React.FC = () => {
  return (
    <div className="flex w-full flex-wrap justify-end gap-2">
      <MessagePrimitive.Attachments>
        {() => <AttachmentUI />}
      </MessagePrimitive.Attachments>
    </div>
  );
};

export const ComposerAttachments: React.FC = () => {
  return (
    <div className="flex w-full flex-wrap items-center gap-2 overflow-x-auto">
      <ComposerPrimitive.Attachments>
        {() => <AttachmentUI removable />}
      </ComposerPrimitive.Attachments>
    </div>
  );
};

export const ComposerAddAttachment: React.FC<{ disabled?: boolean }> = ({ disabled = false }) => {
  return (
    <ComposerPrimitive.AddAttachment asChild>
      <button
        type="button"
        disabled={disabled}
        aria-label="Add Attachment"
        className={cn(
          "flex h-[34px] w-[34px] items-center justify-center rounded-full text-muted-foreground transition-colors",
          "hover:bg-muted hover:text-foreground disabled:opacity-40"
        )}
      >
        <Plus className="h-4 w-4" />
      </button>
    </ComposerPrimitive.AddAttachment>
  );
};
