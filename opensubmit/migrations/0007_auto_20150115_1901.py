# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('opensubmit', '0006_vminstancenovasecuritygroups'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vminstancenovasecuritygroups',
            name='security_group',
            field=models.CharField(help_text=b'Security Group name', max_length=256),
            preserve_default=True,
        ),
    ]
