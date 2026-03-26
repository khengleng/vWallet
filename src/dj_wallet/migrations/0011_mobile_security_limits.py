from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dj_wallet", "0010_mobile_security"),
    ]

    operations = [
        migrations.AddField(
            model_name="mobilesecurityprofile",
            name="pin_failed_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="mobilesecurityprofile",
            name="pin_locked_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="mfachallenge",
            name="failed_attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="mfachallenge",
            name="locked_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
