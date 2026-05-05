from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE app_landrecord712 ADD COLUMN IF NOT EXISTS puid_ulip_no VARCHAR(100) NULL;",
            reverse_sql="ALTER TABLE app_landrecord712 DROP COLUMN IF EXISTS puid_ulip_no;",
        ),
    ]
