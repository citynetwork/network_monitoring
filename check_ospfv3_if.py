#!/usr/bin/env python

import sys
import argparse
from easysnmp import snmp_get, snmp_bulkwalk, EasySNMPConnectionError, EasySNMPTimeoutError

# Nagios states
STATE_OK = 0
STATE_WARN = 1
STATE_CRIT = 2
STATE_UNKNOWN = 3

# Vars
ospfv3_statemappings = {
        1: 'down',
        2: 'attempt',
        3: 'init',
        4: 'twoway',
        5: 'exchangestart',
        6: 'exchange',
        7: 'loading',
        8: 'full'
}
ospfv3_ok_states = [4, 8]

# Argument parsing
parser = argparse.ArgumentParser(description='Check OSPFv3 session status for interface')
parser.add_argument('-C', metavar='<community>', required=True,
                    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Host to check')
parser.add_argument('-i', metavar='<interface>', required=True,
                    help='Interface to check')
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


# Get all interfaces, and then get OSPFv3 data for that interface
try:
    rawdata = snmp_bulkwalk('IF-MIB::ifDescr', hostname=args.H, community=args.C, version=2)
    interface = None
    for obj in rawdata:
        if str(obj.value) == args.i:
            interface = obj
    if not interface:
        print "CRITICAL: Interface {} not found!".format(args.i)
        sys.exit(STATE_CRIT)
    rawdata = snmp_bulkwalk(
            'OSPFV3-MIB::ospfv3NbrState.{}'.format(interface.oid_index),
            hostname=args.H,
            community=args.C,
            version=2
    )
except (EasySNMPConnectionError, EasySNMPTimeoutError) as err:
    snmp_err(err)


# Check for neighbours and their states
status = STATE_OK
statusstr = ""
num_neis = 0

for nei in rawdata:
    num_neis += 1
    nei_state = int(str(nei.value))
    if nei_state not in ospfv3_ok_states:
        trigger_not_ok(STATE_CRIT, "Neighbour {} on interface {} down".format(num_neis, args.i))

if status != STATE_OK:
    if status == STATE_WARN:
        statusstr = "WARNING:" + statusstr
    else:
        statusstr = "CRITICAL:" + statusstr
    print statusstr
    sys.exit(status)

if num_neis < 1:
    print "CRITICAL: No OSPFv3 neighbours found on interface {}".format(args.i)
    sys.exit(STATE_CRIT)


# All good
print "OK: All {} neighbours on interface {} is up".format(num_neis, args.i)
sys.exit(STATE_OK)
