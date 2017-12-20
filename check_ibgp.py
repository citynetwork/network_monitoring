#!/usr/bin/env python

import sys
import argparse
from collections import defaultdict
from easysnmp import snmp_get, snmp_walk, EasySNMPConnectionError, EasySNMPTimeoutError

# Nagios states
STATE_OK = 0
STATE_WARN = 1
STATE_CRIT = 2
STATE_UNKNOWN = 3

# Argument parsing
parser = argparse.ArgumentParser(description='Check iBGP session status')
parser.add_argument('-C', metavar='<community>', required=True,
		    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True,
		    help='Host to check')
args = parser.parse_args()


# Handle (or rather not handle) SNMP errors
def snmp_err(err):
    global STATE_UNKNOWN
    print "UNKNOWN: SNMP Error: {0}".format(err)
    sys.exit(STATE_UNKNOWN)


# SNMP get wrapper with error handling
def my_snmp_get(oid):
    global args
    try:
        retval = snmp_get(oid, hostname=args.H, community=args.C, version=2)
    except (EasySNMPConnectionError, EasySNMPTimeoutError) as err:
        snmp_err(err)
    return retval


# Status change wrapper
def trigger_not_ok(req_state, txt):
    global status
    global statusstr
    if req_state > status:
        status = req_state
    statusstr += txt + ","


# Get local AS number
local_as = my_snmp_get('BGP4-MIB::bgpLocalAs.0').value

# Get all BGP peers
try:
    rawdata = snmp_walk('CISCO-BGP4-MIB::cbgpPeer2Table', hostname=args.H, community=args.C, version=2)
except (EasySNMPConnectionError, EasySNMPTimeoutError) as err:
    snmp_err(err)

data = defaultdict(dict)
for obj in rawdata:
    data[obj.oid_index][obj.oid] = obj

# We default to an OK status
status = STATE_OK
statusstr = ''

# Now loop over data, and for _iBGP_ check the states
for index, peer in data.iteritems():
    if local_as not in peer['cbgpPeer2RemoteAs'].value:
        continue
    peername = peer['cbgpPeer2RemoteIdentifier'].value
    admin_state = peer['cbgpPeer2AdminStatus'].value
    bgp_state = peer['cbgpPeer2State'].value
    if admin_state == 1:  # Down
        trigger_not_ok(STATE_WARN, "{} admin down".format(peername))
        continue
    if bgp_state in [0, 1, 2, 3, 4, 5]:  # none/idle/connect/active/opensent/openconfirm
        trigger_not_ok(STATE_CRIT, "{} BGP session down".format(peername))
        continue

# All checks completed, exiting with the relevant message
if status == STATE_OK:
    statusstr = "OK: All iBGP sessions established"
elif status == STATE_WARN:
    statusstr = "WARNING:" + statusstr
elif status == STATE_CRIT:
    statusstr = "CRITICAL:" + statusstr
print statusstr
sys.exit(status)
