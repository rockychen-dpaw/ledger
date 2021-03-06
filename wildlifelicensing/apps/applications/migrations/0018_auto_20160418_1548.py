# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-04-18 07:48
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0011_auto_20160418_1230'),
        ('applications', '0017_remove_application_conditions'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApplicationCondition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField()),
                ('application', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='applications.Application')),
                ('condition', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.Condition')),
            ],
        ),
        migrations.AddField(
            model_name='application',
            name='conditions',
            field=models.ManyToManyField(through='applications.ApplicationCondition', to='main.Condition'),
        ),
        migrations.AlterUniqueTogether(
            name='applicationcondition',
            unique_together=set([('condition', 'application', 'order')]),
        ),
    ]
