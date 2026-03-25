from datetime import timedelta
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.utils import timezone

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

        # Simple velocity check: too many withdrawals in the last hour
        ct = ContentType.objects.get_for_model(holder)
        wallets = Wallet.objects.filter(holder_type=ct, holder_id=holder.pk)
        since = timezone.now() - timedelta(hours=1)
        recent_withdrawals = (
            Transaction.objects.filter(
                wallet__in=wallets,
                type=Transaction.TYPE_WITHDRAW,
                created_at__gte=since,
            ).aggregate(count=Count("id"))["count"]
            or 0
        )

        if action in {"withdraw", "transfer", "purchase"} and recent_withdrawals > 20:
            return False, "velocity_limit_exceeded"

        # Very large single transfer heuristic (override with real rules)
        if amount > Decimal("1000000"):
            return False, "amount_too_large"

        return True, ""
