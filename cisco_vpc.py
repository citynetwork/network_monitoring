#!/usr/bin/env python
#
# @descr    Checks VPC status for NXOS switches
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import argparse
import re
import sys
from lib.cnh_nm import STATE_OK, STATE_CRIT, STATE_WARN, STATE_UNKNOWN
from lib.cnh_nm import trigger_not_ok, check_if_ok, my_snmp_walk, my_snmp_get
from lib.cnh_nm import snmpresult_to_dict

# Argument parsing
parser = argparse.ArgumentParser(description='Check VPC status for NXOS switches')
parser.add_argument('-C', metavar='<community>', required=True,
                    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Host to check')
args = parser.parse_args()

# These oids are for the overall status
oids = [
    'CISCO-VPC-MIB::cVpcPeerKeepAliveStatus',
    'CISCO-VPC-MIB::cVpcPeerKeepAliveMsgSendStatus',
    'CISCO-VPC-MIB::cVpcPeerKeepAliveMsgRcvrStatus',
    'CISCO-VPC-MIB::cVpcPeerKeepAliveVrfName',
    'CISCO-VPC-MIB::cVpcRoleStatus',
    'CISCO-VPC-MIB::cVpcDualActiveDetectionStatus'
]
# These are for host-link status
oids_host_link_status = [
    'CISCO-VPC-MIB::cVpcStatusHostLinkIfIndex',
    'CISCO-VPC-MIB::cVpcStatusHostLinkStatus',
    'CISCO-VPC-MIB::cVpcStatusHostLinkConsistencyStatus',
    'CISCO-VPC-MIB::cVpcStatusHostLinkConsistencyDetail'
]
oid_t_ifmib_ifname = 'IF-MIB::ifName.{}'


status = STATE_OK
statusstr = ""


# Check VPC general status and the status of peer-links
rawdata = my_snmp_walk(args, oids)
if not rawdata:
    print "UNKNOWN: Switch does not implement Cisco VPC, or does not have it enabled."
    sys.exit(STATE_UNKNOWN)
data = snmpresult_to_dict(rawdata)
vpc_domain_ids = []
for vpc_domain in data:
    vpc_domain_ids.append(vpc_domain)
    vpc_data = data[vpc_domain]

    # 1 = primarySecondary, 2 = primary, 3 = secondaryPrimary, 4 = secondary, 5 = noneEstablished
    if int(vpc_data['cVpcRoleStatus'].value) == 5:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            'VPC Domain {} no peerlinks established'.format(vpc_domain))
        continue  # No point in checking further

    # 1 = true, 2 = false
    if int(vpc_data['cVpcDualActiveDetectionStatus'].value) == 1:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            'VPC Domain {} Dual active detected!'.format(vpc_domain))

    # 1 = disabled, 2 = alive, 3 = peerUnreachable, 4 = aliveButDomainIdDismatch, 5 = suspendedAsISSU
    # 6 = suspendedAsDestIPUnreachable, 7 = suspendedAsVRFUnusable, 8 = misconfigured
    vpc_pkstatus = int(vpc_data['cVpcPeerKeepAliveStatus'].value)
    if vpc_pkstatus != 2:
        vpc_pkerrors = {
            1: { 'state': STATE_WARN, 'txt': 'peer-link is disabled' },
            3: { 'state': STATE_CRIT, 'txt': 'peers are unreachable' },  # Will probably never be checked dueto cVpcRoleStatus above
            4: { 'state': STATE_CRIT, 'txt': 'peer domain ID mismatch' },
            5: { 'state': STATE_WARN, 'txt': 'peer-link suspended due to ongoing ISSU' },
            6: { 'state': STATE_CRIT, 'txt': 'peer-link suspended as destination IP unreachable' },
            7: { 'state': STATE_CRIT, 'txt': 'peer-link suspended as VRF () is unuable'.format(vpc_data['cVpcPeerKeepAliveVrfName'].value) },
            8: { 'state': STATE_CRIT, 'txt': 'peer-link is misconfigured' }
        }
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            vpc_pkerrors[vpc_pkstatus]['state'],
            "VPC Domain {} {}".format(vpc_domain, vpc_pkerrors[vpc_pkstatus]['txt'])
        )

    # 1 = success, 2 = failure
    if int(vpc_data['cVpcPeerKeepAliveMsgSendStatus'].value) != 1:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            'VPC Domain {} Peer-Link MsgSendStatus failure'.format(vpc_domain)
        )

    # 1 = success, 2 = failure
    if int(vpc_data['cVpcPeerKeepAliveMsgRcvrStatus'].value) != 1:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            'VPC Domain {} Peer-Link MsgRcvrStatus failure'.format(vpc_domain)
        )


# Check VPC HostLink status
rawdata = my_snmp_walk(args, oids_host_link_status)
regex = re.compile(r"^[0-9]+\.")
temp = []
for rd in rawdata:  # Filter out the VPC Domain, doesn't matter here
    rd.oid_index = regex.sub('', rd.oid_index)
    temp.append(rd)
data = snmpresult_to_dict(rawdata)
for host_link in data:
    hl_data = data[host_link]
    snmp_ifname = my_snmp_get(args, oid_t_ifmib_ifname.format(hl_data['cVpcStatusHostLinkIfIndex'].value))

    # 1 = down, 2 = downStar (forwarding via VPC host-link), 3 = up
    hl_status = int(hl_data['cVpcStatusHostLinkStatus'].value)
    if hl_status == 1:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            'Host-link {} down'.format(snmp_ifname.value)
        )
    if hl_status == 2:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_WARN,
            'Host-link {} down but forwarding via VPC peer-link'.format(snmp_ifname.value)
        )

    # 1 = success, 2 = failed, 3 = notApplicable
    if int(hl_data['cVpcStatusHostLinkConsistencyStatus'].value) == 2:
        consistency_detail = hl_data['cVpcStatusHostLinkConsistencyDetail'].value
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            'Host-link {} inconsistent between VPC peers ({})'.format(snmp_ifname.value, consistency_detail)
        )

check_if_ok(status, statusstr)

print "OK: VPC Status, Peer-Link status is OK"
sys.exit(STATE_OK)
