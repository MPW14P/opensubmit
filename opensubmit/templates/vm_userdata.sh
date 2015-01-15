#!/bin/sh
curl {{ script_url }} > /usr/bin/submit
chmod +x /usr/bin/submit
passwd -d root

