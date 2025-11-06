# Generated manually for community features and chat fixes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("recom_sys_app", "0004_groupchatmessage"),
    ]

    operations = [
        # Add community group fields to GroupSession
        migrations.AddField(
            model_name="groupsession",
            name="is_public",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="groupsession",
            name="genre_filter",
            field=models.CharField(blank=True, db_index=True, max_length=50, null=True),
        ),
        # Add system message field to GroupChatMessage
        migrations.AddField(
            model_name="groupchatmessage",
            name="is_system_message",
            field=models.BooleanField(default=False),
        ),
    ]
