from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from dj_wallet.models import WalletRole, WalletRoleAssignment


class Command(BaseCommand):
    help = "Backfill existing users into customer role and Customer group."

    def handle(self, *args, **options):
        User = get_user_model()
        role, _ = WalletRole.objects.get_or_create(
            slug="customer", defaults={"name": "Customer"}
        )
        group, _ = Group.objects.get_or_create(name="Customer")

        count = 0
        for user in User.objects.all():
            ct = ContentType.objects.get_for_model(user)
            WalletRoleAssignment.objects.get_or_create(
                holder_type=ct, holder_id=user.pk, role=role
            )
            user.groups.add(group)
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Backfilled {count} users."))
