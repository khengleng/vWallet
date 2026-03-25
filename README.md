# dj-wallets

[![PyPI version](https://badge.fury.io/py/dj-wallet.svg)](https://badge.fury.io/py/dj-wallet)
[![Python Versions](https://img.shields.io/pypi/pyversions/dj-wallet.svg)](https://pypi.org/project/dj-wallet/)
[![Django Versions](https://img.shields.io/pypi/djversions/dj-wallet.svg)](https://pypi.org/project/dj-wallet/)
[![License](https://img.shields.io/badge/license-MIT-purple)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-92%25-yellowgreen)](https://github.com/khaledsukkar2/dj-wallet)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/khaledsukkar2/dj-wallet)


A **secure**, **flexible**, and **powerful** virtual wallet system for Django applications.

*Inspired by [laravel-wallet](https://github.com/bavix/laravel-wallet)*

---

## What is a Virtual Wallet?

Think of this as a "digital balance system" inside your app. It doesn't handle real money directly (like Stripe or PayPal), but it keeps track of **any kind of value** for your users – whether that's money, points, credits, tokens, or any other unit.

**Use Cases:**
- 💰 **Virtual Currency**: E-commerce credits, in-app coins
- 🎮 **Gaming Points**: XP, gems, energy, lives
- 📚 **Learning Platforms**: Course credits, study tokens
- 🏆 **Loyalty Programs**: Reward points, cashback
- 🎁 **Gift Cards**: Prepaid balances, vouchers

- **Deposit**: Adds value to the user's balance.
- **Withdraw**: Takes value away from the balance.
- **Pay**: Automatically deducts the cost of an item from the user's wallet and (optionally) transfers it to the seller.
- **Safe**: Behind the scenes, the library ensures that two transactions can't happen at the exact same time to break the balance (Race Condition Protection).

---

## Features

- **Multi-Purpose Wallets**: Not just for money – use for points, credits, tokens, XP, or any value type.
- **Multi-Wallet Support**: Each user can have multiple wallets (default, savings, points, USD, etc.).
- **Atomic Transactions**: Ensures data integrity during concurrent operations.
- **Transfers & Exchanges**: Move funds between users or between different wallets of the same user.
- **Product Purchases**: Built-in support for purchasing items using wallet balance.
- **Polymorphic Holders**: Attach wallets to any Django model (Users, Organizations, Teams).
- **Admin Panel Integration**: Full Django admin support for managing wallets, transactions, and transfers.
- **Django Signals**: Hook into wallet events (deposits, withdrawals, transfers, etc.) for custom logic.
- **Cryptographic Audit Trail**: Hash-chain of transactions and optional signatures.
- **On-Chain Anchoring**: Create on-chain anchors for each completed transaction hash.
- **Compliance & Role Limits**: Enforce KYC, limits, and role-based permissions.
- **Optional API Layer**: REST endpoints for mobile integration (DRF).

---

## Installation

```bash
pip install dj-wallet
```

For API support:

```bash
pip install dj-wallet[drf]
```

For on-chain anchoring (Besu adapter):

```bash
pip install dj-wallet[chain]
```

For user-signing verification:

```bash
pip install dj-wallet[signing]
```

For queue-based workers:

```bash
pip install dj-wallet[queue]
```

Add to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    'dj_wallet',
]
```

Run migrations:

```bash
python manage.py migrate
```

---

## Hybrid Off-Chain + On-Chain Anchoring

Every completed transaction is hashed (with `prev_tx_hash`) and can be anchored on-chain.
This enables an auditable, tamper-evident ledger off-chain with on-chain proofs.

### Configure Anchoring

```python
# settings.py
dj_wallet = {
    "ANCHOR_CHAIN_NAME": "polygon",  # or any chain label you use
}

# Optional: provide a chain adapter class
DJ_WALLET_CHAIN_ADAPTER = "myapp.chain.PolygonAdapter"

# Besu adapter example
DJ_WALLET_CHAIN_ADAPTER = "dj_wallet.chain.besu.BesuAdapter"
DJ_WALLET_CHAIN_RPC_URL = "http://127.0.0.1:8545"
DJ_WALLET_CHAIN_ID = 20260321
DJ_WALLET_ANCHOR_CONTRACT_ADDRESS = "0xYourAnchorContract"
DJ_WALLET_CHAIN_PRIVATE_KEY = "0x..."
```

### Anchor Contract

A minimal Solidity contract is provided at `contracts/AnchorRegistry.sol`.
Deploy it to your Besu network and set `DJ_WALLET_ANCHOR_CONTRACT_ADDRESS`.

To submit pending anchors:

```bash
python manage.py anchor_pending --limit 100
```

To confirm submitted anchors:

```bash
python manage.py anchor_confirm --limit 100
```

---

## Queue-Based Anchoring (Celery + Redis)

Add a Celery app in your project and schedule the tasks:

```python
# myapp/celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myapp.settings")
app = Celery("myapp")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

```python
# settings.py
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"

CELERY_BEAT_SCHEDULE = {
    "anchor-pending-every-10s": {
        "task": "dj_wallet.tasks.submit_pending_anchors",
        "schedule": 10.0,
        "args": (100,),
    },
    "anchor-confirm-every-20s": {
        "task": "dj_wallet.tasks.confirm_submitted_anchors",
        "schedule": 20.0,
        "args": (100,),
    },
}
```

---

## Permissions, Compliance, and Signing

Permissions are tied to roles and balance. Compliance profiles are enforced automatically.
Transactions are HMAC-signed by default (custodial) using `DJ_WALLET_SIGNING_SECRET`.

```python
# settings.py
DJ_WALLET_SIGNING_SECRET = "change-me"

dj_wallet = {
    "PERMISSION_POLICY_CLASS": "dj_wallet.permissions.DefaultPermissionPolicy",
    "SIGNATURE_SERVICE_CLASS": "dj_wallet.signature.SignatureService",
    "COMPLIANCE_REQUIRE_KYC": ["withdraw", "transfer", "purchase"],
}
```

### Role & Compliance Setup (example)

```python
from dj_wallet.models import WalletRole, WalletRoleAssignment, ComplianceProfile

# Create a role with limits
basic = WalletRole.objects.create(
    slug="basic",
    name="Basic User",
    max_transfer_amount="5000",
    daily_outflow_limit="20000",
)

# Assign role to a user
WalletRoleAssignment.objects.create(holder=user, role=basic)

# Compliance profile
ComplianceProfile.objects.update_or_create(
    holder=user,
    defaults={"status": "verified", "risk_score": 12, "daily_limit": "25000"},
)
```

---

## Optional API Layer (Mobile)

Enable DRF and include the API routes:

```python
# settings.py
INSTALLED_APPS += ["rest_framework", "rest_framework.authtoken"]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "dj_wallet.api.throttles.BurstRateThrottle",
        "dj_wallet.api.throttles.SustainedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "wallet_burst": "60/min",
        "wallet_sustained": "1000/day",
    },
}

# Recommended headers from mobile clients:
# X-Device-Id, X-App-Version, X-Platform

# urls.py
urlpatterns += [path("api/", include("dj_wallet.api.urls"))]
```

### Onboarding (Register)

```http
POST /api/auth/register
{
  "username": "user1",
  "email": "user1@example.com",
  "password": "StrongPass123!"
}
```

Creates a user, a pending compliance profile, and assigns the `basic` role if it exists.

### Token Login

```http
POST /api/auth/token
{
  "username": "user1",
  "password": "StrongPass123!"
}
```

---

## Portal

Open the mobile money portal:

`http://localhost:8000/api/`

---

## Cash-In / Cash-Out (Agent Approval)

```http
POST /api/cashin/request
{ "agent_code": "AGENT-001", "amount": "50.00" }
```

```http
POST /api/cashout/request
{ "agent_code": "AGENT-001", "amount": "25.00" }
```

Admin approval endpoints:

```http
POST /api/cash/approve/<request_id>
POST /api/cash/reject/<request_id>
```

---

## P2P Transfers + Receipts

```http
POST /api/wallet/transfer
{
  "to_user_id": 2,
  "amount": "5.00",
  "note": "Lunch"
}
```

Response includes `receipt` reference.

---

## Statements

```http
GET /api/wallet/statement?from_date=2026-03-01&to_date=2026-03-25
```

---

## Funding Sources (Bank/ABA placeholders)

```http
POST /api/wallet/funding-sources
{
  "type": "aba",
  "label": "ABA Main",
  "account_ref": "ABA-123456"
}
```

```http
GET /api/wallet/funding-sources
```

---

## Agent Onboarding (Admin)

```http
POST /api/agents/onboard
{
  "user_id": 2,
  "code": "AGENT-001"
}
```

### User Signing (Mobile)

This API requires a signature for withdraw and transfer operations.
1. Request a nonce: `POST /api/wallet/nonce`
2. Sign the payload (JSON):

```json
{"holder_id": 123, "holder_type": "auth.user", "action": "withdraw", "amount": "10.00", "nonce": "<nonce>"}
```

3. Send `nonce`, `signature`, and `key_id` with the request.

Register user public keys using the `HolderKey` model.

---

## Quick Start

### 1. Simple Setup
Add the `WalletMixin` to your custom User model to give it wallet capabilities.

```python
from django.contrib.auth.models import AbstractUser
from dj_wallet.mixins import WalletMixin

class User(WalletMixin, AbstractUser):
    pass
```

### 2. Standard Operations

```python
user = User.objects.create(username="khaled")

# Deposit: Adds to balance
user.deposit(500.00)

# Check balance
print(user.balance) # 500.00

# Withdraw: Deducts from balance
user.withdraw(100.00)

# Transfer: Deducts from one, adds to another
recipient = User.objects.create(username="friend")
user.transfer(recipient, 50.00)
```

---

## 🏢 Polymorphic Wallet Holders

Wallets aren't just for users! The `WalletMixin` can be applied to **any Django model**, making it perfect for:

- **Organizations** with shared budgets
- **Teams** with allocated resources
- **Projects** with dedicated funds
- **Departments** with expense tracking
- **Game Characters** with in-game currency

### Example: Organization Wallets

```python
from django.db import models
from dj_wallet.mixins import WalletMixin

class Organization(WalletMixin, models.Model):
    name = models.CharField(max_length=100)

# Now organizations can have wallets just like users!
org = Organization.objects.create(name="Acme Corp")
org.deposit(10000.00)  # Company budget

# Create multiple wallets for different purposes
marketing_wallet = org.get_wallet("marketing")
marketing_wallet.deposit(5000.00)

development_wallet = org.get_wallet("development")
development_wallet.deposit(3000.00)
```

### Example: Team Resource Allocation

```python
class Team(WalletMixin, models.Model):
    name = models.CharField(max_length=100)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)

# Allocate resources from organization to team
team = Team.objects.create(name="Backend Team", organization=org)
org.transfer(team, 2000.00)  # Transfer budget to team

print(team.balance)  # 2000.00
```

This polymorphic design means you can model complex financial hierarchies: companies → departments → teams → employees, each with their own wallets and transfer capabilities.

---

## 🛒 Buying Things (`ProductMixin`)

The library includes a robust system for handling product purchases. To make any Django model "buyable," apply the `ProductMixin`. This allows wallets to interact directly with your business logic.

### 1. Implementation
To make an item purchasable, implement the `ProductMixin` in your model:

```python
from dj_wallet.mixins import ProductMixin
from django.db import models

class DigitalCourse(ProductMixin, models.Model):
    title = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def get_amount_product(self, customer):
        """REQUIRED: Return the price for this specific customer."""
        return self.price

    def can_buy(self, customer, quantity=1):
        """OPTIONAL: Check inventory or eligibility (default: True)."""
        return True

    def get_meta_product(self):
        """OPTIONAL: Add transaction metadata (default: {})."""
        return {"course_id": self.id}
```

### 2. Available Methods (ProductMixin)
These methods should be defined in your product class:

- **`get_amount_product(customer)`**: Returns the cost of the product. This is where you can implement dynamic pricing, discounts, or multi-currency logic.
- **`can_buy(customer, quantity)`**: Validation logic before purchase. Return `False` to block the transaction (e.g., if out of stock).
- **`get_meta_product()`**: Provide extra data that will be saved in the transaction's `meta` JSON field for auditing.

### 3. Processing a Purchase
A holder can pay for a product using the `.pay()` method.

```python
course = DigitalCourse.objects.get(id=1)

# This single line checks balance, validates availability, and transfers funds
try:
    transaction = user.pay(course)
    print("Course purchased successfully!")
except InsufficientFunds:
    print("Insufficient funds in wallet.")
except ProductNotAvailable:
    print("This item is currently out of stock.")
```

---

## Core Services

Django Wallets uses a component-based architecture where logic is encapsulated in services.

- **`WalletService`**: Base wallet operations (deposit, withdraw, reversals).
- **`TransferService`**: Fund movements between holders, refunds, and gifts.
- **`ExchangeService`**: Internal conversions between a holder's different wallets.
- **`PurchaseService`**: High-level logic for processing product payments.

---

## 🛠️ Available Methods Reference

### User/Holder Methods (via `WalletMixin`)
- **`.balance`**: Property that returns the current balance of the default wallet.
- **`.deposit(amount, meta=None, confirmed=True)`**: Adds funds to the default wallet. Supports metadata and unconfirmed states.
- **`.withdraw(amount, meta=None, confirmed=True)`**: Deducts funds. Raises `InsufficientFunds` if the balance is too low.
- **`.force_withdraw(amount)`**: Deducts funds regardless of balance (allows negative balance).
- **`.transfer(to_holder, amount)`**: Moves funds from this holder to another.
- **`.pay(product)`**: High-level method to purchase an item implementing `ProductMixin`.
- **`.get_wallet(slug)`**: Returns a specific wallet by name (creates it if it doesn't exist).
- **`.has_wallet(slug)`**: Checks if a wallet exists without creating it.
- **`.freeze_wallet(slug)`**: Locks a wallet from all incoming/outgoing transactions.
- **`.unfreeze_wallet(slug)`**: Re-enables a frozen wallet.
- **`.get_pending_transactions(slug)`**: Returns a QuerySet of transactions awaiting confirmation.

### 🏗️ Service Methods
For advanced usage, you can call services directly:

- **`WalletService.confirm_transaction(txn)`**: Moves a transaction from `PENDING` to `COMPLETED` and updates the wallet balance.
- **`WalletService.reverse_transaction(txn)`**: Perfectly undoes a transaction and records the reversal.
- **`TransferService.refund(transfer)`**: Reverses a transfer and returns money to the sender.
- **`ExchangeService.exchange(holder, from_slug, to_slug, amount)`**: Moves funds between two wallets owned by the same holder.

---

## Customization

### 1. Models
Extend the default models to add custom fields.

```python
from dj_wallet.abstract_models import AbstractWallet

class MyWallet(AbstractWallet):
    tax_exempt = models.BooleanField(default=False)

```

### 2. Mixins
Override existing logic or add helpers by extending the `WalletMixin`.

```python
from dj_wallet.mixins import WalletMixin

class MyCustomMixin(WalletMixin):
    def deposit(self, amount, meta=None, confirmed=True):
        print(f"User is depositing {amount}")
        return super().deposit(amount, meta, confirmed)

# settings.py
dj_wallet = {
    'WALLET_MIXIN_CLASS': 'myapp.mixins.MyCustomMixin',
}
```

### 3. Services
Override core business logic by extending the service classes.

```python
from dj_wallet.services.common import WalletService

class MyWalletService(WalletService):
    @classmethod
    def deposit(cls, wallet, amount, **kwargs):
        # Your custom logic here
        return super().deposit(wallet, amount, **kwargs)

# settings.py
dj_wallet = {
    'WALLET_SERVICE_CLASS': 'myapp.services.MyWalletService',
}
```

---

## 🛡️ Admin Panel Integration

Django Wallets comes with full Django Admin support out of the box. All models are registered with customized admin interfaces.
---

## 📡 Django Signals

Hook into wallet events for custom business logic, notifications, or integrations:

```python
from dj_wallet.signals import (
    balance_changed,
    transaction_created,
    wallet_created,
    transfer_completed,
    transaction_confirmed,
    pre_withdraw,
    pre_deposit,
)
from django.dispatch import receiver

@receiver(balance_changed)
def notify_user_of_balance_change(sender, wallet, transaction, **kwargs):
    """Send notification when balance changes."""
    print(f"Wallet {wallet.slug} balance changed by {transaction.amount}")

@receiver(transfer_completed)
def log_transfer(sender, transfer, from_wallet, to_wallet, **kwargs):
    """Log completed transfers for auditing."""
    print(f"Transfer from {from_wallet} to {to_wallet} completed")

@receiver(pre_withdraw)
def validate_withdrawal(sender, wallet, amount, meta, **kwargs):
    """Custom validation before withdrawal."""
    if amount > 10000:
        raise ValueError("Withdrawals over 10,000 require approval")
```

### Available Signals

| Signal | Trigger | Arguments |
|--------|---------|----------|
| `balance_changed` | After deposit/withdraw is confirmed | `wallet`, `transaction` |
| `transaction_created` | When any transaction is created | `transaction` |
| `wallet_created` | When a new wallet is created | `wallet`, `holder` |
| `transfer_completed` | After a transfer finishes | `transfer`, `from_wallet`, `to_wallet` |
| `transaction_confirmed` | When pending transaction is confirmed | `transaction` |
| `pre_withdraw` | Before a withdrawal (for validation) | `wallet`, `amount`, `meta` |
| `pre_deposit` | Before a deposit (for validation) | `wallet`, `amount`, `meta` |

## Support Us

If you find this project useful, please consider supporting its development.

### Star the Repository
Show some love by [starring the project on GitHub](https://github.com/khaledsukkar2/django-wallets)!

### Sponsorship & Donations
- **BTC**: `13X8aZ23pFNCH2FPW6YpRTw4PGxo7AvFkN`
- **USDT (TRC20)**: `TEitNDQMm4upYmNvFeMpxTRGEJGdord3S5`
- **USDT (BEP20)**: `0xc491a2ba6f386ddbf26cdc906939230036473f5d`

---

## License

MIT License. See [LICENSE](LICENSE) for details.
