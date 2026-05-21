# ZeroQwait Documentation

This directory is the working documentation set for ZeroQwait: product story, architecture, setup, security, and validation.

ZeroQwait is an AI operations platform for service businesses. The system combines a customer-facing AI receptionist, an owner-facing supervisor agent, specialist business agents, voice interfaces, Human-in-the-Loop approvals, and multi-tenant operational infrastructure.

## Start Here

If you want the strongest high-level narrative first, read these in order:

1. [infrastructure/TECHNICAL_ARCHITECTURE.md](infrastructure/TECHNICAL_ARCHITECTURE.md)
2. [../claude.md](../claude.md)
3. [../README.md](../README.md)

## Source Of Truth

When documents disagree, use this order of precedence:

1. [../claude.md](../claude.md)
2. Active runtime configuration in the repo: `docker-compose.yml`, `k8s-manifests/`, `deployment/scripts/`, backend and frontend source
3. [../README.md](../README.md)
4. Supporting documents in this `docs/` tree

This ordering is intentional. The architecture has evolved quickly, and the detailed operating context lives closest to `claude.md` and the runtime surfaces.

## Documentation Map

### Architecture And Showcase

- [infrastructure/TECHNICAL_ARCHITECTURE.md](infrastructure/TECHNICAL_ARCHITECTURE.md): professional platform overview, architecture diagrams, execution model, and implementation highlights
- [infrastructure/ARCHITECTURE_CASE_STUDY.md](infrastructure/ARCHITECTURE_CASE_STUDY.md): public-facing narrative for portfolio, interviews, and stakeholder walkthroughs
- [infrastructure/PORTFOLIO_DIAGRAMS.md](infrastructure/PORTFOLIO_DIAGRAMS.md): diagram-first architecture deck for screenshots, presentations, and social posts
- [../claude.md](../claude.md): deep product, architecture, safety, deployment, and transition context
- [../README.md](../README.md): repo-level summary and contributor entry point

### Setup And Operations

- [setup/ENVIRONMENT_SETUP.md](setup/ENVIRONMENT_SETUP.md): current local runtime model, environment variables, provider strategy, and service topology
- [setup/EMAIL_SETUP.md](setup/EMAIL_SETUP.md): password reset and email delivery setup
- [setup/SECURITY.md](setup/SECURITY.md): security and isolation guidance

### Feature And Subsystem Notes

- [backend/ANALYTICS_SYSTEM.md](backend/ANALYTICS_SYSTEM.md): analytics implementation notes
- [backend/PASSWORD_RESET_FEATURE.md](backend/PASSWORD_RESET_FEATURE.md): password reset behavior
- [backend/EMPLOYEE_SETUP_INSTRUCTIONS.md](backend/EMPLOYEE_SETUP_INSTRUCTIONS.md): employee setup and staffing flows
- [backend/OWNER_DOCUMENT_KNOWLEDGE_STRATEGY.md](backend/OWNER_DOCUMENT_KNOWLEDGE_STRATEGY.md): owner knowledge ingestion approach
- [frontend/IN_SHOP_DISPLAY.md](frontend/IN_SHOP_DISPLAY.md): in-shop display surface details

### Validation And Infra Notes

- [testing/TESTING_SUMMARY.md](testing/TESTING_SUMMARY.md): current validation flows and smoke checks
- [infrastructure/QUICKSTART_SUBDOMAINS.md](infrastructure/QUICKSTART_SUBDOMAINS.md): wildcard ingress and subdomain testing notes
- [infrastructure/DOMAIN_MIGRATION.md](infrastructure/DOMAIN_MIGRATION.md): domain migration notes for zeroqwait.com

## Folder Guide

```text
docs/
├── README.md                         Documentation hub
├── backend/                          Backend subsystem and feature notes
├── examples/                         Examples, samples, and historical reference material
├── frontend/                         Frontend surface notes
├── infrastructure/                   Architecture, platform, domains, and deployment context
├── setup/                            Environment, email, and security setup
└── testing/                          Test paths and validation guidance
```

## Recommended Reading By Goal

### I want the best showcase of the product and architecture

- Start with [infrastructure/ARCHITECTURE_CASE_STUDY.md](infrastructure/ARCHITECTURE_CASE_STUDY.md)
- Then use [infrastructure/PORTFOLIO_DIAGRAMS.md](infrastructure/PORTFOLIO_DIAGRAMS.md)
- Start with [infrastructure/TECHNICAL_ARCHITECTURE.md](infrastructure/TECHNICAL_ARCHITECTURE.md)
- Then read [../claude.md](../claude.md)

### I need to run the stack locally

- Start with [setup/ENVIRONMENT_SETUP.md](setup/ENVIRONMENT_SETUP.md)
- Then read [../deployment/docs/README.md](../deployment/docs/README.md)

### I need the owner-agent architecture

- Start with [infrastructure/TECHNICAL_ARCHITECTURE.md](infrastructure/TECHNICAL_ARCHITECTURE.md)
- Then inspect `backend/agents/`, `backend/routers/agent_v2.py`, and `frontend/src/features/agent-inbox/`

### I need deployment context

- Start with [../deployment/docs/README.md](../deployment/docs/README.md)
- Then read [infrastructure/TECHNICAL_ARCHITECTURE.md](infrastructure/TECHNICAL_ARCHITECTURE.md)

## Documentation Standard

When updating docs in this repo:

- describe ZeroQwait as an AI operations platform for service businesses
- distinguish clearly between implemented systems, transition paths, and approved next-stage architecture
- document `http://localhost:3000` and `http://localhost:8000` as the canonical local non-prod URLs unless a doc is specifically about ingress
- document K3s and `https://zeroqwait.com` as the active production path
- prefer replacing stale statements over layering warnings on top of outdated text

## Need Help

- Use [infrastructure/TECHNICAL_ARCHITECTURE.md](infrastructure/TECHNICAL_ARCHITECTURE.md) for a polished overview
- Use [../claude.md](../claude.md) for detailed operating context
- Use [../deployment/docs/README.md](../deployment/docs/README.md) for deployment questions
- Validate assumptions against code and runtime manifests when a document looks older than the implementation
