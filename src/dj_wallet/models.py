from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from .abstract_models import AbstractTransaction, AbstractTransfer, AbstractWallet
from .conf import wallet_settings


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
