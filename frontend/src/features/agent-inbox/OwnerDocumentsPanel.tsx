import React from "react";
import { Trash2, RefreshCw, FileText } from "lucide-react";
import { Button } from "../../components/ui/button";
import { useOwnerBrand } from "../../hooks/useOwnerBrand";
import type { OwnerDocumentRecord } from "./types";

interface OwnerDocumentsPanelProps {
  documents: OwnerDocumentRecord[];
  isLoading?: boolean;
  actingDocumentId?: number | null;
  actingType?: "reindex" | "delete" | null;
  onReindex: (document: OwnerDocumentRecord) => void;
  onDelete: (document: OwnerDocumentRecord) => void;
}

const formatBytes = (sizeBytes: number): string => {
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
};

const formatTimestamp = (value?: string | null): string => {
  if (!value) return "Unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";
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
  onReindex,
  onDelete,
}) => {
  const brand = useOwnerBrand();

  return (
    <div
      className="rounded-2xl border backdrop-blur-xl"
      style={{
        borderColor: brand.glass.border,
        backgroundColor: brand.glass.bg,
        boxShadow: `0 18px 50px ${brand.primary}14`,
      }}
    >
      <div className="px-4 py-3">
        {/* Header */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div>
            <p className="text-base font-semibold">Knowledge documents</p>
            <p className="text-sm text-muted-foreground">
              Private owner files stored securely and indexed into shared shop context.
            </p>
          </div>
          <span
            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-bold flex-shrink-0"
            style={{
              backgroundColor: `${brand.primary}1f`,
              color: brand.primary,
            }}
          >
            <FileText className="h-3 w-3" />
            {documents.length}
          </span>
        </div>

        <hr className="mb-3" style={{ borderColor: `${brand.primary}1f` }} />

        {isLoading ? (
          <div className="flex items-center gap-2 py-2">
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-border border-t-primary" />
            <p className="text-sm text-muted-foreground">Loading uploaded documents...</p>
          </div>
        ) : documents.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Upload files from the chat composer to build a shop-specific knowledge base.
          </p>
        ) : (
          <div className="flex flex-col gap-3 max-h-96 overflow-y-auto pr-1">
            {documents.map((document, index) => {
              const isReindexing = actingDocumentId === document.id && actingType === "reindex";
              const isDeleting = actingDocumentId === document.id && actingType === "delete";

              return (
                <React.Fragment key={document.id}>
                  <div className="flex flex-col gap-2">
                    <div className="flex items-start gap-3">
                      <div
                        className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                        style={{
                          backgroundColor: `${brand.primary}1f`,
                          color: brand.primary,
                        }}
                      >
                        <FileText className="h-4 w-4" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p
                          className="text-sm font-semibold truncate"
                          style={{ color: brand.secondary }}
                        >
                          {document.relative_path || document.filename}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatBytes(document.size_bytes)} · {document.chunk_count} chunk
                          {document.chunk_count === 1 ? "" : "s"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Updated {formatTimestamp(document.updated_at || document.created_at)}
                        </p>
                      </div>
                      <span
                        className="inline-flex items-center rounded-full px-2 py-0.5 text-xs border capitalize flex-shrink-0"
                        style={{
                          backgroundColor: `${brand.primary}14`,
                          color: brand.primary,
                          borderColor: `${brand.primary}29`,
                        }}
                      >
                        {document.knowledge_status.replace(/_/g, " ")}
                      </span>
                    </div>

                    <div className="flex gap-2 justify-end">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={Boolean(actingDocumentId)}
                        onClick={() => onReindex(document)}
                        className="rounded-full h-7 text-xs font-bold"
                      >
                        {isReindexing ? (
                          <>
                            <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-border border-t-primary mr-1" />
                            Re-indexing...
                          </>
                        ) : (
                          <>
                            <RefreshCw className="h-3 w-3 mr-1" />
                            Re-index
                          </>
                        )}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={Boolean(actingDocumentId)}
                        onClick={() => onDelete(document)}
                        className="rounded-full h-7 text-xs font-bold text-red-400 hover:text-red-300 hover:bg-red-500/10"
                      >
                        {isDeleting ? (
                          <>
                            <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-red-500/30 border-t-red-400 mr-1" />
                            Removing...
                          </>
                        ) : (
                          <>
                            <Trash2 className="h-3 w-3 mr-1" />
                            Delete
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                  {index < documents.length - 1 && (
                    <hr style={{ borderColor: `${brand.primary}14` }} />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default OwnerDocumentsPanel;
