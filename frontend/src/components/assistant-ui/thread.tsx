import React, { type FC, type ReactNode } from "react";
import { FolderPlus, ArrowUp, Square } from "lucide-react";
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
} from "../AssistantUIAttachment";
import { cn } from "../../lib/utils";

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
  return (
    <ComposerPrimitive.Root
      className="flex flex-col gap-0 overflow-hidden rounded-3xl border border-white/[0.08] bg-[#17181b]/[0.98] shadow-xl"
    >
      {/* Attachments row */}
      <div className="flex flex-wrap gap-1.5 px-3 pt-2.5 empty:hidden">
        <ComposerAttachments />
      </div>

      {/* Textarea */}
      <ComposerPrimitive.Input asChild>
        <textarea
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className={cn(
            "flex-1 resize-none border-none bg-transparent px-3.5 py-3 text-sm leading-relaxed tracking-[0.01em] text-foreground outline-none placeholder:text-muted-foreground",
            "min-h-[40px] max-h-[220px]",
          )}
        />
      </ComposerPrimitive.Input>

      {/* Toolbar */}
      <div className="flex items-center justify-between gap-2 border-t border-white/[0.08] bg-white/[0.02] px-2 py-1.5">
        {/* Left: attachment + folder */}
        <div className="flex items-center gap-0.5">
          <ComposerAddAttachment disabled={disabled} />
          <button
            type="button"
            disabled={disabled}
            onClick={onOpenFolderPicker}
            className={cn(
              "flex h-[34px] w-[34px] items-center justify-center rounded-[10px] text-white/80 transition-colors",
              "hover:bg-white/[0.08] disabled:opacity-40"
            )}
          >
            <FolderPlus className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1" />

        {/* Right: dictation + send/stop */}
        <div className="flex items-center gap-0.5">
          {dictationControl}
          {isRunning ? (
            <ComposerPrimitive.Cancel asChild>
              <button
                type="button"
                className="flex h-[34px] w-[34px] items-center justify-center rounded-[10px] bg-foreground text-background shadow-none hover:opacity-90"
              >
                <Square className="h-[18px] w-[18px]" />
              </button>
            </ComposerPrimitive.Cancel>
          ) : (
            <ComposerPrimitive.Send asChild>
              <button
                type="submit"
                className={cn(
                  "flex h-[34px] w-[34px] items-center justify-center rounded-[10px] bg-foreground text-background shadow-none",
                  "hover:opacity-90 disabled:bg-white/20 disabled:text-black/50"
                )}
              >
                <ArrowUp className="h-[18px] w-[18px]" />
              </button>
            </ComposerPrimitive.Send>
          )}
        </div>
      </div>
    </ComposerPrimitive.Root>
  );
};

export const ThreadWelcome: FC<{ title?: string; subtitle?: string }> = ({
  title = "Hello there!",
  subtitle = "How can I help you today?",
}) => {
  return (
    <div className="my-auto flex flex-1 flex-col justify-center px-4">
      <h2 className="text-4xl font-bold tracking-[-0.035em] text-foreground">{title}</h2>
      <p className="mt-1 text-xl font-normal tracking-[-0.02em] text-muted-foreground">{subtitle}</p>
    </div>
  );
};

export const AssistantMessage: FC = () => {
  return (
    <MessagePrimitive.Root data-role="assistant">
      <div className="w-full text-foreground">
        <MessagePrimitive.Parts />
      </div>
    </MessagePrimitive.Root>
  );
};

export const UserMessage: FC = () => {
  return (
    <MessagePrimitive.Root data-role="user">
      <UserMessageAttachments />
      <div className="flex w-full justify-end">
        <div className="max-w-[85%] rounded-2xl bg-muted px-4 py-2.5 text-foreground">
          <MessagePrimitive.Parts />
        </div>
      </div>
    </MessagePrimitive.Root>
  );
};

export const Thread: FC<ThreadProps> = ({
  welcome = <ThreadWelcome />,
  footer = <Composer />,
}) => {
  return (
    <ThreadPrimitive.Root className="flex flex-1 min-h-0 flex-col">
      <ThreadPrimitive.Viewport
        autoScroll
        className="flex flex-1 min-h-0 flex-col overflow-x-hidden overflow-y-auto"
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
