#!/usr/bin/env python
#
# @descr    Checks OSPFv3 sessions on Cisco IOS devices
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
import argparse
from lib.cnh_nm import STATE_OK, STATE_CRIT
from lib.cnh_nm import my_snmp_walk
from lib.cnh_nm import trigger_not_ok, check_if_ok


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


# Get all interfaces, and then get OSPFv3 data for that interface
rawdata = my_snmp_walk(args, 'IF-MIB::ifDescr')
interface = None
for obj in rawdata:
    if str(obj.value) == args.i:
        interface = obj
if not interface:
    print "CRITICAL: Interface {} not found!".format(args.i)
    sys.exit(STATE_CRIT)
rawdata = my_snmp_walk(args, 'OSPFV3-MIB::ospfv3NbrState.{}'.format(interface.oid_index))


# Check for neighbours and their states
status = STATE_OK
statusstr = ""
num_neis = 0

for nei in rawdata:
    num_neis += 1
    nei_state = int(str(nei.value))
    if nei_state not in ospfv3_ok_states:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            "Neighbour {} on interface {} down".format(num_neis, args.i))

if num_neis < 1:
    status, statusstr = trigger_not_ok(
        status,
        statusstr,
        STATE_CRIT,
        "CRITICAL: No OSPFv3 neighbours found on interface {}".format(args.i))


# Check status
check_if_ok(status, statusstr)

print "OK: All {} neighbours on interface {} is up".format(num_neis, args.i)
sys.exit(STATE_OK)
