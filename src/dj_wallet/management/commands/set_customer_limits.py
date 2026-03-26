from django.core.management.base import BaseCommand

from dj_wallet.models import WalletRole


class Command(BaseCommand):
    help = "Set default limits for the customer role."

    def handle(self, *args, **options):
        role, _ = WalletRole.objects.get_or_create(
            slug="customer", defaults={"name": "Customer"}
        )
        role.description = "Default customer limits"
        role.max_withdraw_amount = "500"
        role.max_transfer_amount = "500"
        role.daily_outflow_limit = "1000"
        role.monthly_outflow_limit = "5000"
        role.min_balance_required = "0"
        role.save()
        self.stdout.write(self.style.SUCCESS("Customer limits updated."))
