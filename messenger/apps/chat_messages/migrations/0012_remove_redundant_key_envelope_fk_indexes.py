# Generated for the Myna key-envelope insert index A/B benchmark.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat_messages", "0011_remove_unused_message_indexes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="messagekeyenvelope",
            name="message",
            field=models.ForeignKey(
                db_index=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="key_envelopes",
                to="chat_messages.message",
            ),
        ),
        migrations.AlterField(
            model_name="messagekeyenvelope",
            name="recipient_device",
            field=models.ForeignKey(
                db_index=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="message_key_envelopes",
                to="e2ee_devices.device",
            ),
        ),
    ]
