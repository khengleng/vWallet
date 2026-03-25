from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from dj_wallet.models import WalletRole, WalletRoleAssignment


class Command(BaseCommand):
    help = "Seed default roles and assign to existing users"

    def handle(self, *args, **options):
        roles = [
            ("ops", "Operations"),
            ("agent", "Cash Agent"),
            ("customer", "Customer"),
        ]

        role_map = {}
        for slug, name in roles:
            role, _ = WalletRole.objects.get_or_create(slug=slug, defaults={"name": name})
            role_map[slug] = role

        User = get_user_model()
        for user in User.objects.all():
            ct = ContentType.objects.get_for_model(user)
            if user.is_superuser:
                WalletRoleAssignment.objects.get_or_create(
                    holder_type=ct, holder_id=user.pk, role=role_map["ops"]
                )
            else:
                WalletRoleAssignment.objects.get_or_create(
                    holder_type=ct, holder_id=user.pk, role=role_map["customer"]
                )

        self.stdout.write(self.style.SUCCESS("Seeded roles and assignments"))
