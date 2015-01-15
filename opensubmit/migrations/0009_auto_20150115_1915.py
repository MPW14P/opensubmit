# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('opensubmit', '0008_vminstance_token'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vminstance',
            name='token',
            field=models.CharField(max_length=38),
            preserve_default=True,
        ),
    ]
