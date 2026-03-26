# Multi-Tenant SaaS Roadmap (vWallet / 2M Platform)

This document outlines a phased plan to evolve the current single‑tenant wallet platform into a multi‑tenant SaaS. The goal is to allow multiple companies (tenants) such as “2M Platform” and “3M Platform” to run isolated instances with the same capabilities, branding, and controls.

## Goals

- Isolate data per tenant (no cross‑tenant access).
- Allow tenant‑specific branding and configuration.
- Support self‑service tenant onboarding.
- Keep operational workflows consistent across tenants.
- Operate as a SaaS: operators must sign up and be approved before full access.
- Each company gets exactly one tenant by default, with full platform capacities after approval.

## SaaS Operator Approval Model

This platform is designed as SaaS. Each company/operator must:

1. **Sign up as a new tenant**
   - Provide company details and an admin user.
   - Create a tenant record with status `pending`.

2. **Undergo approval**
   - Operations team reviews compliance and risk.
   - Tenant is activated only after approval.

3. **Gain full platform capacity**
   - Once approved, the tenant receives the full wallet platform features
     and default limits as defined for that tenant.
   - All users under that tenant inherit the tenant’s configured capacities.

## Phase 1: Core Tenant Model

1. **Tenant Entity**
   - `name`, `slug`, `status`, `created_at`
   - Branding: `display_name`, `logo_url`, `theme_color`
   - Settings: `currency`, `limits`, `anchoring_chain`, `support_email`

2. **Tenant Membership**
   - Add `tenant_id` to `User`
   - Ensure every user belongs to exactly one tenant

3. **Tenant Scoping**
   - Add `tenant_id` to all core models:
     - Wallets
     - Transactions
     - CashRequests
     - Anchors
     - Compliance profiles
     - Roles and role assignments
   - Enforce `tenant_id` filtering in every query and API endpoint

## Phase 2: Tenant Resolution

1. **Tenant Resolver Middleware**
   - Identify tenant by:
     - Subdomain (e.g., `2m.platform.com`)
     - Or request header `X-Tenant-ID`
   - Attach `request.tenant`

2. **Tenant‑Aware Auth**
   - Token issued with tenant context
   - All auth checks include tenant match

## Phase 3: Tenant Admin & Ops

1. **Tenant‑Scoped Admin**
   - Default admin sees only its tenant data
   - Super admin can switch tenants

2. **Role Seeding**
   - Each tenant gets default roles (`customer`, `agent`, `ops`)
   - Each tenant has independent role limits

## Phase 4: Tenant Signup (SaaS Onboarding)

1. **Tenant Registration Flow**
   - Create Tenant
   - Create Company Admin user
   - Seed roles + default limits
   - Apply branding + settings

2. **Tenant Settings UI**
   - Branding, limits, anchors, and KYC rules

## Tenant Membership Rules (Required)

These rules must be enforced once multi‑tenant mode is enabled:

1. **All users belong to exactly one tenant**
   - A user account cannot exist without a tenant.
   - The tenant is selected at signup or derived from subdomain.

2. **Tenant‑scoped sign up**
   - A user signing up under tenant A is **always** created inside tenant A.
   - The tenant is resolved by subdomain or `X-Tenant-ID`.

3. **Tenant‑scoped login**
   - A user can only log in to the tenant they belong to.
   - Tokens are issued with tenant context.

4. **Tenant‑scoped data access**
   - Every API query is filtered by `tenant_id`.
   - No cross‑tenant read or write is allowed.

5. **Tenant‑scoped roles and limits**
   - Roles are defined per tenant.
   - Limits apply inside that tenant only.

## Phase 5: Anchoring Strategy

1. **Shared Chain vs Dedicated Chain**
   - Shared chain with tenant ID embedded in hash payload
   - Or tenant‑specific chain/contract

2. **Tenant‑Specific Anchor Schedule**
   - Batch sizing and cadence per tenant

## Phase 6: Multi‑Tenant Mobile PWA

1. **Tenant Selection**
   - Tenant selection at login
   - Or auto‑resolve by subdomain

2. **Tenant Branding**
   - Dynamic logo + colors per tenant

## Notes

- This design keeps tenant isolation as the primary invariant.
- Every new feature should be built tenant‑first once this migration begins.

## Mobile Security Policy (Planned)

1. **PIN required for every financial action**
   - Transfer, withdraw, cash in/out, top‑up
   - Mobile app must submit `pin` with each action

2. **High‑value transactions require MFA**
   - Above `APPROVAL_WITHDRAW_THRESHOLD` or `APPROVAL_TRANSFER_THRESHOLD`
   - Mobile app must perform biometric (Face ID / Face Pass)
   - Backend requires an `mfa_token` or signed challenge proof

3. **Ops actions require higher‑level approval**
   - Admin or ops actions above thresholds must be approved
   - Two‑person approval policy enforced at the platform level

## Approval Workflow Extensions (Planned)

The platform already supports basic approval requests above thresholds. The following extensions are required:

1. **MFA‑gated approvals**
   - High‑value mobile transactions must include MFA proof before approval.
   - Approvers can only approve if the MFA proof is attached.

2. **Two‑person approval**
   - High‑risk actions require two distinct approvers.
   - Approver #2 must be different from the submitter and approver #1.

3. **Approval policy matrix**
   - Approval thresholds and number of approvers are configurable per tenant.

## Next Implementation Milestone (when you’re ready)

1. Create `Tenant` model
2. Add tenant middleware
3. Scope all queries to tenant
4. Add signup flow to create new tenants
