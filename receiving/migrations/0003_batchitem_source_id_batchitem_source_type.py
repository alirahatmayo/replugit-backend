# Generated by Django 5.1.3 on 2025-04-26 06:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('receiving', '0002_remove_batchitem_unique_batch_product_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='batchitem',
            name='source_id',
            field=models.CharField(blank=True, help_text='ID in the source system', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='batchitem',
            name='source_type',
            field=models.CharField(blank=True, help_text="Source system type (e.g., 'manifest')", max_length=50, null=True),
        ),
    ]
