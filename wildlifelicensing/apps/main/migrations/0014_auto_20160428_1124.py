# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-04-28 03:24
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('applications', '0025_auto_20160428_1124'),
        ('main', '0013_condition_obsolete'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssessorGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('email', models.EmailField(max_length=254)),
                ('members', models.ManyToManyField(blank=True, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.RemoveField(
            model_name='assessordepartment',
            name='members',
        ),
        migrations.RemoveField(
            model_name='assessordepartment',
            name='suggested_conditions',
        ),
        migrations.DeleteModel(
            name='AssessorDepartment',
        ),
    ]
