# Generated by Django 5.1.4 on 2025-04-05 09:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tapAppGestion', '0021_remove_pedidoproducto_unidades_pagadas'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedidoproducto',
            name='impreso_cocina',
            field=models.BooleanField(default=False),
        ),
    ]
