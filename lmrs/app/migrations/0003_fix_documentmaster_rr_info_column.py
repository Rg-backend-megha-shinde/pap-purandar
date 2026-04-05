from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0002_treedetail_valuation"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'app_documentmaster'
                      AND column_name = 'rr_rate_id'
                ) AND NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'app_documentmaster'
                      AND column_name = 'rr_info_id'
                ) THEN
                    ALTER TABLE app_documentmaster
                    RENAME COLUMN rr_rate_id TO rr_info_id;
                END IF;
            END
            $$;
            """,
            reverse_sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'app_documentmaster'
                      AND column_name = 'rr_info_id'
                ) AND NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'app_documentmaster'
                      AND column_name = 'rr_rate_id'
                ) THEN
                    ALTER TABLE app_documentmaster
                    RENAME COLUMN rr_info_id TO rr_rate_id;
                END IF;
            END
            $$;
            """,
        ),
    ]
