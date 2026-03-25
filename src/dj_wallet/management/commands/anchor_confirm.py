from django.core.management.base import BaseCommand

from dj_wallet.anchor import AnchorService
from dj_wallet.models import ChainAnchor


class Command(BaseCommand):
    help = "Confirm submitted anchors on the configured chain"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        anchors = ChainAnchor.objects.filter(
            status=ChainAnchor.STATUS_SUBMITTED
        )[: options["limit"]]
        for anchor in anchors:
            AnchorService.confirm(anchor)
        self.stdout.write(self.style.SUCCESS("Processed submitted anchors"))
