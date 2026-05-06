from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0003_landrecord712_document_712"),
    ]

    operations = [
        migrations.AddField(
            model_name="landrecord712",
            name="original_document_name",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]

