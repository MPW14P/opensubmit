#!/bin/sh

if [ "$#" -ne 1 ] || ! [ -f "$1" ]; then
	echo Usage: $0 \<submission file\> >&2
	exit 1
fi

curl -F token={{ vm.token }} -F submission=@"$1" {{ submit_url }}
echo 


