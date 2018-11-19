#!/usr/bin/env python
#
# @descr    Checks MPLS L2VPN status of Cisco IOS devices
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
import argparse
from lib.cnh_nm import STATE_OK, STATE_CRIT, STATE_WARN
from lib.cnh_nm import my_snmp_walk, snmpresult_to_dict
from lib.cnh_nm import trigger_not_ok, check_if_ok


# Defaults
vpls_vcid_range = xrange(1, 4096)
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


# Get all VC's
oids = [
    'CISCO-IETF-PW-MIB::cpwVcPsnType',
    'CISCO-IETF-PW-MIB::cpwVcID',
    'CISCO-IETF-PW-MIB::cpwVcLocalIfMtu',
    'CISCO-IETF-PW-MIB::cpwVcRemoteIfMtu',
    'CISCO-IETF-PW-MIB::cpwVcInboundOperStatus',
    'CISCO-IETF-PW-MIB::cpwVcOutboundOperStatus',
    'CISCO-IETF-PW-MIB::cpwVcAdminStatus',
    'CISCO-IETF-PW-MIB::cpwVcOperStatus'
]
rawdata = my_snmp_walk(args, oids)
data = snmpresult_to_dict(rawdata)


# Now loop over data, and perform checks
status = STATE_OK
statusstr = ''
num_vc = 0
for index, vc in data.iteritems():
    if int(str(vc['cpwVcID'].value)) in vpls_vcid_range:
        mpls_vc_type = 'VPLS'
    else:
        mpls_vc_type = 'EoMPLS'
    num_vc += 1

    # Check VC status
    if vc['cpwVcAdminStatus'].value == u'1':
        if vc['cpwVcOperStatus'].value != u'1':
            status, statusstr = trigger_not_ok(
                status,
                statusstr,
                STATE_CRIT,
                "OperStatus {} on {} VCID {}".format(
                    cpw_oper_status_mapping[vc['cpwVcOperStatus'].value],
                    mpls_vc_type,
                    vc['cpwVcID'].value)
            )
            continue
        if vc['cpwVcInboundOperStatus'].value != '1':
            status, statusstr = trigger_not_ok(
                status,
                statusstr,
                STATE_CRIT,
                "InboundOperStatus {} on {} VCID {}".format(
                    cpw_oper_status_mapping[vc['cpwVcInboundOperStatus'].value],
                    mpls_vc_type,
                    vc['cpwVcID'].value)
            )
        if vc['cpwVcOutboundOperStatus'].value != '1':
            status, statusstr = trigger_not_ok(
                status,
                statusstr,
                STATE_CRIT,
                "OutboundOperStatus {} on {} VCID {}".format(
                    cpw_oper_status_mapping[vc['cpwVcOutboundOperStatus'].value],
                    mpls_vc_type,
                    vc['cpwVcID'].value)
            )
        if status == STATE_CRIT:  # No point in checking more minor issues if OperStatus isn't up
            continue

    else:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_WARN,
            "Admin shutdown on {} VCID {}".format(
                mpls_vc_type,
                vc['cpwVcId'].value)
        )
        continue

    # Check for MTU mismatches
    if vc['cpwVcLocalIfMtu'].value != vc['cpwVcRemoteIfMtu'].value:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            "MTU mismatch (local={}, remote={}) on {} VCID {}".format(
                vc['cpwVcLocalIfMtu'].value,
                vc['cpwVcRemoteIfMtu'].value,
                mpls_vc_type,
                vc['cpwVcId'].value
            )
        )

# All checks completed, exiting with the relevant message
check_if_ok(status, statusstr)

print "OK: All ({}) VPLS/EoMPLS VC's are up and running".format(num_vc)
sys.exit(STATE_OK)
