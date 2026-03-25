# vWallet Mobile Integration (Quick Start)

Base URL (local): `http://127.0.0.1:8000/api`

## 1) Auth

### Get token
```bash
curl -X POST http://127.0.0.1:8000/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"user","password":"WingBank@123$"}'
```

Use the returned token as:
```
Authorization: Token <TOKEN>
```

## 2) Get signing nonce
```bash
curl -X POST http://127.0.0.1:8000/api/wallet/nonce \
  -H "Authorization: Token <TOKEN>"
```

## 3) Build signed payload (secp256k1)

Payload format:
```json
{
  "holder_id": 2,
  "holder_type": "auth.user",
  "action": "transfer",
  "amount": "1.00000000",
  "nonce": "<NONCE>"
}
```

Sign it with Ethereum-style `personal_sign` (EIP-191). Example in JS:

```js
import { ethers } from "ethers";

const payload = {
  holder_id: 2,
  holder_type: "auth.user",
  action: "transfer",
  amount: "1.00000000",
  nonce: "<NONCE>"
};

const message = JSON.stringify(payload);
const wallet = new ethers.Wallet("0x4977dd85ef7e3328201ed0638d295938bfc3fcacbe14fa2d68a21c9778b6faa0");
const signature = await wallet.signMessage(message);
console.log(signature);
```

## 4) Transfer (signed)
```bash
curl -X POST http://127.0.0.1:8000/api/wallet/transfer \
  -H "Authorization: Token <TOKEN>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: tx-001" \
  -d '{
    "to_user_id": 1,
    "amount": "1.00000000",
    "nonce": "<NONCE>",
    "signature": "0x...",
    "key_id": "user-0x9c92a1675533389b29b4b8b41f6233b9d776b1dc",
    "note": "mobile transfer"
  }'
```

## 5) Deposit (no signature)
```bash
curl -X POST http://127.0.0.1:8000/api/wallet/deposit \
  -H "Authorization: Token <TOKEN>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: dep-001" \
  -d '{"amount":"10.00","meta":{"action":"mobile_deposit"}}'
```

## 6) Withdraw (signed)
```bash
curl -X POST http://127.0.0.1:8000/api/wallet/withdraw \
  -H "Authorization: Token <TOKEN>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: wdr-001" \
  -d '{
    "amount":"1.00000000",
    "nonce":"<NONCE>",
    "signature":"0x...",
    "key_id":"user-0x9c92a1675533389b29b4b8b41f6233b9d776b1dc"
  }'
```

## 7) Cash in / out
```bash
curl -X POST http://127.0.0.1:8000/api/cashin/request \
  -H "Authorization: Token <TOKEN>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: cashin-001" \
  -d '{"agent_code":"AGENT1","amount":"5.00"}'
```

```bash
curl -X POST http://127.0.0.1:8000/api/cashout/request \
  -H "Authorization: Token <TOKEN>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: cashout-001" \
  -d '{"agent_code":"AGENT1","amount":"3.00"}'
```

## Notes
- For production, store the private key in secure hardware (HSM/KMS).
- Device ID is required for withdraw/transfer (send `X-Device-Id` header).
