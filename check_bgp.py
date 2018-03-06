#!/usr/bin/env python

import argparse
import ipaddress
import sys
from collections import defaultdict
from easysnmp import snmp_get, snmp_bulkwalk, EasySNMPConnectionError, EasySNMPTimeoutError

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
parser.add_argument('-p', metavar='<peer>', required=True,
                    help='Peer to check')
args = parser.parse_args()

# Expand IPv6
orig_args_p = args.p
if ':' in args.p:
    addr = ipaddress.ip_address(unicode(args.p))
    args.p = addr.exploded.lower()


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


# Detecting IP version of SNMP OID index
def snmp_oid_ipver(oid):
    if oid.startswith("1.4"):
        return 'IPv4'
    elif oid.startswith("2.16"):
        return 'IPv6'
    else:
        return None


# Decoding IP from SNMP OID index
def snmp_oid_decode_ip(oid):
    ipver = snmp_oid_ipver(oid)
    if 'IPv4' == ipver:
        return oid[4:]
    else:
        ip_coded = oid[5:].split('.')
        ip_decoded = ""
        i = 1
        for part in ip_coded:
            ip_decoded += str(hex(int(part, 10)))[2:].zfill(2)
            if i % 2 == 0:
                ip_decoded += ':'
            i += 1
        if isinstance(ip_decoded, unicode):
            return ip_decoded.lower().rstrip(':')
        else:
            return unicode(ip_decoded.lower().rstrip(':'))


# Get all BGP peers
try:
    oids = ['CISCO-BGP4-MIB::cbgpPeer2RemoteIdentifier','CISCO-BGP4-MIB::cbgpPeer2AdminStatus','CISCO-BGP4-MIB::cbgpPeer2State','CISCO-BGP4-MIB::cbgpPeer2LastErrorTxt', 'CISCO-BGP4-MIB::cbgpPeer2RemoteAs']
    rawdata = snmp_bulkwalk(oids, hostname=args.H, community=args.C, version=2)
except (EasySNMPConnectionError, EasySNMPTimeoutError) as err:
    snmp_err(err)

data = defaultdict(dict)
for obj in rawdata:
    data[obj.oid_index][obj.oid] = obj

# We default to an OK status
status = STATE_OK
statusstr = ''

# Now loop over data, and check the states
peer_found = False
remote_as = ""
for index, peer in data.iteritems():
    peer_ip = snmp_oid_decode_ip(index)
    if peer_ip != args.p:
        continue
    peer_found = True
    peername = peer['cbgpPeer2RemoteIdentifier'].value
    admin_state = peer['cbgpPeer2AdminStatus'].value
    bgp_state = peer['cbgpPeer2State'].value
    last_error = peer['cbgpPeer2LastErrorTxt'].value
    remote_as = peer['cbgpPeer2RemoteAs'].value

    if not last_error.strip():
        last_error = 'None'

    if admin_state == 1:  # Down
        trigger_not_ok(STATE_WARN, "{}(AS{}) admin down".format(peername, remote_as))
        continue
    if bgp_state in [0, 1, 2, 3, 4, 5]:  # none/idle/connect/active/opensent/openconfirm
        trigger_not_ok(STATE_CRIT, "{}(AS{}) BGP session down".format(peername, remote_as))
        continue
    statusstr = last_error
if not peer_found:
    trigger_not_ok(STATE_CRIT, "BGP session for peer {} not found!".format(orig_args_p))

# All checks completed, exiting with the relevant message
if status == STATE_OK:
    statusstr = "OK: BGP session with {}(AS{}) established, last error: {}".format(orig_args_p, remote_as, statusstr)
elif status == STATE_WARN:
    statusstr = "WARNING:" + statusstr
elif status == STATE_CRIT:
    statusstr = "CRITICAL:" + statusstr
print statusstr
sys.exit(status)
