import csv
import sys

from django.core.management.base import BaseCommand

from dj_wallet.models import TransactionReview


class Command(BaseCommand):
    help = "Export compliance reviews to CSV (stdout)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--status",
            default="open,escalated",
            help="Comma-separated statuses to export (default: open,escalated)",
        )

    def handle(self, *args, **options):
        statuses = [s.strip() for s in options["status"].split(",") if s.strip()]
        qs = TransactionReview.objects.filter(status__in=statuses).select_related(
            "transaction"
        )

        writer = csv.writer(sys.stdout)
        writer.writerow(
            [
                "review_id",
                "status",
                "rule",
                "reason",
                "score",
                "transaction_id",
                "transaction_uuid",
                "amount",
                "created_at",
            ]
        )
        for review in qs:
            txn = review.transaction
            writer.writerow(
                [
                    review.id,
                    review.status,
                    review.rule,
                    review.reason,
                    review.score,
                    txn.id,
                    txn.uuid,
                    txn.amount,
                    review.created_at,
                ]
            )
