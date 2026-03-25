import json

from django.core.management.base import BaseCommand

from dj_wallet.audit import AuditService
from dj_wallet.models import Transaction


class Command(BaseCommand):
    help = "Verify audit hash for a transaction UUID."

    def add_arguments(self, parser):
        parser.add_argument("uuid")

    def handle(self, *args, **options):
        txn = Transaction.objects.filter(uuid=options["uuid"]).first()
        if not txn:
            self.stdout.write("not_found")
            return
        payload = AuditService._payload(txn)
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        import hashlib

        expected = hashlib.sha256(data).hexdigest()
        actual = (txn.meta or {}).get("audit_hash")
        if expected == actual:
            self.stdout.write("ok")
        else:
            self.stdout.write("mismatch")
