# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('opensubmit', '0004_auto_20150115_1622'),
    ]

    operations = [
        migrations.AddField(
            model_name='assignment',
            name='nova_network',
            field=models.CharField(default=None, max_length=38, null=True, blank=True),
            preserve_default=True,
        ),
    ]
