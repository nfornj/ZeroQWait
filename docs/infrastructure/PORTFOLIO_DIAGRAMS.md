# ZeroQwait Portfolio Diagrams

This page is designed for screenshots, presentations, portfolio posts, and LinkedIn-style architecture storytelling. Each section has one diagram and a short caption so you can use it as a slide deck in markdown form.

## How To Use This Page

- use one section per slide
- take screenshots of the Mermaid diagrams with the caption below each one
- pair the diagram title with a short spoken explanation rather than dense on-slide text

## 1. Product Surface Map

```mermaid
flowchart LR
    Customer[Customer] --> Receptionist[AI Receptionist]
    Owner[Shop Owner] --> Inbox[Agent Inbox]
    Owner --> Dashboard[Operations Dashboard]
    Owner --> Brain[Agent Brain]
    Employee[Employee] --> Dashboard
    Telegram[Telegram] --> Inbox
    Voice[Voice Interface] --> Receptionist
    Voice --> Inbox
```

Caption: ZeroQwait is not a single chatbot. It is a multi-surface product with distinct experiences for customers, owners, employees, voice interaction, and messaging channels.

## 2. High-Level Platform Architecture

```mermaid
flowchart TD
    subgraph Experience[Experience Layer]
        Receptionist[Customer AI Receptionist]
        OwnerUI[Owner Workspace]
        Voice[Voice Mode]
        Telegram[Telegram]
    end

    subgraph Orchestration[Orchestration Layer]
        Legacy[Legacy Customer Chat]
        AgentV2[Owner Agent API]
        Supervisor[Supervisor Graph]
        Specialists[Receptionist Finance HR CRM]
    end

    subgraph Services[Service Layer]
        MCP[MCP Services]
        Temporal[Temporal Workflows]
        VoiceStack[ASR and TTS]
        Odoo[Odoo CRM]
    end

    subgraph Data[State Layer]
        Postgres[(PostgreSQL)]
        Redis[(Redis)]
    end

    Receptionist --> Legacy
    OwnerUI --> AgentV2
    Voice --> VoiceStack
    Telegram --> AgentV2
    AgentV2 --> Supervisor
    Supervisor --> Specialists
    Specialists --> MCP
    Supervisor --> Temporal
    MCP --> Odoo
    AgentV2 --> Postgres
    AgentV2 --> Redis
    Legacy --> Postgres
    Legacy --> Redis
```

Caption: The core design separates experience surfaces, orchestration logic, service integrations, and state management. That makes the system easier to evolve and safer to operate.

## 3. Owner-Agent Execution Flow

```mermaid
flowchart LR
    OwnerMessage[Owner Message] --> Auth[Auth + Shop Scope]
    Auth --> State[Build Agent State]
    State --> Checkpoint[Load Checkpoint]
    Checkpoint --> Classify[Classify Intent]
    Classify --> Route[Route To Specialist]
    Route --> Tools[Execute Via MCP Or Integration]
    Tools --> Approval{Approval Needed?}
    Approval -->|Yes| Pause[Pause And Save Checkpoint]
    Pause --> Decision[Owner Approves Or Rejects]
    Decision --> Resume[Resume Graph]
    Approval -->|No| Respond[Respond]
    Resume --> Respond
```

Caption: The owner experience is a stateful workflow engine, not a stateless prompt-response loop. That is what enables safe execution and resumable approvals.

## 4. Specialist Agent Model

```mermaid
flowchart TD
    Supervisor[Supervisor] --> Receptionist[Receptionist Specialist]
    Supervisor --> Finance[Finance Specialist]
    Supervisor --> HR[HR Specialist]
    Supervisor --> CRM[CRM Specialist]

    Receptionist --> Booking[Booking MCP]
    Finance --> FinanceMCP[Finance MCP]
    Finance --> PostgresMCP[Postgres MCP]
    HR --> HRMCP[HR MCP]
    CRM --> OdooMCP[Odoo MCP]
```

Caption: Each specialist owns a narrower business domain, which keeps execution clearer and avoids turning one prompt into an unmaintainable catch-all system.

## 5. Human-In-The-Loop Control Plane

```mermaid
sequenceDiagram
    participant Owner
    participant UI as Agent Inbox
    participant API as Owner Agent API
    participant Graph as LangGraph Runtime
    participant DB as Checkpoint Store

    Owner->>UI: Request action
    UI->>API: POST /api/v2/agent/chat/stream
    API->>Graph: Execute graph
    Graph->>DB: Save checkpoint before action
    Graph-->>UI: approval_required event
    Owner->>UI: Approve or reject
    UI->>API: POST /api/v2/agent/approve
    API->>Graph: Resume from checkpoint
    Graph-->>UI: Final result
```

Caption: Approval is part of the runtime architecture. It is not simulated in the frontend. The system can pause, persist, and resume safely.

## 6. Voice Pipeline

```mermaid
flowchart LR
    Mic[Microphone] --> Recorder[Frontend Recorder]
    Recorder --> ASRRequest[/api/voice/transcribe]
    ASRRequest --> ASR[Whisper ASR]
    ASR --> Agent[Agent Runtime]
    Agent --> TTSRequest[/api/voice/tts]
    TTSRequest --> TTS[Qwen3-TTS Vivian]
    TTS --> Playback[Audio Playback]
```

Caption: Voice is handled through dedicated ASR and TTS services so conversational audio remains reliable and operationally isolated from the main backend.

## 7. Agent Brain Layer

```mermaid
flowchart TD
    Chat[Owner Conversations] --> Soul[SOUL Patterns]
    Chat --> Commitments[Commitment Scanner]
    Chat --> Schedules[Schedule Intent Parser]
    Soul --> Temporal[Temporal Workflows]
    Commitments --> Temporal
    Schedules --> Temporal
    Temporal --> Notifications[Notifications And Follow-Up]
    Temporal --> Inbox[Owner Inbox]
```

Caption: The platform goes beyond chat by preserving learned patterns, tracking promises, and turning natural-language intent into recurring operational workflows.

## 8. Local Runtime Topology

```mermaid
flowchart LR
    subgraph Compose[Docker Compose]
        FE[Frontend]
        BE[Backend]
        DB[(PostgreSQL)]
        Redis[(Redis)]
        MCPs[MCP Services]
        Odoo[Odoo]
        Temporal[Temporal]
        Worker[Temporal Worker]
    end

    FE --> BE
    BE --> DB
    BE --> Redis
    BE --> MCPs
    MCPs --> Odoo
    Worker --> Temporal
    Worker --> DB
    Worker --> Redis
```

Caption: Local development uses a single-stack runtime so the whole product can be tested quickly without reproducing the full production footprint.

## 9. Production Deployment Topology

```mermaid
flowchart TD
    Internet[zeroqwait.com] --> Ingress[Traefik Ingress]
    Ingress --> Frontend[Frontend Service]
    Ingress --> Backend[Backend Service]
    Backend --> Postgres[(PostgreSQL)]
    Backend --> Redis[(Redis)]
    Backend --> MCPs[MCP Services]
    Backend --> VoiceMCP[Voice MCP]
    Backend --> Temporal[Temporal Server]
    TemporalWorker[Temporal Worker] --> Temporal
    VoiceMCP --> ASR[ASR Service]
    VoiceMCP --> TTS[TTS Service]
    MCPs --> Odoo[Odoo]
```

Caption: Production separates application, data, workflow, voice, and integration services so the platform can scale and be operated as a real system rather than a demo stack.

## 10. Tier Isolation Strategy

```mermaid
flowchart LR
    subgraph FreeTier[Free Tier]
        FreeBackend[Shared Backend]
        FreeWorker[Shared Worker]
        FreeSchemas[Per-Shop Schemas]
    end

    subgraph PremiumTier[Premium Tier]
        PremiumBackend[Dedicated Backend]
        PremiumWorker[Dedicated Worker]
        PremiumData[Dedicated Runtime Assignment]
    end
```

Caption: The architecture supports a practical growth path: shared infrastructure for free-tier shops and stronger runtime isolation for premium shops, while keeping the same product codebase.

## Suggested Presentation Order

1. Product Surface Map
2. High-Level Platform Architecture
3. Owner-Agent Execution Flow
4. Human-In-The-Loop Control Plane
5. Agent Brain Layer
6. Voice Pipeline
7. Production Deployment Topology
8. Tier Isolation Strategy

## Companion Pages

- [ARCHITECTURE_CASE_STUDY.md](ARCHITECTURE_CASE_STUDY.md)
- [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md)
