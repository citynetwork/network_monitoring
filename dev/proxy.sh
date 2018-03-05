#!/bin/sh

com="$1"
shift
/opt/plugins/custom/network_monitoring/$com $@
