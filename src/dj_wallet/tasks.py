from celery import shared_task

from dj_wallet.anchor import AnchorService
from dj_wallet.conf import wallet_settings
from dj_wallet.models import ChainAnchor


@shared_task
def submit_pending_anchors(limit=None):
    batch = limit if limit is not None else wallet_settings.ANCHOR_BATCH_SIZE
    AnchorService.process_pending(limit=batch)


@shared_task
def confirm_submitted_anchors(limit=None):
    batch = limit if limit is not None else wallet_settings.ANCHOR_BATCH_SIZE
    anchors = ChainAnchor.objects.filter(status=ChainAnchor.STATUS_SUBMITTED)[:batch]
    for anchor in anchors:
        AnchorService.confirm(anchor)
