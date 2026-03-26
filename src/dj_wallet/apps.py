"""
Django app configuration for dj_wallet.
"""

from django.apps import AppConfig


class DjangoWalletsConfig(AppConfig):
    """Configuration for the 2M Wallets application."""

    name = "dj_wallet"
    verbose_name = "2M Wallets"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        """Import signals when the app is ready."""
        # Import signals to register them
        from . import signals  # noqa: F401

        # Attach WalletMixin helpers to the User model if not already present.
        # This keeps the default auth.User usable without a custom model.
        from django.contrib.auth import get_user_model

        from .mixins import WalletMixin

        User = get_user_model()
        mixin_attrs = [
            "balance",
            "wallet",
            "get_wallet",
            "create_wallet",
            "has_wallet",
            "deposit",
            "withdraw",
            "force_withdraw",
            "transfer",
            "safe_transfer",
            "pay",
            "freeze_wallet",
            "unfreeze_wallet",
            "is_wallet_frozen",
            "get_pending_transactions",
        ]

        for name in mixin_attrs:
            if not hasattr(User, name):
                setattr(User, name, getattr(WalletMixin, name))
