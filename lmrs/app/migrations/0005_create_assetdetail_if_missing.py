from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0004_add_missing_documentmaster_entry_id"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS app_assetdetail (
                id BIGSERIAL PRIMARY KEY,
                plot VARCHAR(50) NOT NULL DEFAULT '',
                name VARCHAR(100) NOT NULL DEFAULT '',
                asset_parameter JSONB NOT NULL DEFAULT '{}'::jsonb,
                valuation NUMERIC(15,2) NULL,
                inspection_id BIGINT NOT NULL,
                CONSTRAINT app_assetdetail_inspection_id_fk
                    FOREIGN KEY (inspection_id)
                    REFERENCES app_inspection (id)
                    ON DELETE CASCADE
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS app_assetdetail;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS app_assetdetail_inspection_id_idx ON app_assetdetail (inspection_id);",
            reverse_sql="DROP INDEX IF EXISTS app_assetdetail_inspection_id_idx;",
        ),
    ]
