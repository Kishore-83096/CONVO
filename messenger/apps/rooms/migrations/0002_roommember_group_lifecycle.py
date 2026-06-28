# Generated for Myna Messenger Phase 3 group membership lifecycle

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rooms", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="roommember",
            name="removed_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="roommember",
            name="banned_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="roommember",
            name="removed_by_user_id",
            field=models.CharField(
                blank=True,
                max_length=128,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="roommember",
            name="membership_version",
            field=models.PositiveIntegerField(
                default=1,
            ),
        ),
    ]