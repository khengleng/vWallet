from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.db import models

from .abstract_models import AbstractTransaction, AbstractTransfer, AbstractWallet
from .conf import wallet_settings
import uuid


class Wallet(AbstractWallet):
    """
    Concrete Wallet model.
    For custom wallet models, extend AbstractWallet instead.
    """


class Transaction(AbstractTransaction):
    """
    Concrete Transaction model.
    For custom transaction models, extend AbstractTransaction instead.
    """

    # The specific wallet this transaction affects
    wallet = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name="transactions"
    )


class Transfer(AbstractTransfer):
    """
    Concrete Transfer model.
    For custom transfer models, extend AbstractTransfer instead.
    """

    # The transaction withdrawing money from sender
    withdraw = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="transfer_withdraw"
    )

    # The transaction depositing money to receiver
    deposit = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="transfer_deposit"
    )


class TransactionSignature(models.Model):
    """
    Stores cryptographic signatures for transactions.
    """

    SCHEME_HMAC_SHA256 = "hmac-sha256"
    SCHEME_ED25519 = "ed25519"
    SCHEME_SECP256K1 = "secp256k1"

    SCHEME_CHOICES = (
        (SCHEME_HMAC_SHA256, "HMAC-SHA256"),
        (SCHEME_ED25519, "Ed25519"),
        (SCHEME_SECP256K1, "Secp256k1"),
    )

    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="signatures"
    )
    scheme = models.CharField(max_length=32, choices=SCHEME_CHOICES)
    public_key = models.TextField(blank=True, default="")
    signature = models.TextField()
    key_id = models.CharField(max_length=128, blank=True, default="")

    # Optional signer (user, org, service account)
    signer_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    signer_id = models.PositiveIntegerField(null=True, blank=True)
    signer = GenericForeignKey("signer_type", "signer_id")

    created_at = models.DateTimeField(auto_now_add=True)


class MobileSecurityProfile(models.Model):
    """
    Mobile PIN profile for a user (PWA / native).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mobile_security"
    )
    pin_hash = models.CharField(max_length=128, blank=True, default="")
    pin_set_at = models.DateTimeField(null=True, blank=True)
    pin_failed_count = models.PositiveSmallIntegerField(default=0)
    pin_locked_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class MfaChallenge(models.Model):
    """
    MFA challenge for high-value mobile actions.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action = models.CharField(max_length=64)
    amount = models.DecimalField(
        max_digits=64, decimal_places=wallet_settings.WALLET_MATH_SCALE
    )
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    mfa_token = models.CharField(max_length=128, blank=True, default="")
    mfa_expires_at = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)


class ChainAnchor(models.Model):
    """
    On-chain anchor record for a transaction hash.
    """

    STATUS_PENDING = "pending"
    STATUS_SUBMITTED = "submitted"
    STATUS_CONFIRMED = "confirmed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_FAILED, "Failed"),
    )

    transaction = models.OneToOneField(
        Transaction, on_delete=models.CASCADE, related_name="anchor"
    )
    chain = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    onchain_tx_hash = models.CharField(max_length=256, blank=True, default="")
    error = models.TextField(blank=True, default="")
    attempts = models.PositiveIntegerField(default=0)

    submitted_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class IdempotencyKey(models.Model):
    """
    Idempotency tracking for API requests.
    """

    key = models.CharField(max_length=128, unique=True)
    scope = models.CharField(max_length=64, default="wallet")
    request_hash = models.CharField(max_length=64, blank=True, default="")
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(blank=True, null=True, default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class LedgerEntry(models.Model):
    """
    Immutable ledger entry (double-entry primitive).
    """

    ENTRY_DEBIT = "debit"
    ENTRY_CREDIT = "credit"
    ENTRY_CHOICES = (
        (ENTRY_DEBIT, "Debit"),
        (ENTRY_CREDIT, "Credit"),
    )

    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="ledger_entries"
    )
    wallet = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name="ledger_entries"
    )
    entry_type = models.CharField(max_length=16, choices=ENTRY_CHOICES)
    amount = models.DecimalField(
        max_digits=64, decimal_places=wallet_settings.WALLET_MATH_SCALE
    )
    balance_before = models.DecimalField(
        max_digits=64, decimal_places=wallet_settings.WALLET_MATH_SCALE
    )
    balance_after = models.DecimalField(
        max_digits=64, decimal_places=wallet_settings.WALLET_MATH_SCALE
    )

    created_at = models.DateTimeField(auto_now_add=True)


class ApprovalRequest(models.Model):
    """
    Approval workflow for high-risk actions.
    """

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    )

    action = models.CharField(max_length=32)
    holder_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    holder_id = models.PositiveIntegerField()
    holder = GenericForeignKey("holder_type", "holder_id")

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    amount = models.DecimalField(
        max_digits=64, decimal_places=wallet_settings.WALLET_MATH_SCALE
    )
    meta = models.JSONField(blank=True, null=True, default=dict)

    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    reason = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_requests_created",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_requests_resolved",
    )
    second_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_requests_second_approved",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    second_approved_at = models.DateTimeField(null=True, blank=True)
    required_approvals = models.PositiveSmallIntegerField(default=2)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class WalletRole(models.Model):
    """
    Role-based limits and permissions for wallet holders.
    """

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")

    max_withdraw_amount = models.DecimalField(
        max_digits=64,
        decimal_places=wallet_settings.WALLET_MATH_SCALE,
        null=True,
        blank=True,
    )
    max_transfer_amount = models.DecimalField(
        max_digits=64,
        decimal_places=wallet_settings.WALLET_MATH_SCALE,
        null=True,
        blank=True,
    )
    min_balance_required = models.DecimalField(
        max_digits=64,
        decimal_places=wallet_settings.WALLET_MATH_SCALE,
        default=0,
    )
    daily_outflow_limit = models.DecimalField(
        max_digits=64,
        decimal_places=wallet_settings.WALLET_MATH_SCALE,
        null=True,
        blank=True,
    )
    monthly_outflow_limit = models.DecimalField(
        max_digits=64,
        decimal_places=wallet_settings.WALLET_MATH_SCALE,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class WalletRoleAssignment(models.Model):
    """
    Assign roles to any holder (User, Org, etc).
    """

    holder_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    holder_id = models.PositiveIntegerField()
    holder = GenericForeignKey("holder_type", "holder_id")

    role = models.ForeignKey(WalletRole, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("holder_type", "holder_id", "role"),)


class ComplianceProfile(models.Model):
    """
    Compliance & risk profile for a holder.
    """

    STATUS_PENDING = "pending"
    STATUS_VERIFIED = "verified"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_VERIFIED, "Verified"),
        (STATUS_REJECTED, "Rejected"),
    )

    holder_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    holder_id = models.PositiveIntegerField()
    holder = GenericForeignKey("holder_type", "holder_id")

    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    risk_score = models.PositiveSmallIntegerField(default=0)
    is_suspended = models.BooleanField(default=False)

    daily_limit = models.DecimalField(
        max_digits=64,
        decimal_places=wallet_settings.WALLET_MATH_SCALE,
        null=True,
        blank=True,
    )
    monthly_limit = models.DecimalField(
        max_digits=64,
        decimal_places=wallet_settings.WALLET_MATH_SCALE,
        null=True,
        blank=True,
    )

    flags = models.JSONField(blank=True, null=True, default=dict)
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SanctionedEntity(models.Model):
    """
    Simple sanctions/blocklist entry for holders.
    """

    holder_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    holder_id = models.PositiveIntegerField()
    holder = GenericForeignKey("holder_type", "holder_id")

    source = models.CharField(max_length=120, blank=True, default="manual")
    reason = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("holder_type", "holder_id", "source"),)


class TransactionReview(models.Model):
    """
    Compliance review record for a transaction.
    """

    STATUS_OPEN = "open"
    STATUS_CLEARED = "cleared"
    STATUS_ESCALATED = "escalated"

    STATUS_CHOICES = (
        (STATUS_OPEN, "Open"),
        (STATUS_CLEARED, "Cleared"),
        (STATUS_ESCALATED, "Escalated"),
    )

    transaction = models.ForeignKey(
        Transaction, on_delete=models.CASCADE, related_name="reviews"
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN
    )
    rule = models.CharField(max_length=64, blank=True, default="")
    reason = models.TextField(blank=True, default="")
    score = models.PositiveSmallIntegerField(default=0)

    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class HolderKey(models.Model):
    """
    Public keys registered for holders (user-signing).
    """

    SCHEME_SECP256K1 = "secp256k1"
    SCHEME_ED25519 = "ed25519"

    SCHEME_CHOICES = (
        (SCHEME_SECP256K1, "Secp256k1"),
        (SCHEME_ED25519, "Ed25519"),
    )

    holder_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    holder_id = models.PositiveIntegerField()
    holder = GenericForeignKey("holder_type", "holder_id")

    scheme = models.CharField(max_length=32, choices=SCHEME_CHOICES)
    public_key = models.CharField(max_length=256)
    key_id = models.CharField(max_length=128, unique=True)
    label = models.CharField(max_length=120, blank=True, default="")
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)


class SignatureNonce(models.Model):
    """
    Anti-replay nonce for user-signed requests.
    """

    holder_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    holder_id = models.PositiveIntegerField()
    holder = GenericForeignKey("holder_type", "holder_id")

    nonce = models.CharField(max_length=64, unique=True)
    used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class CashAgent(models.Model):
    """
    Cash-in / Cash-out agent.
    """

    holder_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    holder_id = models.PositiveIntegerField()
    holder = GenericForeignKey("holder_type", "holder_id")

    code = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    daily_limit = models.DecimalField(
        max_digits=64,
        decimal_places=wallet_settings.WALLET_MATH_SCALE,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)


class CashRequest(models.Model):
    """
    Cash-in / Cash-out request requiring approval.
    """

    TYPE_CASHIN = "cashin"
    TYPE_CASHOUT = "cashout"
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    TYPE_CHOICES = (
        (TYPE_CASHIN, "Cash In"),
        (TYPE_CASHOUT, "Cash Out"),
    )
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    )

    holder_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    holder_id = models.PositiveIntegerField()
    holder = GenericForeignKey("holder_type", "holder_id")

    agent = models.ForeignKey(CashAgent, on_delete=models.PROTECT)
    amount = models.DecimalField(
        max_digits=64, decimal_places=wallet_settings.WALLET_MATH_SCALE
    )
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    meta = models.JSONField(blank=True, null=True, default=dict)

    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TransferReceipt(models.Model):
    """
    Receipt for P2P transfers.
    """

    transfer = models.OneToOneField(Transfer, on_delete=models.CASCADE)
    reference = models.CharField(max_length=64, unique=True)
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)


class FundingSource(models.Model):
    """
    External funding source (bank/ABA placeholder).
    """

    TYPE_BANK = "bank"
    TYPE_ABA = "aba"
    TYPE_MOBILE = "mobile"

    TYPE_CHOICES = (
        (TYPE_BANK, "Bank"),
        (TYPE_ABA, "ABA"),
        (TYPE_MOBILE, "Mobile"),
    )

    holder_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    holder_id = models.PositiveIntegerField()
    holder = GenericForeignKey("holder_type", "holder_id")

    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    label = models.CharField(max_length=120)
    account_ref = models.CharField(max_length=128)
    meta = models.JSONField(blank=True, null=True, default=dict)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
