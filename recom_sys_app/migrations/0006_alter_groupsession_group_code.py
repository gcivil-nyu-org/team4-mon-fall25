# Generated manually to fix group_code max_length for tests

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("recom_sys_app", "0005_groupsession_community_fields_groupchatmessage_system"),
    ]

    operations = [
        migrations.AlterField(
            model_name="groupsession",
            name="group_code",
            field=models.CharField(db_index=True, max_length=16, unique=True),
        ),
    ]
