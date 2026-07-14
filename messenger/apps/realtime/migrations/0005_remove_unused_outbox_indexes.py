from django.db import migrations


EVENT_KEY_PATTERN_INDEX = (
    "realtime_outbox_events_event_key_bea203cd_like"
)


class Migration(migrations.Migration):
    dependencies = [
        ("realtime", "0004_outbox_claiming_and_event_key"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="realtimeoutboxevent",
            name="rt_outbox_status_next_idx",
        ),
        migrations.RemoveIndex(
            model_name="realtimeoutboxevent",
            name="rt_outbox_type_created_idx",
        ),
        migrations.RemoveIndex(
            model_name="realtimeoutboxevent",
            name="rt_outbox_group_created_idx",
        ),
        migrations.RunSQL(
            sql=(
                f'DROP INDEX IF EXISTS "{EVENT_KEY_PATTERN_INDEX}"'
            ),
            reverse_sql=(
                f'CREATE INDEX "{EVENT_KEY_PATTERN_INDEX}" '
                'ON "realtime_outbox_events" '
                '("event_key" varchar_pattern_ops)'
            ),
        ),
    ]
