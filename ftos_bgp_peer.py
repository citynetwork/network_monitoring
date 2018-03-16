#!/usr/bin/env python
#
# @descr    Checks BGP peer status of FTOS devices
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
import argparse
from lib.cnh_nm import STATE_OK, STATE_WARN, STATE_CRIT
from lib.cnh_nm import snmpresult_to_dict, my_snmp_walk
from lib.cnh_nm import trigger_not_ok, check_if_ok, ftos_get_peer_ip


# Argument parsing
parser = argparse.ArgumentParser(description='Check BGP session status')
parser.add_argument('-C', metavar='<community>', required=True,
                    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Host to check')
parser.add_argument('-p', metavar='<peer>', required=True,
                    help='Peer to check')
args = parser.parse_args()


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
peer_as = ""
peername = ""
peer_found = False
for index, peer in data.iteritems():
    peername = ftos_get_peer_ip(peer['dellNetBgpM2PeerRemoteAddr'], peer['dellNetBgpM2PeerRemoteAddrType'])
    if peername.lower() != args.p.lower():
        continue
    peer_found = True
    peer_as = "AS" + str(peer['dellNetBgpM2PeerRemoteAs'].value)

    bgp_fsm_state = int(str(peer['dellNetBgpM2PeerStatus'].value))
    if bgp_fsm_state == 1:  # 1=halted, 2=running
        status, statusstr = trigger_not_ok(
                status,
                statusstr,
                STATE_WARN,
                "{}({}) BGP Admin down".format(peername, peer_as))
        break

    peer_state = int(str(peer['dellNetBgpM2PeerState'].value))
    if peer_state in [1, 2, 3, 4, 5]:  # idle/connect/active/opensent/openconfirm, 6=established
        status, statusstr = trigger_not_ok(
                status,
                statusstr,
                STATE_CRIT,
                "{}({}) BGP session down".format(peername, peer_as))
    break

if not peer_found:
    print "CRITICAL: Cannot find any configured BGP session with peer {}".format(args.p)
    sys.exit(STATE_CRIT)


# All checks completed, exiting with the relevant message
check_if_ok(status, statusstr)

print "OK: BGP session with {}({}) established".format(peername, peer_as)
sys.exit(STATE_OK)
