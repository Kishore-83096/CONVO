# Generated for the Myna message-insert index A/B benchmark.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("chat_messages", "0010_send_hot_path_indexes"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="message",
            name="msg_room_created_idx",
        ),
        migrations.RemoveIndex(
            model_name="message",
            name="msg_sender_created_idx",
        ),
        migrations.RemoveIndex(
            model_name="message",
            name="msg_room_type_time_idx",
        ),
    ]
