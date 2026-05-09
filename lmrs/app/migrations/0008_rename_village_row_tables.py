from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0007_merge_20260508_1543'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE app_villagedata15_2row RENAME TO app_villagedata32_2row;
                ALTER TABLE app_villagedata15_2rowfile RENAME TO app_villagedata32_2rowfile;
                ALTER TABLE app_villagedata18_1row RENAME TO app_villagedata32_1row;
                ALTER TABLE app_villagedata18_1rowfile RENAME TO app_villagedata32_1rowfile;
            """,
            reverse_sql="""
                ALTER TABLE app_villagedata32_2row RENAME TO app_villagedata15_2row;
                ALTER TABLE app_villagedata32_2rowfile RENAME TO app_villagedata15_2rowfile;
                ALTER TABLE app_villagedata32_1row RENAME TO app_villagedata18_1row;
                ALTER TABLE app_villagedata32_1rowfile RENAME TO app_villagedata18_1rowfile;
            """,
        ),
    ]
