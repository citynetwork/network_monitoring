#!/usr/bin/env python
#
# @descr    Checks OSPF session status on NX-OS (VRF-aware, requires SNMPv3)
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
import argparse
from lib.cnh_nm import STATE_OK, STATE_CRIT
from lib.cnh_nm import snmpresult_to_dict, my_snmp_walk_v3, snmp_translate_oid2string


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
parser.add_argument('-p', metavar='<peer>', required=True,
                    help='Neighbor to check (peer IP)')
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

    # Iterating the neighbors of the current context
    raw_neighbors = my_snmp_walk_v3(args, nei_oids, snmp_context)
    neighbors = snmpresult_to_dict(raw_neighbors)
    for nei_index, nei_data in neighbors.iteritems():
        nei_ip = nei_data['ospfNbrIpAddr'].value
        nei_rtrid = nei_data['ospfNbrRtrId'].value
        nei_state = int(nei_data['ospfNbrState'].value)

        if nei_ip == args.p:
            if nei_state in ospf_ok_states:
                print "OK: Neighbor {} RtrID {} in state full/two-way.".format(args.p, nei_rtrid)
                sys.exit(STATE_OK)
            else:
                print "CRITICAL: Neighbor {} RtrID {} in state {}!".format(args.p, nei_rtrid, ospf_crit_statemapper[nei_state])
                sys.exit(STATE_CRIT)


print "CRITICAL: Neighbor {} not found!".format(args.p)
sys.exit(STATE_CRIT)
