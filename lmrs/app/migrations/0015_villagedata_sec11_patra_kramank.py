from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0014_villagedata_related_section_rows'),
    ]

    operations = [
        migrations.AddField(
            model_name='villagedata',
            name='sec11_patra_kramank',
            field=models.TextField(blank=True),
        ),
    ]
