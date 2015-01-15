# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('opensubmit', '0003_vminstance'),
    ]

    operations = [
        migrations.AddField(
            model_name='assignment',
            name='nova_flavor',
            field=models.CharField(default=None, max_length=38, null=True, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='assignment',
            name='nova_image',
            field=models.CharField(default=None, max_length=38, null=True, blank=True),
            preserve_default=True,
        ),
    ]
