# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import opensubmit.fields


class Migration(migrations.Migration):

    dependencies = [
        ('opensubmit', '0010_auto_20150115_1933'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assignment',
            name='nova_security_groups',
            field=opensubmit.fields.SeparatedValuesField(),
            preserve_default=True,
        ),
    ]
