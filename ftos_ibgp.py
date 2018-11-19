#!/usr/bin/env python
#
# @descr    Checks iBGP status of FTOS devices
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
import argparse
from lib.cnh_nm import STATE_OK, STATE_WARN, STATE_CRIT
from lib.cnh_nm import my_snmp_get, snmpresult_to_dict, my_snmp_walk
from lib.cnh_nm import trigger_not_ok, check_if_ok, ftos_get_peer_ip


# Argument parsing
parser = argparse.ArgumentParser(description='Check iBGP session status')
parser.add_argument('-C', metavar='<community>', required=True,
                    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Host to check')
args = parser.parse_args()


# Get local AS number
local_as = my_snmp_get(args, 'DELL-NETWORKING-BGP4-V2-MIB::dellNetBgpM2LocalAs.0').value


# Get all BGP peers
oids = [
    'DELL-NETWORKING-BGP4-V2-MIB::dellNetBgpM2PeerIdentifier',
    'DELL-NETWORKING-BGP4-V2-MIB::dellNetBgpM2PeerState',
    'DELL-NETWORKING-BGP4-V2-MIB::dellNetBgpM2PeerStatus',
    'DELL-NETWORKING-BGP4-V2-MIB::dellNetBgpM2PeerRemoteAddrType',
    'DELL-NETWORKING-BGP4-V2-MIB::dellNetBgpM2PeerRemoteAddr',
    'DELL-NETWORKING-BGP4-V2-MIB::dellNetBgpM2PeerRemoteAs'
]
rawdata = my_snmp_walk(args, oids)
data = snmpresult_to_dict(rawdata)


# Now loop over data, and for _iBGP_ check the states
status = STATE_OK
statusstr = ''
num_ibgp = 0
for index, peer in data.iteritems():
    if local_as not in peer['dellNetBgpM2PeerRemoteAs'].value:
        continue
    num_ibgp += 1
    peername = ftos_get_peer_ip(peer['dellNetBgpM2PeerRemoteAddr'], peer['dellNetBgpM2PeerRemoteAddrType'])

    bgp_fsm_state = int(str(peer['dellNetBgpM2PeerStatus'].value))
    if bgp_fsm_state == 1:  # 1=halted, 2=running
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_WARN,
            "{} iBGP Admin down".format(peername))
        continue

    peer_state = int(str(peer['dellNetBgpM2PeerState'].value))
    if peer_state in [1, 2, 3, 4, 5]:  # idle/connect/active/opensent/openconfirm, 6=established
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            "{} iBGP session down".format(peername))


# All checks completed, exiting with the relevant message
check_if_ok(status, statusstr)

print "OK: All ({}) iBGP sessions established".format(num_ibgp)
sys.exit(STATE_OK)
