# ZeroQwait Documentation

This folder contains the current documentation index for ZeroQwait.

## Source Of Truth

When documents disagree, use this order of precedence:

1. `../README.md`
2. `../claude.md`
3. Code and deployment scripts in the repo
4. Supporting documents in this `docs/` tree

The current project story is:

- Product: AI operations system for service businesses
- Current backend: FastAPI + LangGraph owner agents + legacy customer chat transition path
- Current data layer: PostgreSQL and Redis
- Current production deployment: K3s
- Current non-prod test deployment: single Docker Compose stack on `localhost`

## What Is Current

### Project Overviews

- [../README.md](../README.md): top-level product, stack, and development overview
- [../claude.md](../claude.md): detailed architecture, product rules, and deployment context
- [../deployment/docs/README.md](../deployment/docs/README.md): current deployment model and scripts
- [../backend/README.md](../backend/README.md): backend runtime and API overview

### Backend Docs

- [backend/PASSWORD_RESET_FEATURE.md](backend/PASSWORD_RESET_FEATURE.md): current password reset behavior
- [backend/ANALYTICS_SYSTEM.md](backend/ANALYTICS_SYSTEM.md): analytics-related implementation notes
- [backend/EMPLOYEE_SETUP_INSTRUCTIONS.md](backend/EMPLOYEE_SETUP_INSTRUCTIONS.md): employee and staffing setup details

### Setup Docs

- [setup/ENVIRONMENT_SETUP.md](setup/ENVIRONMENT_SETUP.md): environment setup notes
- [setup/EMAIL_SETUP.md](setup/EMAIL_SETUP.md): email configuration
- [setup/SECURITY.md](setup/SECURITY.md): security-related guidance

## Folder Guide

```text
docs/
├── README.md                 This index
├── backend/                  Feature and implementation notes for backend subsystems
├── archive/                  Retained documents that are not part of the active top-level story
├── frontend/                 Feature notes for frontend surfaces
├── infrastructure/           Infrastructure and domain notes
├── setup/                    Setup, email, and security docs
├── testing/                  Test summaries and validation notes
└── examples/                 Example snippets and historical schemas
```

## Recommended Reading By Goal

### I need the current product overview

- Start with [../README.md](../README.md)
- Then read [../claude.md](../claude.md)

### I need to run the stack locally

- Start with [../README.md](../README.md)
- Then read [../deployment/docs/README.md](../deployment/docs/README.md)

### I need backend architecture context

- Start with [../backend/README.md](../backend/README.md)
- Then read [../claude.md](../claude.md)

## Documentation Cleanup Standard

When updating docs in this repo:

- Describe ZeroQwait as an AI operations system for service businesses
- Document PostgreSQL and Redis as the active data and cache layers
- Document K3s as the active production deployment model
- Document the `localhost:3000` and `localhost:8000` test stack as the active non-prod path
- Remove outdated wording when updating a document instead of layering warning text onto it

## Need Help

- Check [../README.md](../README.md) first
- Use [../claude.md](../claude.md) for architectural context
- Use [../deployment/docs/README.md](../deployment/docs/README.md) for deployment questions
- Use repo search if you need to confirm whether an older doc is still true
