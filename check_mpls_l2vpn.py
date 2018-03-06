#!/usr/bin/env python

import sys
import argparse
from collections import defaultdict
from easysnmp import snmp_get, snmp_bulkwalk, EasySNMPConnectionError, EasySNMPTimeoutError

# Nagios states
STATE_OK = 0
STATE_WARN = 1
STATE_CRIT = 2
STATE_UNKNOWN = 3

# Defaults
vpls_vcid_range = xrange(1,4096)
cpw_oper_status_mapping = {
        "1": "up",
        "2": "down",
        "3": "testing",
        "4": "dormant",
        "5": "notPresent",
        "6": "lowerLayerDown"
        }

# Argument parsing
parser = argparse.ArgumentParser(description='Check MPLS L2VPN status')
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


# Get all VC's
try:
    oids = [
            'CISCO-IETF-PW-MIB::cpwVcPsnType',
            #'CISCO-IETF-PW-MIB::cpwVcPeerAddr',
            #'CISCO-IETF-PW-MIB::cpwVcPeerAddrType',
            'CISCO-IETF-PW-MIB::cpwVcID',
            'CISCO-IETF-PW-MIB::cpwVcLocalIfMtu',
            'CISCO-IETF-PW-MIB::cpwVcRemoteIfMtu',
            'CISCO-IETF-PW-MIB::cpwVcInboundOperStatus',
            'CISCO-IETF-PW-MIB::cpwVcOutboundOperStatus',
            'CISCO-IETF-PW-MIB::cpwVcAdminStatus',
            'CISCO-IETF-PW-MIB::cpwVcOperStatus',
            #'CISCO-IETF-PW-MIB::cpwVcName', # These two only used for EoMPLS
            #'CISCO-IETF-PW-MIB::cpwVcDescr'
    ]
    rawdata = snmp_bulkwalk(oids, hostname=args.H, community=args.C, version=2)
except (EasySNMPConnectionError, EasySNMPTimeoutError) as err:
    snmp_err(err)

data = defaultdict(dict)
for obj in rawdata:
    data[obj.oid_index][obj.oid] = obj

# We default to an OK status
status = STATE_OK
statusstr = ''

# Now loop over data, and perform checks
num_vc = 0
for index, vc in data.iteritems():
    if int(vc['cpwVcID'].value) in vpls_vcid_range:
        mpls_vc_type = 'VPLS'
    else:
        mpls_vc_type = 'EoMPLS'
    num_vc += 1

    # Check VC status
    if vc['cpwVcAdminStatus'].value == '1':
        if vc['cpwVcOperStatus'].value != '1':
            trigger_not_ok(STATE_CRIT, "OperStatus {} on {} VCID {}".format(
                cpw_oper_status_mapping[vc['cpwVcOperStatus'].value],
                mpls_vc_type,
                vc['cpwVcID'].value)
            )
            continue
        if vc['cpwVcInboundOperStatus'].value != '1':
            trigger_not_ok(STATE_CRIT, "InboundOperStatus {} on {} VCID {}".format(
                cpw_oper_status_mapping[vc['cpwVcInboundOperStatus'].value],
                mpls_vc_type,
                vc['cpwVcID'].value)
            )
        if vc['cpwVcOutboundOperStatus'].value != '1':
            trigger_not_ok(STATE_CRIT, "OutboundOperStatus {} on {} VCID {}".format(
                cpw_oper_status_mapping[vc['cpwVcOutboundOperStatus'].value],
                mpls_vc_type,
                vc['cpwVcID'].value)
            )
        if status == STATE_CRIT: # No point in checking more minor issues if OperStatus isn't up
            continue

    else:
        trigger_not_ok(STATE_WARN, "Admin shutdown on {} VCID {}".format(
            mpls_vc_type,
            vc['cpwVcId'].value)
        )
        continue

    # Check for MTU mismatches
    if vc['cpwVcLocalIfMtu'].value != vc['cpwVcRemoteIfMtu'].value:
        trigger_not_ok(STATE_CRIT, "MTU mismatch (local={}, remote={}) on {} VCID {}".format(
            vc['cpwVcLocalIfMtu'].value,
            vc['cpwVcRemoteIfMtu'].value,
            mpls_vc_type,
            vc['cpwVcId'].value)
        )

# All checks completed, exiting with the relevant message
if status == STATE_OK:
    statusstr = "OK: All ({}) VPLS/EoMPLS VC's are up and running".format(num_vc)
elif status == STATE_WARN:
    statusstr = "WARNING:" + statusstr
elif status == STATE_CRIT:
    statusstr = "CRITICAL:" + statusstr
print statusstr
sys.exit(status)
