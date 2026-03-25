# dj_wallet/admin.py
from django.contrib import admin

from .models import (
    ChainAnchor,
    ComplianceProfile,
    Transaction,
    TransactionSignature,
    Transfer,
    Wallet,
    WalletRole,
    WalletRoleAssignment,
)


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
