from django.core.management.base import BaseCommand

from dj_wallet.anchor import AnchorService
from dj_wallet.models import ChainAnchor, Transaction


class Command(BaseCommand):
    help = "Verify on-chain anchor for a transaction UUID."

    def add_arguments(self, parser):
        parser.add_argument("uuid")

    def handle(self, *args, **options):
        txn = Transaction.objects.filter(uuid=options["uuid"]).first()
        if not txn:
            self.stdout.write("not_found")
            return
        anchor = ChainAnchor.objects.filter(transaction=txn).first()
        if not anchor:
            self.stdout.write("no_anchor")
            return
        ok = AnchorService.confirm(anchor)
        status = anchor.status
        self.stdout.write(f"{status}")
