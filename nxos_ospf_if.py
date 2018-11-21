#!/usr/bin/env python
#
# @descr    Checks OSPF session status on NX-OS (VRF-aware, requires SNMPv3)
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
import argparse
from ipaddress import ip_address, ip_network
from lib.cnh_nm import STATE_OK, STATE_CRIT
from lib.cnh_nm import snmpresult_to_dict, my_snmp_walk_v3, snmp_translate_oid2string, my_snmp_get_v3


# OSPF states:
# 1=down, 2=attempt, 3=init, 4=twoway
# 5=exchangestart, 6=exchange, 7=loading
# 8=full
ospf_ok_states = [4, 8]
ospf_crit_statemapper = {
    1: 'down',
    2: 'attempt',
    3: 'init',
    5: 'exchangestart',
    6: 'exchange',
    7: 'loading'
}


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


# OSPF oids
nei_oids = [
    'OSPF-MIB::ospfNbrIpAddr',
    'OSPF-MIB::ospfNbrRtrId',
    'OSPF-MIB::ospfNbrState'
]


# Iterating all SNMPv3 contexts that have a configured VRF mapping
rawdata = my_snmp_walk_v3(args, 'CISCO-CONTEXT-MAPPING-MIB::cContextMappingVrfName')
data = snmpresult_to_dict(rawdata)
for index, mapping in data.iteritems():
    if not mapping['cContextMappingVrfName'].value:
        continue  # This is an auto-created context which likely doesn't contain anything useful
    snmp_context = snmp_translate_oid2string(index)
    snmp_vrf = mapping['cContextMappingVrfName'].value

    # Get routing table of the current context
    raw_ipforward = my_snmp_walk_v3(args, 'IP-FORWARD-MIB::inetCidrRouteIfIndex.1.4', snmp_context)
    snmp_ipforward = snmpresult_to_dict(raw_ipforward)
    routingtable = []
    for ipf_index, ipf_data in snmp_ipforward.iteritems():
        ipf_index_parts = ipf_index.split(".")
        ipf_ip = ".".join(ipf_index_parts[2:6])
        ipf_cidr = ipf_index_parts[6:7].pop()
        routingtable.append({'ip': ipf_ip, 'cidr': ipf_cidr, 'ifindex': ipf_data['inetCidrRouteIfIndex'].value})

    # Iterating the neighbors of the current context
    raw_neighbors = my_snmp_walk_v3(args, nei_oids, snmp_context)
    neighbors = snmpresult_to_dict(raw_neighbors)
    for nei_index, nei_data in neighbors.iteritems():
        nei_ip = nei_data['ospfNbrIpAddr'].value
        nei_rtrid = nei_data['ospfNbrRtrId'].value
        nei_state = int(nei_data['ospfNbrState'].value)

        nei_ifindex = None
        last_route_size = None
        for route in routingtable:
            if ip_address(nei_ip) in ip_network(u"{}/{}".format(route['ip'], route['cidr'])):
                if not last_route_size:
                    last_route_size = route['cidr']
                    nei_ifindex = route['ifindex']
                elif int(last_route_size) < int(route['cidr']):
                    last_route_size = route['cidr']
                    nei_ifindex = route['ifindex']
        nei_ifname = my_snmp_get_v3(args, 'IF-MIB::ifDescr.{}'.format(nei_ifindex), snmp_context).value
        if args.I.lower() == nei_ifname.lower():
            if nei_state in ospf_ok_states:
                print "OK: Found neighbor ({}) on {} in state full/two-way.".format(nei_rtrid, args.I)
                sys.exit(STATE_OK)
            else:
                print "CRITICAL: Neighbor ({}) on {} in state {}!".format(nei_rtrid, args.I, ospf_crit_statemapper[nei_state])
                sys.exit(STATE_CRIT)


print "CRITICAL: No neighbor found on interface {}!".format(args.I)
sys.exit(STATE_CRIT)
