from django.contrib.contenttypes.models import ContentType

from .models import FundingSource


class FundingService:
    """
    Placeholder hooks for bank/ABA integrations.
    """

    @staticmethod
    def create_source(holder, type, label, account_ref, meta=None):
        return FundingSource.objects.create(
            holder_type=ContentType.objects.get_for_model(holder),
            holder_id=holder.pk,
            type=type,
            label=label,
            account_ref=account_ref,
            meta=meta or {},
        )

    @staticmethod
    def list_sources(holder):
        ct = ContentType.objects.get_for_model(holder)
        return FundingSource.objects.filter(holder_type=ct, holder_id=holder.pk, is_active=True)

    @staticmethod
    def deactivate(source):
        source.is_active = False
        source.save(update_fields=["is_active"])
        return source
