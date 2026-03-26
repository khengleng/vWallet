# Operator Signup & Approval Flow (SaaS)

This document describes how an operator (company) signs up for the platform and gets approved before full access.

## Flow Overview

1. **Operator Signup**
   - Company submits a registration form:
     - Company name
     - Contact email
     - Admin user
     - Country/jurisdiction
     - Intended use case
   - System creates a `Tenant` with status `pending`.
   - Each company gets exactly **one tenant** by default.
   - That tenant includes the **full wallet platform capacities** (subject to approval).
   - Admin user is created but has **limited access** until approval.

2. **Review & Approval**
   - Internal ops/compliance team reviews:
     - Company legitimacy
     - Regulatory requirements
     - Risk profile
   - Tenant status transitions:
     - `pending` → `approved` or `rejected`

3. **Activation**
   - When approved:
     - Tenant becomes `active`
     - Default roles and limits are seeded
     - Full platform features are enabled
   - Notification sent to operator admin

## Status Definitions

- `pending`: Tenant created, awaiting review.
- `approved`: Passed review; ready for activation.
- `active`: Full capacity enabled.
- `rejected`: Application denied.
- `suspended`: Temporarily disabled due to compliance/abuse.

## Audit & Compliance

- Approval actions are logged.
- All status transitions are auditable.
- Each operator’s onboarding record is preserved for compliance review.
