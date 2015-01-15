# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('opensubmit', '0002_auto_20141208_1122'),
    ]

    operations = [
        migrations.CreateModel(
            name='VMInstance',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', models.CharField(help_text=b'Instance UUID', max_length=38)),
                ('assignment', models.ForeignKey(to='opensubmit.Assignment')),
                ('owner', models.ForeignKey(related_name='vms', to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
