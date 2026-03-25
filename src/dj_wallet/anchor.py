from django.conf import settings
from django.utils import timezone

from .conf import wallet_settings
from .models import ChainAnchor


class ChainAdapter:
    """
    Base on-chain adapter. Override with actual chain integration.
    """

    def submit_hash(self, tx_hash):
        raise NotImplementedError

    def check_confirmation(self, onchain_tx_hash):
        return False


class NoopChainAdapter(ChainAdapter):
    """
    Dev adapter that marks submissions as confirmed immediately.
    """

    def submit_hash(self, tx_hash):
        return f"noop-{tx_hash[:16]}"

    def check_confirmation(self, onchain_tx_hash):
        return True


class AnchorService:
    @staticmethod
    def _adapter():
        adapter = getattr(settings, "DJ_WALLET_CHAIN_ADAPTER", None)
        if adapter is None:
            return NoopChainAdapter()
        return adapter()

    @staticmethod
    def _chain_name():
        return getattr(settings, "DJ_WALLET_CHAIN_NAME", wallet_settings.ANCHOR_CHAIN_NAME)

    @classmethod
    def ensure_anchor(cls, txn):
        anchor, _ = ChainAnchor.objects.get_or_create(
            transaction=txn, defaults={"chain": cls._chain_name()}
        )
        return anchor

    @classmethod
    def submit(cls, txn):
        anchor = cls.ensure_anchor(txn)
        if anchor.status in {ChainAnchor.STATUS_SUBMITTED, ChainAnchor.STATUS_CONFIRMED}:
            return anchor

        adapter = cls._adapter()
        onchain_tx_hash = adapter.submit_hash(txn.tx_hash)

        anchor.status = ChainAnchor.STATUS_SUBMITTED
        anchor.onchain_tx_hash = onchain_tx_hash
        anchor.submitted_at = timezone.now()
        anchor.attempts += 1
        anchor.save(
            update_fields=[
                "status",
                "onchain_tx_hash",
                "submitted_at",
                "attempts",
                "updated_at",
            ]
        )
        return anchor

    @classmethod
    def confirm(cls, anchor):
        adapter = cls._adapter()
        if adapter.check_confirmation(anchor.onchain_tx_hash):
            anchor.status = ChainAnchor.STATUS_CONFIRMED
            anchor.confirmed_at = timezone.now()
            anchor.save(update_fields=["status", "confirmed_at", "updated_at"])
        return anchor

    @classmethod
    def process_pending(cls, limit=100):
        anchors = ChainAnchor.objects.filter(
            status=ChainAnchor.STATUS_PENDING
        ).select_related("transaction")[:limit]
        for anchor in anchors:
            cls.submit(anchor.transaction)
