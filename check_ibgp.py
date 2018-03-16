#!/usr/bin/env python
#
# @descr    Checks iBGP status of Cisco IOS devices
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
import argparse
from lib.cnh_nm import STATE_OK, STATE_WARN, STATE_CRIT
from lib.cnh_nm import my_snmp_get, snmpresult_to_dict, my_snmp_walk
from lib.cnh_nm import trigger_not_ok, check_if_ok


# Argument parsing
parser = argparse.ArgumentParser(description='Check iBGP session status')
parser.add_argument('-C', metavar='<community>', required=True,
                    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Host to check')
args = parser.parse_args()


# Get local AS number
local_as = my_snmp_get(args, 'BGP4-MIB::bgpLocalAs.0').value


# Get all BGP peers
oids = [
        'CISCO-BGP4-MIB::cbgpPeer2RemoteAs',
        'CISCO-BGP4-MIB::cbgpPeer2AdminStatus',
        'CISCO-BGP4-MIB::cbgpPeer2State',
        'CISCO-BGP4-MIB::cbgpPeer2RemoteIdentifier'
]
rawdata = my_snmp_walk(args, oids)
data = snmpresult_to_dict(rawdata)


# Now loop over data, and for _iBGP_ check the states
status = STATE_OK
statusstr = ''
num_ibgp = 0
for index, peer in data.iteritems():
    if local_as not in peer['cbgpPeer2RemoteAs'].value:
        continue
    num_ibgp += 1
    peername = peer['cbgpPeer2RemoteIdentifier'].value
    admin_state = peer['cbgpPeer2AdminStatus'].value
    bgp_state = peer['cbgpPeer2State'].value
    if admin_state == 1:  # Down
        status, statusstr = trigger_not_ok(
                status,
                statusstr,
                STATE_WARN,
                "{} admin down".format(peername))
        continue
    if bgp_state in [0, 1, 2, 3, 4, 5]:  # none/idle/connect/active/opensent/openconfirm
        status, statusstr = trigger_not_ok(
                status,
                statusstr,
                STATE_CRIT,
                "{} BGP session down".format(peername))
        continue


# All checks completed, exiting with the relevant message
check_if_ok(status, statusstr)

print "OK: All ({}) iBGP sessions established".format(num_ibgp)
sys.exit(STATE_OK)
