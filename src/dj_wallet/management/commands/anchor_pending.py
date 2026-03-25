from django.core.management.base import BaseCommand

from dj_wallet.anchor import AnchorService


class Command(BaseCommand):
    help = "Submit pending wallet transaction anchors to the configured chain"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        AnchorService.process_pending(limit=options["limit"])
        self.stdout.write(self.style.SUCCESS("Processed pending anchors"))
