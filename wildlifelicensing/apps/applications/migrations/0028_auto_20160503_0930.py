# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-05-03 01:30
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0014_auto_20160428_1124'),
        ('applications', '0027_merge'),
    ]

    operations = [
        migrations.RenameField(
            model_name='assessment',
            old_name='assessor_department',
            new_name='assessor_group',
        ),
    ]
