# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-05-17 02:31
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('licence', '0006_licencetype_is_renewable'),
    ]

    operations = [
        migrations.AddField(
            model_name='licence',
            name='is_renewable',
            field=models.NullBooleanField(),
        ),
    ]
