from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0009_create_villagedatasec15rate_if_missing"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS app_villagedata (
                id BIGSERIAL PRIMARY KEY,
                district TEXT NOT NULL,
                taluka TEXT NOT NULL,
                village TEXT NOT NULL,
                sec1_adesh_kramank TEXT NOT NULL DEFAULT '',
                sec1_date DATE NULL,
                sec1_files TEXT NOT NULL DEFAULT '',
                sec2_adhisuchana_kramank TEXT NOT NULL DEFAULT '',
                sec2_date DATE NULL,
                sec2_files TEXT NOT NULL DEFAULT '',
                sec2_paper1_name TEXT NOT NULL DEFAULT '',
                sec2_paper1_date DATE NULL,
                sec2_paper1_files TEXT NOT NULL DEFAULT '',
                sec2_paper2_name TEXT NOT NULL DEFAULT '',
                sec2_paper2_date DATE NULL,
                sec2_paper2_files TEXT NOT NULL DEFAULT '',
                sec3_adhisuchana_kramank TEXT NOT NULL DEFAULT '',
                sec3_date DATE NULL,
                sec3_files TEXT NOT NULL DEFAULT '',
                sec5_prastaav_kramank TEXT NOT NULL DEFAULT '',
                sec5_date DATE NULL,
                sec5_files TEXT NOT NULL DEFAULT '',
                sec6_register_number TEXT NOT NULL DEFAULT '',
                sec6_date DATE NULL,
                sec6_parishisht16_files TEXT NOT NULL DEFAULT '',
                sec6_nakasha_files TEXT NOT NULL DEFAULT '',
                sec7_aakshep_details TEXT NOT NULL DEFAULT '',
                sec7_files TEXT NOT NULL DEFAULT '',
                sec9_paper1_name TEXT NOT NULL DEFAULT '',
                sec9_paper1_date DATE NULL,
                sec9_paper1_files TEXT NOT NULL DEFAULT '',
                sec9_paper2_name TEXT NOT NULL DEFAULT '',
                sec9_paper2_date DATE NULL,
                sec9_paper2_files TEXT NOT NULL DEFAULT '',
                sec10_prastaav_kramank TEXT NOT NULL DEFAULT '',
                sec10_date DATE NULL,
                sec10_files TEXT NOT NULL DEFAULT '',
                sec11_date DATE NULL,
                sec11_files TEXT NOT NULL DEFAULT '',
                sec12_zone_details TEXT NOT NULL DEFAULT '',
                sec12_date DATE NULL,
                sec12_files TEXT NOT NULL DEFAULT '',
                sec13_kharedi_vikri_details TEXT NOT NULL DEFAULT '',
                sec13_files TEXT NOT NULL DEFAULT '',
                sec14_meeting_details TEXT NOT NULL DEFAULT '',
                sec14_date DATE NULL,
                sec14_files TEXT NOT NULL DEFAULT '',
                sec16_letter_details TEXT NOT NULL DEFAULT '',
                sec16_date DATE NULL,
                sec16_files TEXT NOT NULL DEFAULT '',
                sec17_letter_details TEXT NOT NULL DEFAULT '',
                sec17_date DATE NULL,
                sec17_files TEXT NOT NULL DEFAULT '',
                sec18_letter_details TEXT NOT NULL DEFAULT '',
                sec18_date DATE NULL,
                sec18_files TEXT NOT NULL DEFAULT '',
                sec19_letter_details TEXT NOT NULL DEFAULT '',
                sec19_date DATE NULL,
                sec19_files TEXT NOT NULL DEFAULT '',
                sec20_letter_details TEXT NOT NULL DEFAULT '',
                sec20_date DATE NULL,
                sec20_files TEXT NOT NULL DEFAULT '',
                sec21_prastaav TEXT NOT NULL DEFAULT '',
                sec21_prastaav_date DATE NULL,
                sec21_prastaav_files TEXT NOT NULL DEFAULT '',
                sec21_karyavrutant TEXT NOT NULL DEFAULT '',
                sec21_karyavrutant_date DATE NULL,
                sec21_karyavrutant_files TEXT NOT NULL DEFAULT '',
                sec23_kramank TEXT NOT NULL DEFAULT '',
                sec23_date DATE NULL,
                sec23_files TEXT NOT NULL DEFAULT '',
                sec24_court_details TEXT NOT NULL DEFAULT '',
                sec24_files TEXT NOT NULL DEFAULT '',
                sec25_kramank TEXT NOT NULL DEFAULT '',
                sec25_date DATE NULL,
                sec25_files TEXT NOT NULL DEFAULT '',
                is_final_submitted BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                user_id INTEGER NOT NULL
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS app_villagedata;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS app_villagedata_user_id_idx ON app_villagedata (user_id);",
            reverse_sql="DROP INDEX IF EXISTS app_villagedata_user_id_idx;",
        ),
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS app_villagedatafile (
                id BIGSERIAL PRIMARY KEY,
                field_key VARCHAR(100) NOT NULL,
                file VARCHAR(1000) NOT NULL,
                uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                village_data_id BIGINT NOT NULL
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS app_villagedatafile;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS app_villagedatafile_village_data_id_idx ON app_villagedatafile (village_data_id);",
            reverse_sql="DROP INDEX IF EXISTS app_villagedatafile_village_data_id_idx;",
        ),
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS app_villagedata8arecord (
                id BIGSERIAL PRIMARY KEY,
                khate_kramank TEXT NOT NULL DEFAULT '',
                navavar_kshetra TEXT NOT NULL DEFAULT '',
                ferfar_kramank TEXT NOT NULL DEFAULT '',
                ferfar_date DATE NULL,
                files TEXT NOT NULL DEFAULT '',
                village_data_id BIGINT NOT NULL
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS app_villagedata8arecord;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS app_villagedata8arecord_village_data_id_idx ON app_villagedata8arecord (village_data_id);",
            reverse_sql="DROP INDEX IF EXISTS app_villagedata8arecord_village_data_id_idx;",
        ),
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS app_villagedata8afile (
                id BIGSERIAL PRIMARY KEY,
                file VARCHAR(1000) NOT NULL,
                uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                record_8a_id BIGINT NOT NULL
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS app_villagedata8afile;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS app_villagedata8afile_record_8a_id_idx ON app_villagedata8afile (record_8a_id);",
            reverse_sql="DROP INDEX IF EXISTS app_villagedata8afile_record_8a_id_idx;",
        ),
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS app_villagedata15_2row (
                id BIGSERIAL PRIMARY KEY,
                adhisuchana_kramank TEXT NOT NULL DEFAULT '',
                adhisuchana_date DATE NULL,
                paper1_name TEXT NOT NULL DEFAULT '',
                paper1_date DATE NULL,
                paper2_name TEXT NOT NULL DEFAULT '',
                paper2_date DATE NULL,
                village_data_id BIGINT NOT NULL
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS app_villagedata15_2row;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS app_villagedata15_2row_village_data_id_idx ON app_villagedata15_2row (village_data_id);",
            reverse_sql="DROP INDEX IF EXISTS app_villagedata15_2row_village_data_id_idx;",
        ),
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS app_villagedata15_2rowfile (
                id BIGSERIAL PRIMARY KEY,
                field_key VARCHAR(40) NOT NULL DEFAULT 'main',
                file VARCHAR(1000) NOT NULL,
                uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                row_15_2_id BIGINT NOT NULL
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS app_villagedata15_2rowfile;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS app_villagedata15_2rowfile_row_15_2_id_idx ON app_villagedata15_2rowfile (row_15_2_id);",
            reverse_sql="DROP INDEX IF EXISTS app_villagedata15_2rowfile_row_15_2_id_idx;",
        ),
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS app_villagedata18_1row (
                id BIGSERIAL PRIMARY KEY,
                adhisuchana_kramank TEXT NOT NULL DEFAULT '',
                adhisuchana_date DATE NULL,
                village_data_id BIGINT NOT NULL
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS app_villagedata18_1row;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS app_villagedata18_1row_village_data_id_idx ON app_villagedata18_1row (village_data_id);",
            reverse_sql="DROP INDEX IF EXISTS app_villagedata18_1row_village_data_id_idx;",
        ),
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS app_villagedata18_1rowfile (
                id BIGSERIAL PRIMARY KEY,
                file VARCHAR(1000) NOT NULL,
                uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                row_18_1_id BIGINT NOT NULL
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS app_villagedata18_1rowfile;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS app_villagedata18_1rowfile_row_18_1_id_idx ON app_villagedata18_1rowfile (row_18_1_id);",
            reverse_sql="DROP INDEX IF EXISTS app_villagedata18_1rowfile_row_18_1_id_idx;",
        ),
    ]
