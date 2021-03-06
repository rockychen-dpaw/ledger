# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-03-29 03:30
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0002_condition_wildlifelicencetype'),
        ('applications', '0005_auto_20160329_1130'),
    ]

    operations = [
        migrations.AddField(
            model_name='application',
            name='conditions',
            field=models.ManyToManyField(to='main.Condition'),
        ),
        migrations.AddField(
            model_name='application',
            name='customer_status',
            field=models.CharField(choices=[('draft', 'Draft'), ('pending', 'Pending'), ('under_review', 'Under Review'), ('amendment_required', 'Amendment Required'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='draft', max_length=20, verbose_name='Customer Status'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='application',
            name='notes',
            field=models.TextField(blank=True, verbose_name='Notes'),
        ),
        migrations.AddField(
            model_name='application',
            name='processing_status',
            field=models.CharField(choices=[('draft', 'Draft'), ('new', 'New'), ('incomplete', 'Incomplete'), ('amended', 'Amended'), ('ready_for_assessment', 'Ready for Assessment'), ('awaiting_assessment', 'Awaiting Assessment'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='draft', max_length=20, verbose_name='Processing Status'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='application',
            name='licence_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.WildlifeLicenceType'),
        ),
        migrations.AddField(
            model_name='assessorcomment',
            name='application',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='applications.Application'),
        ),
        migrations.AddField(
            model_name='amendmentrequest',
            name='application',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='applications.Application'),
        ),
    ]
