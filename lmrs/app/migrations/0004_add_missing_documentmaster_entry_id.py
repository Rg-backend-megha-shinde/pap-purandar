from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0003_add_missing_inspection_columns"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE app_documentmaster ADD COLUMN IF NOT EXISTS entry_id BIGINT NULL;",
            reverse_sql="ALTER TABLE app_documentmaster DROP COLUMN IF EXISTS entry_id;",
        ),
    ]
