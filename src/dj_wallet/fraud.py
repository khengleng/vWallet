from datetime import timedelta
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.utils import timezone

from .conf import wallet_settings
from .models import Transaction, Wallet


class FraudService:
    """
    Basic fraud heuristics. Override in production.
    """

    @staticmethod
    def evaluate(holder, action, amount, meta=None):
        """
        Returns (allowed: bool, reason: str).
        """
        meta = meta or {}
        amount = Decimal(str(amount))

        # Blocked IPs
        ip = meta.get("ip", "")
        if ip and ip in wallet_settings.FRAUD_BLOCKED_IPS:
            return False, "blocked_ip"

        # Device binding for sensitive actions
        if wallet_settings.FRAUD_REQUIRE_DEVICE_ID and action in {
            "withdraw",
            "transfer",
            "purchase",
        }:
            if not meta.get("device_id"):
                return False, "device_required"

        # Velocity checks
        ct = ContentType.objects.get_for_model(holder)
        wallets = Wallet.objects.filter(holder_type=ct, holder_id=holder.pk)
        since = timezone.now() - timedelta(minutes=wallet_settings.FRAUD_VELOCITY_WINDOW_MIN)

        recent_withdrawals = (
            Transaction.objects.filter(
                wallet__in=wallets,
                type=Transaction.TYPE_WITHDRAW,
                created_at__gte=since,
            ).aggregate(count=Count("id"))["count"]
            or 0
        )
        if action == "withdraw" and recent_withdrawals > wallet_settings.FRAUD_WITHDRAW_COUNT:
            return False, "withdraw_velocity_exceeded"

        recent_transfers = (
            Transaction.objects.filter(
                wallet__in=wallets,
                type=Transaction.TYPE_WITHDRAW,
                created_at__gte=since,
                meta__action="transfer_send",
            ).aggregate(count=Count("id"))["count"]
            or 0
        )
        if action == "transfer" and recent_transfers > wallet_settings.FRAUD_TRANSFER_COUNT:
            return False, "transfer_velocity_exceeded"

        # Very large single transfer heuristic (override with real rules)
        if amount > Decimal("1000000"):
            return False, "amount_too_large"

        return True, ""
