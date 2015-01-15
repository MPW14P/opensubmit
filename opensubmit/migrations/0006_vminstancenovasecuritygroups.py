# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('opensubmit', '0005_assignment_nova_network'),
    ]

    operations = [
        migrations.CreateModel(
            name='VMInstanceNovaSecurityGroups',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('security_group', models.CharField(help_text=b'Security Group UUID', max_length=38)),
                ('assignment', models.ForeignKey(related_name='nova_security_groups', to='opensubmit.Assignment')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
