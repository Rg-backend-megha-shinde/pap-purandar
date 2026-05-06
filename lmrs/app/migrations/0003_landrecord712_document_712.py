from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0002_add_missing_documentmaster_land_record_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="landrecord712",
            name="document_712",
            field=models.FileField(blank=True, null=True, upload_to="land_record_712/"),
        ),
    ]

