#!/bin/sh

check_nrpe="/opt/plugins/check_nrpe"

usage() {
	echo "Usage: $0 <proxy-host> <command> [<args>] ..."
	exit
}

if [ -z "$1" ]; then
	usage
elif [ -z "$2" ]; then
	usage
fi

proxy_host="$1"
shift

if [ -z "$1" ]; then
	$check_nrpe -H $proxy_host -c proxy
else
	argstr="$1"
	shift
	while true; do
		if [ $# -lt 1 ]; then
			break
		fi
		argstr="$argstr $1"
		shift
	done
	$check_nrpe -H $proxy_host -c proxy -a "$argstr"
fi
