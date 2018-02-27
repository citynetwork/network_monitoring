#!/usr/bin/env python

import argparse
import ipaddress
import sys
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
parser.add_argument('-p', metavar='<peer>', required=True,
                    help='Peer to check')
args = parser.parse_args()

# Expand IPv6
if ':' in args.p:
    addr = ipaddress.ip_address(args.p)
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
        return ip_decoded.lower()


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

# Now loop over data, and check the states
for index, peer in data.iteritems():
    peer_ip = snmp_oid_decode_ip(index)
    if peer_ip != args.p:
        continue
    peername = peer['cbgpPeer2RemoteIdentifier'].value
    admin_state = peer['cbgpPeer2AdminStatus'].value
    bgp_state = peer['cbgpPeer2State'].value
    last_error = peer['cbgpPeer2LastErrorTxt'].value
    if not last_error.strip():
        last_error = 'None'

    if admin_state == 1:  # Down
        trigger_not_ok(STATE_WARN, "{} admin down".format(peername))
        continue
    if bgp_state in [0, 1, 2, 3, 4, 5]:  # none/idle/connect/active/opensent/openconfirm
        trigger_not_ok(STATE_CRIT, "{} BGP session down".format(peername))
        continue
    statusstr = last_error

# All checks completed, exiting with the relevant message
if status == STATE_OK:
    statusstr = "OK: BGP session with {} established, last error: ".format(args.p, statusstr)
elif status == STATE_WARN:
    statusstr = "WARNING:" + statusstr
elif status == STATE_CRIT:
    statusstr = "CRITICAL:" + statusstr
print statusstr
sys.exit(status)
