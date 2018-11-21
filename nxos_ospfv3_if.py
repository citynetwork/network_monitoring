#!/usr/bin/env python
#
# @descr    Checks OSPF session status on NX-OS (VRF-aware, requires SNMPv3)
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
import argparse
from lib.cnh_nm import STATE_OK, STATE_CRIT
from lib.cnh_nm import snmpresult_to_dict, my_snmp_walk_v3, snmp_translate_oid2string, my_snmp_get_v3, snmp_oid_decode_ip


ospf_ok_states = ['full', 'twoway']


# Argument parsing
parser = argparse.ArgumentParser(description='Check a OSPF sessions status on NX-OS (VRF-aware, requires SNMPv3)')
parser.add_argument('-l', metavar='<level>', required=True,
                    help='Security level')
parser.add_argument('-u', metavar='<username>', required=True,
                    help='Security username')
parser.add_argument('-a', metavar='<protocol>', required=True,
                    help='Auth protocol')
parser.add_argument('-A', metavar='<password>', required=True,
                    help='Auth password')
parser.add_argument('-x', metavar='<protocol>', required=True,
                    help='Privacy protocol')
parser.add_argument('-X', metavar='<password>', required=True,
                    help='Privacy password')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Host to check')
parser.add_argument('-I', metavar='<interface>', required=True,
                    help='Interface to check')
args = parser.parse_args()


# Iterating all SNMPv3 contexts that have a configured VRF mapping
rawdata = my_snmp_walk_v3(args, 'CISCO-CONTEXT-MAPPING-MIB::cContextMappingVrfName')
data = snmpresult_to_dict(rawdata)
for index, mapping in data.iteritems():
    if not mapping['cContextMappingVrfName'].value:
        continue  # This is an auto-created context which likely doesn't contain anything useful
    snmp_context = snmp_translate_oid2string(index)
    snmp_vrf = mapping['cContextMappingVrfName'].value

    # Get NDP table (IPv6 equivalent of ARP) - actually we get both since AF is the OID after ifIndex.....
    raw_ndp = my_snmp_walk_v3(args, 'IP-MIB::ipNetToPhysicalPhysAddress', snmp_context, True)
    snmp_ndp = snmpresult_to_dict(raw_ndp)
    v6addr_2_ifindex = {}
    for ndp_index, ndp_data in snmp_ndp.iteritems():
        ndp_ifindex = ndp_index.split(".")[0]
        if ".2.16." in ndp_index:
            v6_addr = snmp_oid_decode_ip(".".join(ndp_index.split(".")[1:]))
            v6addr_2_ifindex[v6_addr] = ndp_ifindex

    # Iterating the neighbors of the current context
    raw_neighbors = my_snmp_walk_v3(args, ['OSPFV3-MIB::ospfv3NbrState', 'OSPFV3-MIB::ospfv3NbrAddress'], snmp_context, True)
    neighbors = snmpresult_to_dict(raw_neighbors)
    for nei_index, nei_data in neighbors.iteritems():
        nei_state = nei_data['ospfv3NbrState'].value
        nei_ip_parts = nei_data['ospfv3NbrAddress'].value.strip('"').strip().split(" ")
        nei_ip = ""
        i = 1
        for part in nei_ip_parts:
            nei_ip += part
            if i % 2 == 0:
                nei_ip += ':'
            i += 1
        nei_ip = nei_ip.rstrip(":").lower()
        nei_ifindex = v6addr_2_ifindex[nei_ip]
        nei_ifname = my_snmp_get_v3(args, 'IF-MIB::ifDescr.{}'.format(nei_ifindex), snmp_context).value
        if args.I.lower() == nei_ifname.lower():
            if nei_state in ospf_ok_states:
                print "OK: Found neighbor ({}) on {} in state full/two-way.".format(nei_ip, args.I)
                sys.exit(STATE_OK)
            else:
                print "CRITICAL: Neighbor ({}) on {} in state {}!".format(nei_ip, args.I, nei_state)
                sys.exit(STATE_CRIT)


print "CRITICAL: No neighbor found on interface {}!".format(args.I)
sys.exit(STATE_CRIT)
