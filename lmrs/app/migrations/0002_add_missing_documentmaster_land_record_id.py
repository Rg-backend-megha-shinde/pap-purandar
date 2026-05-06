from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'purandar_airport'
                      AND table_name = 'app_documentmaster'
                ) THEN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'purandar_airport'
                          AND table_name = 'app_documentmaster'
                          AND column_name = 'land_record_id'
                    ) THEN
                        ALTER TABLE purandar_airport.app_documentmaster
                        ADD COLUMN land_record_id bigint NULL;
                    END IF;
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'pune_ring_road'
                      AND table_name = 'app_documentmaster'
                ) THEN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'pune_ring_road'
                          AND table_name = 'app_documentmaster'
                          AND column_name = 'land_record_id'
                    ) THEN
                        ALTER TABLE pune_ring_road.app_documentmaster
                        ADD COLUMN land_record_id bigint NULL;
                    END IF;
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'purandar_airport_new'
                      AND table_name = 'app_documentmaster'
                ) THEN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'purandar_airport_new'
                          AND table_name = 'app_documentmaster'
                          AND column_name = 'land_record_id'
                    ) THEN
                        ALTER TABLE purandar_airport_new.app_documentmaster
                        ADD COLUMN land_record_id bigint NULL;
                    END IF;
                END IF;
            END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
