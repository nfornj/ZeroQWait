# Multi-Tenancy Architecture

## Status

This document is in transition, but the target model is now explicit:

- Free shops run on shared backend/agent compute and the shared PostgreSQL
	instance, with one schema per shop
- Premium shops keep one schema per shop and add dedicated backend/agent compute
- `subscription_tier` is an entitlement signal, not the runtime source of truth

The codebase now has explicit per-shop isolation metadata:

- `shops.data_isolation_mode` tracks whether shop-scoped rows live in `public`
	or a dedicated shop schema
- `shops.compute_mode` tracks whether the shop runs on shared or dedicated
	backend compute
- `shop_runtime_assignments` is the future control table for dedicated runtime
	placement

Today, the runtime is still mostly shared. `tenant_manager.py` has new
schema-for-all and runtime-assignment helpers, but ingress routing and dedicated
premium deployments are not fully implemented yet.

## Overview

ZeroQwait currently uses an application-enforced multi-tenant model built around shop ownership, employee membership, and tenant-scoped agent execution.

The active design is:

- One PostgreSQL application database for core business data
- One schema per shop for shop-scoped operational data
- Shop-scoped authorization for owner and employee operations
- Tenant-aware LangGraph state keyed by shop and user
- Shared backend/agent compute for free shops
- Dedicated backend/agent compute for premium shops
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

In the current transition state, shops carry explicit metadata:

- `data_isolation_mode = shared_public | shop_schema` (`shop_schema` is the target for all shops)
- `compute_mode = shared_instance | dedicated_instance`
- `shop_runtime_assignments` stores dedicated runtime placement for premium shops

`subscription_tier` remains the product entitlement and billing state. Runtime
placement should be driven by `compute_mode` plus `shop_runtime_assignments`.

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

When a shop is schema-isolated, the request-scoped database session sets
`search_path` to that shop schema plus `public`.

The target state is that every shop-scoped request resolves a shop schema,
including free shops on shared compute.

### Agent Layer

- LangGraph owner-agent flows run under shop-scoped context
- checkpoints are persisted in PostgreSQL
- approval-gated actions pause before high-impact writes
- free shops share the backend and Temporal/agent worker processes
- premium shops use dedicated backend and Temporal/agent worker processes while
	running the same agent code

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

The target direction currently being implemented is:

- schema-per-shop data isolation
- shared compute for free shops
- dedicated backend/worker compute for premium shops

Do not implement premium as a separate agent framework. Premium dedicated
agents are dedicated runtime processes for the same LangGraph agent graphs.

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
