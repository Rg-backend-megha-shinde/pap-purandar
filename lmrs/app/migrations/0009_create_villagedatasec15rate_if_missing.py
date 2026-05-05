from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0008_add_missing_readyreckonerrate_columns"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS app_villagedatasec15rate (
                id BIGSERIAL PRIMARY KEY,
                approved_rate NUMERIC(15,2) NULL,
                rr_rate_id BIGINT NOT NULL,
                village_data_id BIGINT NOT NULL,
                CONSTRAINT app_villagedatasec15rate_unique
                    UNIQUE (village_data_id, rr_rate_id)
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS app_villagedatasec15rate;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS app_villagedatasec15rate_rr_rate_id_idx ON app_villagedatasec15rate (rr_rate_id);",
            reverse_sql="DROP INDEX IF EXISTS app_villagedatasec15rate_rr_rate_id_idx;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS app_villagedatasec15rate_village_data_id_idx ON app_villagedatasec15rate (village_data_id);",
            reverse_sql="DROP INDEX IF EXISTS app_villagedatasec15rate_village_data_id_idx;",
        ),
    ]
