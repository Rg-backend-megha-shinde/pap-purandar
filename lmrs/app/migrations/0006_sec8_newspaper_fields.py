from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0005_villagedata_sec14_approved_rate_details'),
    ]

    operations = [
        migrations.AddField(
            model_name='villagedata18_1row',
            name='paper1_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='villagedata18_1row',
            name='paper1_name',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='villagedata18_1row',
            name='paper2_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='villagedata18_1row',
            name='paper2_name',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='villagedata18_1rowfile',
            name='field_key',
            field=models.CharField(default='main', max_length=40),
        ),
    ]
