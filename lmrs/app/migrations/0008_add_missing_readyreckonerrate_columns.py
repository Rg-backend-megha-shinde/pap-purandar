from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0007_documentmaster_land_record"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE app_readyreckonerrate ADD COLUMN IF NOT EXISTS shighrasiddha_vibhag TEXT NULL;",
            reverse_sql="ALTER TABLE app_readyreckonerrate DROP COLUMN IF EXISTS shighrasiddha_vibhag;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE app_readyreckonerrate ADD COLUMN IF NOT EXISTS village_type VARCHAR(20) NULL;",
            reverse_sql="ALTER TABLE app_readyreckonerrate DROP COLUMN IF EXISTS village_type;",
        ),
    ]
