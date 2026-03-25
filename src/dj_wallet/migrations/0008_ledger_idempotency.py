from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("dj_wallet", "0007_compliance_reviews"),
    ]

    operations = [
        migrations.CreateModel(
            name="IdempotencyKey",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=128, unique=True)),
                ("scope", models.CharField(default="wallet", max_length=64)),
                ("request_hash", models.CharField(blank=True, default="", max_length=64)),
                ("response_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("response_body", models.JSONField(blank=True, default=dict, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="LedgerEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entry_type", models.CharField(choices=[("debit", "Debit"), ("credit", "Credit")], max_length=16)),
                ("amount", models.DecimalField(decimal_places=8, max_digits=64)),
                ("balance_before", models.DecimalField(decimal_places=8, max_digits=64)),
                ("balance_after", models.DecimalField(decimal_places=8, max_digits=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("transaction", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ledger_entries", to="dj_wallet.transaction")),
                ("wallet", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ledger_entries", to="dj_wallet.wallet")),
            ],
        ),
    ]
