import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Inspection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('district', models.CharField(max_length=100)),
                ('taluka', models.CharField(max_length=100)),
                ('village', models.CharField(max_length=100)),
                ('gut_number', models.CharField(max_length=50)),
                ('officer', models.CharField(max_length=200)),
                ('date', models.DateField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='TreeDetail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('plot', models.CharField(blank=True, max_length=50)),
                ('name', models.CharField(blank=True, max_length=100)),
                ('length', models.FloatField(blank=True, null=True)),
                ('width', models.FloatField(blank=True, null=True)),
                ('girth', models.FloatField(blank=True, null=True)),
                ('height', models.FloatField(blank=True, null=True)),
                ('inspection', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='trees', to='app.inspection')),
            ],
        ),
         migrations.CreateModel(
            name='LandRecord712',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('district', models.CharField(max_length=100)),
                ('taluka', models.CharField(max_length=100)),
                ('village', models.CharField(max_length=150)),
                ('gut_number', models.CharField(max_length=50)),
                ('farmer_name', models.CharField(max_length=200)),
                ('aakarnee', models.CharField(blank=True, max_length=100, null=True)),
                ('rate_applied', models.CharField(blank=True, max_length=100, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='ReadyReckonerRate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('district', models.CharField(max_length=100)),
                ('taluka', models.CharField(max_length=100)),
                ('village', models.CharField(max_length=100)),
                ('assessment_type', models.CharField(max_length=200)),
                ('assessment_range_min', models.DecimalField(decimal_places=2, max_digits=10)),
                ('assessment_range_max', models.DecimalField(decimal_places=2, max_digits=10)),
                ('rate', models.DecimalField(decimal_places=2, max_digits=15)),
                ('unit', models.CharField(max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]



