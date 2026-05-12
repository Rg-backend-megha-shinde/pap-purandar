from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_processchartcase_processchartdepartmentrow_and_more'),
        ('app', '0008_rename_village_row_tables'),
    ]

    operations = [
        migrations.AddField(
            model_name='villagedata',
            name='land_acquisition_purpose',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='villagedata',
            name='collector_name',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='villagedata',
            name='collector_office_name',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='villagedata',
            name='collector_office_address',
            field=models.TextField(blank=True),
        ),
    ]
