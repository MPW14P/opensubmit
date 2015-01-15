# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('opensubmit', '0007_auto_20150115_1901'),
    ]

    operations = [
        migrations.AddField(
            model_name='vminstance',
            name='token',
            field=models.CharField(default='.', max_length=40),
            preserve_default=False,
        ),
    ]
