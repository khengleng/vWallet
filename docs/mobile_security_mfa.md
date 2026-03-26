# Mobile PWA Security (Implementation Scope)

This document defines the mobile (PWA) security controls to be implemented first.

## Rules (Mobile Only)

1. **PIN required for every financial action**
   - Transfer, withdraw, cash in/out, top‑up
   - PIN is verified on the server for each action

2. **High‑value requires MFA**
   - If amount >= `APPROVAL_WITHDRAW_THRESHOLD` or `APPROVAL_TRANSFER_THRESHOLD`
   - Mobile must perform an MFA step (biometric in native app later)
   - Backend requires `mfa_token` proof

3. **No multi‑person approval for mobile**
   - High‑value mobile uses MFA instead of approval workflow

## Endpoints (Planned)

1. `POST /api/auth/pin/set`  
   - Body: `{ "pin": "1234" }`

2. `POST /api/auth/mfa/challenge`  
   - Body: `{ "action": "transfer", "amount": "5000" }`  
   - Returns: `challenge_id`, `expires_at` (and `code` in debug only)

3. `POST /api/auth/mfa/verify`  
   - Body: `{ "challenge_id": "...", "code": "123456" }`  
   - Returns: `mfa_token`, `expires_at`

## Enforcement (Planned)

- Mobile requests are detected by `X-Platform: pwa`.
- Financial actions require:
  - `pin` always
  - `mfa_token` if high‑value

