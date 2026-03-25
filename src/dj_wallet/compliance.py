from datetime import timedelta
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum
from django.utils import timezone

from .models import ComplianceProfile, Transaction, Wallet


class ComplianceService:
    """
    Compliance checks and limits for holders.
    """

    @staticmethod
    def get_profile(holder):
        ct = ContentType.objects.get_for_model(holder)
        profile, _ = ComplianceProfile.objects.get_or_create(
            holder_type=ct, holder_id=holder.pk
        )
        return profile

    @staticmethod
    def sum_outflow(holder, since):
        ct = ContentType.objects.get_for_model(holder)
        wallets = Wallet.objects.filter(holder_type=ct, holder_id=holder.pk)
        total = (
            Transaction.objects.filter(
                wallet__in=wallets,
                type=Transaction.TYPE_WITHDRAW,
                confirmed=True,
                created_at__gte=since,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        return total

    @classmethod
    def daily_outflow(cls, holder):
        since = timezone.now() - timedelta(days=1)
        return cls.sum_outflow(holder, since)

    @classmethod
    def monthly_outflow(cls, holder):
        since = timezone.now() - timedelta(days=30)
        return cls.sum_outflow(holder, since)
