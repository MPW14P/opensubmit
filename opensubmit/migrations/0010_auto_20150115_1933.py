# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('opensubmit', '0009_auto_20150115_1915'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='vminstancenovasecuritygroups',
            name='assignment',
        ),
        migrations.DeleteModel(
            name='VMInstanceNovaSecurityGroups',
        ),
        migrations.AddField(
            model_name='assignment',
            name='nova_security_groups',
            field=models.TextField(default=b'', blank=True),
            preserve_default=True,
        ),
    ]
