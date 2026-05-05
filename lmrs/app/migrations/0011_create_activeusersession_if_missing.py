from django.db import migrations


def create_active_user_session_if_missing(apps, schema_editor):
    ActiveUserSession = apps.get_model("app", "ActiveUserSession")
    existing_tables = schema_editor.connection.introspection.table_names()
    if ActiveUserSession._meta.db_table not in existing_tables:
        schema_editor.create_model(ActiveUserSession)


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0010_create_missing_village_tables"),
    ]

    operations = [
        migrations.RunPython(
            create_active_user_session_if_missing,
            migrations.RunPython.noop,
        ),
    ]
