from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("dj_wallet", "0006_funding_sources"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SanctionedEntity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("holder_id", models.PositiveIntegerField()),
                ("source", models.CharField(blank=True, default="manual", max_length=120)),
                ("reason", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("holder_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="contenttypes.contenttype")),
            ],
            options={
                "unique_together": {("holder_type", "holder_id", "source")},
            },
        ),
        migrations.CreateModel(
            name="TransactionReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("open", "Open"), ("cleared", "Cleared"), ("escalated", "Escalated")], default="open", max_length=16)),
                ("rule", models.CharField(blank=True, default="", max_length=64)),
                ("reason", models.TextField(blank=True, default="")),
                ("score", models.PositiveSmallIntegerField(default=0)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("transaction", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="dj_wallet.transaction")),
            ],
        ),
    ]
