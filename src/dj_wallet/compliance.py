from datetime import timedelta
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum
from django.utils import timezone

from .conf import wallet_settings
from .models import ComplianceProfile, SanctionedEntity, Transaction, TransactionReview, Wallet


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
    def check_sanctions(holder):
        ct = ContentType.objects.get_for_model(holder)
        blocked = SanctionedEntity.objects.filter(
            holder_type=ct, holder_id=holder.pk, is_active=True
        ).exists()
        return not blocked

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

    @classmethod
    def _velocity_count(cls, holder):
        window = wallet_settings.COMPLIANCE_VELOCITY_WINDOW_MIN
        since = timezone.now() - timedelta(minutes=window)
        ct = ContentType.objects.get_for_model(holder)
        wallets = Wallet.objects.filter(holder_type=ct, holder_id=holder.pk)
        return Transaction.objects.filter(
            wallet__in=wallets, confirmed=True, created_at__gte=since
        ).count()

    @classmethod
    def evaluate_transaction(cls, txn):
        """
        Create compliance review records for notable activity.
        """
        holder = txn.payable
        if holder is None:
            return None

        reviews = []
        amount = Decimal(str(txn.amount))

        # Large transaction threshold
        if (
            wallet_settings.COMPLIANCE_ALERT_AMOUNT is not None
            and amount >= wallet_settings.COMPLIANCE_ALERT_AMOUNT
        ):
            reviews.append(
                TransactionReview(
                    transaction=txn,
                    rule="amount_threshold",
                    reason="amount_exceeds_threshold",
                    score=50,
                )
            )

        # Velocity threshold
        if (
            wallet_settings.COMPLIANCE_VELOCITY_COUNT is not None
            and cls._velocity_count(holder) >= wallet_settings.COMPLIANCE_VELOCITY_COUNT
        ):
            reviews.append(
                TransactionReview(
                    transaction=txn,
                    rule="velocity_threshold",
                    reason="velocity_exceeds_threshold",
                    score=40,
                )
            )

        if reviews:
            TransactionReview.objects.bulk_create(reviews)
        return reviews
