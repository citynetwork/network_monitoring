#!/usr/bin/env python
#
# @descr    Checks BGP status on Cisco IOS devices
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import argparse
import ipaddress
import sys
from lib.cnh_nm import STATE_OK, STATE_CRIT, STATE_WARN
from lib.cnh_nm import my_snmp_walk, snmp_oid_decode_ip, snmpresult_to_dict
from lib.cnh_nm import trigger_not_ok, check_if_ok


# Argument parsing
parser = argparse.ArgumentParser(description='Check iBGP session status')
parser.add_argument('-C', metavar='<community>', required=True,
                    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Host to check')
parser.add_argument('-p', metavar='<peer>', required=True,
                    help='Peer to check')
args = parser.parse_args()

# Expand IPv6
orig_args_p = args.p
if ':' in args.p:
    addr = ipaddress.ip_address(unicode(args.p))
    args.p = addr.exploded.lower()


oids = [
    'CISCO-BGP4-MIB::cbgpPeer2AdminStatus',
    'CISCO-BGP4-MIB::cbgpPeer2State',
    'CISCO-BGP4-MIB::cbgpPeer2LastErrorTxt',
    'CISCO-BGP4-MIB::cbgpPeer2RemoteAs'
]


# Get all BGP peers
rawdata = my_snmp_walk(args, oids)
data = snmpresult_to_dict(rawdata)


# Now loop over data, and check the states
status = STATE_OK
statusstr = ''
peer_found = False
remote_as = ""
for index, peer in data.iteritems():
    peer_ip = snmp_oid_decode_ip(index)
    if peer_ip != args.p:
        continue
    peer_found = True
    admin_state = peer['cbgpPeer2AdminStatus'].value
    bgp_state = peer['cbgpPeer2State'].value
    last_error = peer['cbgpPeer2LastErrorTxt'].value
    remote_as = peer['cbgpPeer2RemoteAs'].value

    if not last_error.strip():
        last_error = 'None'

    admin_state = int(str(admin_state))
    if admin_state == 1:  # Down
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_WARN,
            "{}(AS{}) admin down".format(orig_args_p, remote_as))
        continue
    bgp_state = int(str(bgp_state))
    if bgp_state in [0, 1, 2, 3, 4, 5]:  # none/idle/connect/active/opensent/openconfirm
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            "{}(AS{}) BGP session down".format(orig_args_p, remote_as))
        continue
    statusstr = last_error
if not peer_found:
    status, statusstr = trigger_not_ok(
        status,
        statusstr,
        STATE_CRIT,
        "BGP session for peer {} not found!".format(orig_args_p))


# All checks completed, exiting with the relevant message
check_if_ok(status, statusstr)

print "OK: BGP session with {}(AS{}) established, last error: {}".format(orig_args_p, remote_as, statusstr)
sys.exit(STATE_OK)
