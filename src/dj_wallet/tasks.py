from celery import shared_task

from dj_wallet.anchor import AnchorService
from dj_wallet.models import ChainAnchor


@shared_task
def submit_pending_anchors(limit=100):
    AnchorService.process_pending(limit=limit)


@shared_task
def confirm_submitted_anchors(limit=100):
    anchors = ChainAnchor.objects.filter(status=ChainAnchor.STATUS_SUBMITTED)[
        :limit
    ]
    for anchor in anchors:
        AnchorService.confirm(anchor)
