#!/usr/bin/env python
#
# @descr    Checks backup timestamps of all nodes in Oxidized
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import argparse
import json
import sys
import requests
from time import time
from lib.cnh_nm import STATE_OK, STATE_CRIT, STATE_WARN
from lib.cnh_nm import trigger_not_ok, check_if_ok, strtime_to_timestamp


# Argument parsing
parser = argparse.ArgumentParser(description='Checks backup timestamps of all nodes in Oxidized')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Oxidized host')
parser.add_argument('-p', metavar='<port>', required=False,
                    help='Oxidized port (default 8888)')
parser.add_argument('-w', metavar='<seconds>', required=False,
                    help='Emit WARN if something not backuped since <seconds> ago (default 84600)')
parser.add_argument('-c', metavar='<seconds>', required=False,
                    help='Emit CRIT if something not backuped since <seconds> ago (default 169200)')
args = parser.parse_args()
if not args.p:
    args.p = 8888
if not args.w:
    args.w = 84600
if not args.c:
    args.c = 169200


status = STATE_OK
statusstr = ""


# Fetch oxidized node status
resp = requests.get("http://{}:{}/nodes?format=json".format(args.H, args.p))
nodes = json.loads(resp.content)


# Loop over and check timestamps
cur_time = int(time())
for node in nodes:
    node_update_ts = strtime_to_timestamp(node['time'])
    diff_ts = cur_time - node_update_ts
    if diff_ts > args.c:
        status, statusstr = trigger_not_ok(status, statusstr, STATE_CRIT, "{} hasn't been backed up since {}".format(node['name'], node['time']))
    elif diff_ts > args.w:
        status, statusstr = trigger_not_ok(status, statusstr, STATE_WARN, "{} hasn't been backed up since {}".format(node['name'], node['time']))


# Check status and exit accordingly
check_if_ok(status, statusstr)
print "OK: All equipment properly backed up."
sys.exit(status)
