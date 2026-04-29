# Owner Document Knowledge Strategy

## Goal

Let shop owners upload operational documents into the owner workspace so the supervisor can answer questions from those documents without exposing them as public files.

## Current Product-Focused Implementation

This repo now supports a narrow first version focused on the owner workflow:

- Upload from the owner chat composer with a single attach action.
- Accept multiple files at once, including folder selections from the browser.
- Restrict ingestion to text-based formats that the backend can parse reliably today.
- Store original file bytes in PostgreSQL, not under public static URLs.
- Chunk extracted text into tenant-scoped `agent_memory` entries so the existing supervisor memory retrieval path can use them immediately.

## Security Model

### Access control

- Uploads are only available on authenticated owner endpoints.
- Every upload requires `shop_id` and passes the same owner-shop authorization check as the rest of `/api/v2/agent`.
- Stored documents are tenant-scoped with `shop_id` and `uploaded_by_user_id`.

### Storage

- Original bytes are stored in `agent_documents.file_blob`.
- No public `/static/...` URL is created for owner knowledge documents.
- File metadata includes checksum, MIME type, original filename, optional relative path, and ingestion status.

### Validation

- File count is capped per request.
- File size is capped per file.
- Only text-like file types are accepted in the current version: `txt`, `md`, `csv`, `json`, `html`, `xml`, `yaml`, `tsv`.
- Duplicate uploads are detected by shop-scoped SHA-256 checksum.

## Knowledge Ingestion Path

1. Owner selects files or a folder from the chat composer.
2. Frontend posts multipart form data to `/api/v2/agent/documents/upload`.
3. Backend validates shop ownership, file count, type, and size.
4. Backend extracts readable text from each file.
5. Backend stores the raw file bytes and extracted text in `agent_documents`.
6. Backend chunks extracted text into `agent_memory` rows with `memory_type="document"`.
7. Future owner chat requests reuse the existing `_build_memory_context()` flow, which already searches and injects relevant tenant memories into the supervisor graph.

## Why This Shape

- It avoids public file exposure.
- It reuses the existing owner-agent retrieval path instead of building a parallel document system.
- It stays tenant-scoped and product-specific.
- It avoids introducing a new external storage service before that is actually required.

## Current Limitations

- Binary office and PDF parsing are not enabled yet.
- Retrieval is still based on the current `agent_memory` search path, which is PostgreSQL text matching rather than dedicated vector retrieval.
- Documents are available to the supervisor as supporting context, not as a citation-aware retrieval UI yet.

## Recommended Next Phases

### Phase 2: Retrieval quality

- Add document summaries at upload time.
- Add per-chunk embeddings for `agent_documents` or `agent_memory` and rank with semantic search.
- Return source labels in the generated answer so owners can see which document informed the reply.

### Phase 3: Governance

- Add document listing, deletion, and re-index actions in the owner workspace.
- Add retention rules and soft-delete for document records.
- Add audit events for uploads, deletes, and re-ingestion.

### Phase 4: Rich document support

- Add PDF and office document extraction only after selecting and approving the exact parsing libraries.
- Keep extraction server-side and tenant-scoped.
- Preserve the rule that owner knowledge documents are never published via public static paths.

## Rule Of Thumb

Use the owner document flow for practical shop documents such as SOPs, FAQs, service notes, staffing notes, scripts, and policy text. Keep it scoped to “documents that help the supervisor answer owner questions better,” not a generic enterprise document platform.