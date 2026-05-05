from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0005_create_assetdetail_if_missing"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE app_landrecord712 ADD COLUMN IF NOT EXISTS hissa_number VARCHAR(50) NULL;",
            reverse_sql="ALTER TABLE app_landrecord712 DROP COLUMN IF EXISTS hissa_number;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE app_landrecord712 ADD COLUMN IF NOT EXISTS jirayit VARCHAR(50) NULL;",
            reverse_sql="ALTER TABLE app_landrecord712 DROP COLUMN IF EXISTS jirayit;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE app_landrecord712 ADD COLUMN IF NOT EXISTS bagayat VARCHAR(50) NULL;",
            reverse_sql="ALTER TABLE app_landrecord712 DROP COLUMN IF EXISTS bagayat;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE app_landrecord712 ADD COLUMN IF NOT EXISTS potkharaba VARCHAR(50) NULL;",
            reverse_sql="ALTER TABLE app_landrecord712 DROP COLUMN IF EXISTS potkharaba;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE app_landrecord712 ADD COLUMN IF NOT EXISTS total_area VARCHAR(50) NULL;",
            reverse_sql="ALTER TABLE app_landrecord712 DROP COLUMN IF EXISTS total_area;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE app_landrecord712 ADD COLUMN IF NOT EXISTS aakarni VARCHAR(50) NULL;",
            reverse_sql="ALTER TABLE app_landrecord712 DROP COLUMN IF EXISTS aakarni;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE app_landrecord712 ADD COLUMN IF NOT EXISTS khata_number VARCHAR(50) NULL;",
            reverse_sql="ALTER TABLE app_landrecord712 DROP COLUMN IF EXISTS khata_number;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE app_landrecord712 ADD COLUMN IF NOT EXISTS khata_area VARCHAR(50) NULL;",
            reverse_sql="ALTER TABLE app_landrecord712 DROP COLUMN IF EXISTS khata_area;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE app_landrecord712 ADD COLUMN IF NOT EXISTS aakar VARCHAR(50) NULL;",
            reverse_sql="ALTER TABLE app_landrecord712 DROP COLUMN IF EXISTS aakar;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE app_landrecord712 ADD COLUMN IF NOT EXISTS holder_name TEXT NULL;",
            reverse_sql="ALTER TABLE app_landrecord712 DROP COLUMN IF EXISTS holder_name;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE app_landrecord712 ADD COLUMN IF NOT EXISTS kul_khand_other_rights TEXT NULL;",
            reverse_sql="ALTER TABLE app_landrecord712 DROP COLUMN IF EXISTS kul_khand_other_rights;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE app_landrecord712 ADD COLUMN IF NOT EXISTS area_more_than_20guntha VARCHAR(10) NULL;",
            reverse_sql="ALTER TABLE app_landrecord712 DROP COLUMN IF EXISTS area_more_than_20guntha;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE app_landrecord712 ADD COLUMN IF NOT EXISTS bagayat_more_than_10guntha VARCHAR(10) NULL;",
            reverse_sql="ALTER TABLE app_landrecord712 DROP COLUMN IF EXISTS bagayat_more_than_10guntha;",
        ),
    ]
