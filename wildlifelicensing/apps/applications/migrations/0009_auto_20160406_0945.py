# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-04-06 01:45
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0008_auto_20160404_1617'),
    ]

    operations = [
        migrations.AlterField(
            model_name='application',
            name='character_check_status',
            field=models.CharField(choices=[('not_checked', 'Not Checked'), ('accepted', 'Accepted'), ('rejected', 'Rejected')], default='not_checked', max_length=20, verbose_name='Character Check Status'),
        ),
        migrations.AlterField(
            model_name='application',
            name='customer_status',
            field=models.CharField(choices=[('draft', 'Draft'), ('pending', 'Pending'), ('under_review', 'Under Review'), ('amendment_required', 'Amendment Required'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='draft', max_length=20, verbose_name='Customer Status'),
        ),
        migrations.AlterField(
            model_name='application',
            name='id_check_status',
            field=models.CharField(choices=[('not_checked', 'Not Checked'), ('awaiting_update', 'Awaiting Update'), ('updated', 'Updated'), ('accepted', 'Accepted')], default='not_checked', max_length=20, verbose_name='Identification Check Status'),
        ),
        migrations.AlterField(
            model_name='application',
            name='processing_status',
            field=models.CharField(choices=[('draft', 'Draft'), ('new', 'New'), ('ready_for_action', 'Ready for Action'), ('awaiting_applicant_response', 'Awaiting Applicant Response'), ('awaiting_assessor_response', 'Awaiting Assessor Response'), ('awaiting_responses', 'Awaiting Responses'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='draft', max_length=30, verbose_name='Processing Status'),
        ),
        migrations.AlterField(
            model_name='application',
            name='review_status',
            field=models.CharField(choices=[('not_reviewed', 'Not Reviewed'), ('awaiting_amendments', 'Awaiting Amendments'), ('amended', 'Amended'), ('accepted', 'Accepted'), ('rejected', 'Rejected')], default='not_reviewed', max_length=20, verbose_name='Review Status'),
        ),
    ]
