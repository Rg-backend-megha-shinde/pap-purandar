from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0002_add_missing_landrecord712_columns"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE app_inspection ADD COLUMN IF NOT EXISTS inspection_asset_type VARCHAR(100) NULL;",
            reverse_sql="ALTER TABLE app_inspection DROP COLUMN IF EXISTS inspection_asset_type;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE app_inspection ADD COLUMN IF NOT EXISTS latitude NUMERIC(9,6) NULL;",
            reverse_sql="ALTER TABLE app_inspection DROP COLUMN IF EXISTS latitude;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE app_inspection ADD COLUMN IF NOT EXISTS longitude NUMERIC(9,6) NULL;",
            reverse_sql="ALTER TABLE app_inspection DROP COLUMN IF EXISTS longitude;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE app_inspection ADD COLUMN IF NOT EXISTS remark TEXT NULL;",
            reverse_sql="ALTER TABLE app_inspection DROP COLUMN IF EXISTS remark;",
        ),
    ]
