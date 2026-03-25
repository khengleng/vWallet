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

    @classmethod
    def suspend(cls, holder, reason=""):
        profile = cls.get_profile(holder)
        profile.is_suspended = True
        if reason:
            profile.notes = (profile.notes + "\n" if profile.notes else "") + reason
        profile.save(update_fields=["is_suspended", "notes", "updated_at"])
        return profile

    @classmethod
    def unsuspend(cls, holder, reason=""):
        profile = cls.get_profile(holder)
        profile.is_suspended = False
        if reason:
            profile.notes = (profile.notes + "\n" if profile.notes else "") + reason
        profile.save(update_fields=["is_suspended", "notes", "updated_at"])
        return profile

    @classmethod
    def set_status(cls, holder, status, note=""):
        profile = cls.get_profile(holder)
        profile.status = status
        if note:
            profile.notes = (profile.notes + "\n" if profile.notes else "") + note
        profile.save(update_fields=["status", "notes", "updated_at"])
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
