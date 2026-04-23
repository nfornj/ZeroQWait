# Multi-Tenancy Architecture

## Overview

ZeroQwait currently uses an application-enforced multi-tenant model built around shop ownership, employee membership, and tenant-scoped agent execution.

The active design is:

- One PostgreSQL application database for core business data
- Shop-scoped authorization for owner and employee operations
- Tenant-aware LangGraph state keyed by shop and user
- Public-response sanitization for customer-facing endpoints

This file replaces the older subscription-tier and dedicated-database story.

## Current Isolation Model

### Application Data

Core business entities live in the main PostgreSQL database and are linked through explicit ownership fields and foreign keys:

- `users`
- `shops`
- `queues`
- `queue_items`
- `shop_employees`
- `employee_shifts`
- `conversation_history`

Isolation is enforced by:

- `owner_id` on shops
- `shop_id` on shop-owned records
- employee membership checks against `shop_employees`
- route-level permission helpers such as `check_shop_access(...)`

### Agent State

Owner-facing agent workflows add a second tenant boundary:

- `tenant_id` is injected into `AgentState` at request entry
- checkpoint thread IDs follow the shop-scoped pattern `tenant_{shop_id}_{user_id}`
- tool calls inherit tenant context and execute against the correct shop scope

### Public Surfaces

Customer and public endpoints use sanitized payloads so internal staffing or owner-only data is not leaked outside authenticated owner or employee flows.

## Runtime Components

### Backend Request Layer

- JWT authentication establishes the current user
- route dependencies enforce required or optional auth
- permission helpers determine shop ownership or employee access

### Data Layer

- SQLAlchemy sessions connect to the current PostgreSQL database
- `db_interface.py` provides domain-level access patterns used by routes and agent tools
- Redis is used for cache and transient state, not as the source of tenant truth

### Agent Layer

- LangGraph owner-agent flows run under shop-scoped context
- checkpoints are persisted in PostgreSQL
- approval-gated actions pause before high-impact writes

## Authorization Model

### Shop Owners

- can manage their own shops
- can access owner dashboards, analytics, and agent operations
- can add, remove, and reactivate employees for their shops

### Employees

- can access only assigned shops
- can perform employee-scoped queue and shift operations
- cannot perform owner-only configuration or billing actions

### Customers And Public Users

- can access public discovery and queue flows where allowed
- cannot access management endpoints or owner workspaces

## What Is Not Current

The following older ideas are not the active tenancy design:

- subscription-tier-specific dedicated databases
- per-tenant PostgreSQL database creation during upgrades
- physical database isolation for premium plans as the default product model

If that architecture is revisited later, it should be documented as a new design rather than assumed from this file.

## Operational Notes

- Keep all owner and employee actions tied to an explicit `shop_id`
- Prefer permission helpers over ad hoc ownership checks
- Keep agent requests tenant-scoped from the router entry point
- Treat shop-scoped thread IDs and checkpoint keys as part of the isolation model

## Useful References

- `permissions.py`
- `tenant_manager.py`
- `routers/agent_v2.py`
- `agents/state.py`
- `agents/checkpoints.py`

## Best Practices

1. ✅ Always use `get_database_for_user()` in API routes
2. ✅ Test migrations in staging first
3. ✅ Monitor tenant DB sizes
4. ✅ Set up alerts for failed migrations
5. ✅ Document tenant-specific configurations
6. ✅ Regular backup testing
7. ✅ Capacity planning for new tenants

## Support

For issues with multi-tenancy:
1. Check user's subscription tier
2. Verify tenant database exists
3. Check connection pool health
4. Review migration logs
5. Contact DevOps team
