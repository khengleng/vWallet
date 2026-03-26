# dj_wallet/admin.py
from django.contrib import admin

from .models import (
    ChainAnchor,
    ComplianceProfile,
    SanctionedEntity,
    TransactionReview,
    HolderKey,
    SignatureNonce,
    CashAgent,
    CashRequest,
    TransferReceipt,
    FundingSource,
    LedgerEntry,
    IdempotencyKey,
    ApprovalRequest,
    Transaction,
    TransactionSignature,
    Transfer,
    Wallet,
    WalletRole,
    WalletRoleAssignment,
    MobileSecurityProfile,
    MfaChallenge,
)

admin.site.site_header = "2M Platform Administration"
admin.site.site_title = "2M Platform Administration"
admin.site.index_title = "2M Platform Administration"


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("slug", "holder", "balance", "created_at")
    search_fields = ("slug", "uuid")
    readonly_fields = (
        "balance",
        "uuid",
    )  # Balance should not be edited manually to preserve audit trail

    # Helper to show holder in list regardless of type
    def holder(self, obj):
        return f"{obj.holder_type} - {obj.holder_id}"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("uuid", "wallet", "type", "amount", "confirmed", "created_at")
    list_filter = ("type", "confirmed", "created_at")
    search_fields = ("uuid", "wallet__slug")


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ("uuid", "from_object", "to_object", "status", "created_at")


@admin.register(TransactionSignature)
class TransactionSignatureAdmin(admin.ModelAdmin):
    list_display = ("transaction", "scheme", "key_id", "created_at")
    search_fields = ("transaction__uuid", "key_id")


@admin.register(ChainAnchor)
class ChainAnchorAdmin(admin.ModelAdmin):
    list_display = ("transaction", "chain", "status", "submitted_at", "confirmed_at")
    search_fields = ("transaction__uuid", "onchain_tx_hash")
    list_filter = ("chain", "status")


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("transaction", "wallet", "entry_type", "amount", "created_at")
    list_filter = ("entry_type",)
    search_fields = ("transaction__uuid", "wallet__uuid")


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ("key", "scope", "response_status", "created_at")
    search_fields = ("key",)


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = (
        "action",
        "holder_type",
        "holder_id",
        "amount",
        "status",
        "created_at",
        "resolved_by",
        "second_approved_by",
    )
    list_filter = ("action", "status")
    search_fields = ("holder_id",)


@admin.register(WalletRole)
class WalletRoleAdmin(admin.ModelAdmin):
    list_display = ("slug", "name")
    search_fields = ("slug", "name")


@admin.register(WalletRoleAssignment)
class WalletRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("role", "holder_type", "holder_id", "created_at")
    list_filter = ("role",)


@admin.register(ComplianceProfile)
class ComplianceProfileAdmin(admin.ModelAdmin):
    list_display = ("holder_type", "holder_id", "status", "risk_score", "is_suspended")
    list_filter = ("status", "is_suspended")


@admin.register(SanctionedEntity)
class SanctionedEntityAdmin(admin.ModelAdmin):
    list_display = ("holder_type", "holder_id", "source", "is_active", "created_at")
    list_filter = ("source", "is_active")
    search_fields = ("holder_id",)


@admin.register(TransactionReview)
class TransactionReviewAdmin(admin.ModelAdmin):
    list_display = ("transaction", "status", "rule", "score", "created_at")
    list_filter = ("status", "rule")
    search_fields = ("transaction__uuid", "rule")


@admin.register(HolderKey)
class HolderKeyAdmin(admin.ModelAdmin):
    list_display = ("key_id", "holder_type", "holder_id", "scheme", "is_active")
    search_fields = ("key_id", "public_key")


@admin.register(MobileSecurityProfile)
class MobileSecurityProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "pin_set_at", "created_at")
    search_fields = ("user__username", "user__email")


@admin.register(MfaChallenge)
class MfaChallengeAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "amount", "expires_at", "verified_at")
    search_fields = ("user__username", "action")
    list_filter = ("action",)


@admin.register(SignatureNonce)
class SignatureNonceAdmin(admin.ModelAdmin):
    list_display = ("nonce", "holder_type", "holder_id", "used_at", "expires_at")
    search_fields = ("nonce",)


@admin.register(CashAgent)
class CashAgentAdmin(admin.ModelAdmin):
    list_display = ("code", "holder_type", "holder_id", "is_active")
    search_fields = ("code",)
    list_filter = ("is_active",)


@admin.register(CashRequest)
class CashRequestAdmin(admin.ModelAdmin):
    list_display = ("type", "status", "amount", "agent", "holder_type", "holder_id")
    list_filter = ("type", "status")


@admin.register(TransferReceipt)
class TransferReceiptAdmin(admin.ModelAdmin):
    list_display = ("reference", "transfer", "created_at")
    search_fields = ("reference",)


@admin.register(FundingSource)
class FundingSourceAdmin(admin.ModelAdmin):
    list_display = ("type", "label", "holder_type", "holder_id", "is_active")
    list_filter = ("type", "is_active")
    search_fields = ("label", "account_ref")
