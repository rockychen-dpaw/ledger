# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-04-28 03:24
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0024_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='application',
            name='customer_status',
            field=models.CharField(choices=[('draft', 'Draft'), ('under_review', 'Under Review'), ('id_required', 'Identification Required'), ('amendment_required', 'Amendment Required'), ('id_and_amendment_required', 'Identification/Amendments Required'), ('approved', 'Approved'), ('declined', 'Declined')], default='draft', max_length=30, verbose_name='Customer Status'),
        ),
        migrations.AlterField(
            model_name='assessment',
            name='assessor_department',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.AssessorGroup'),
        ),
    ]
