#!/usr/bin/env python
#
# @descr    Retrieves metrics about QoS on Cisco IOS routers
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import argparse
import os
import sys
from time import time
from socket import socket

sys.path.append(os.path.dirname('..'))

from lib.cnh_nm import my_snmp_walk, my_snmp_get  # noqa


def send_metrics(name, value):
    global args
    sock = socket()
    sock.settimeout(5)
    sock.connect( (args.g, 2003) )
    sock.send("%s %d %d\n" % (name, value, int(time())))
    sock.close()


# Argument parsing
parser = argparse.ArgumentParser(description='Retrieves metrics about QoS on Cisco IOS routers')
parser.add_argument('-C', metavar='<community>', required=True,
                    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Host to check')
parser.add_argument('-g', metavar='<host>', required=True,
                    help='Graphite host')
args = parser.parse_args()

bulk_oids = [
    'CISCO-CLASS-BASED-QOS-MIB::cbQosCMName',
    'CISCO-CLASS-BASED-QOS-MIB::cbQosPolicyMapName',
    'CISCO-CLASS-BASED-QOS-MIB::cbQosIfIndex',
    'CISCO-CLASS-BASED-QOS-MIB::cbQosCMDropByte',
    'CISCO-CLASS-BASED-QOS-MIB::cbQosCMPrePolicyByte',
    'CISCO-CLASS-BASED-QOS-MIB::cbQosCMPostPolicyByte'
]
QOS_IFTYPE_OID = 'CISCO-CLASS-BASED-QOS-MIB::cbQosIfType'
QOS_CONFIG_INDEX_OID = 'CISCO-CLASS-BASED-QOS-MIB::cbQosConfigIndex'


rawdata = my_snmp_walk(args, bulk_oids)
policy_maps = dict()  # policy-map index -> policy-map name
class_maps = dict()  # class-map index -> class-map name
qos_interfaces = list()  # qos ifIndex -> IF-MIB ifIndex
cmstats = dict()  # <interface>: {<qos_ifindex>: {<statsname>: <value>} }
qos_config_index_mapping = dict()

# Parse the first bulkwalk into the above datastructures
for snmpobj in rawdata:
    if snmpobj.oid == 'cbQosCMName':
        class_maps[snmpobj.oid_index] = snmpobj.value
    elif snmpobj.oid == 'cbQosPolicyMapName':
        policy_maps[snmpobj.oid_index] = snmpobj.value
    elif snmpobj.oid == 'cbQosIfIndex':
        iftype = my_snmp_get(args, "{}.{}".format(QOS_IFTYPE_OID, snmpobj.oid_index))
        if iftype.value != '5':  # control-plane auto-copp
            policy_map_id = my_snmp_get(args, "{}.{}.{}".format(QOS_CONFIG_INDEX_OID, snmpobj.oid_index, snmpobj.oid_index))
            qos_interfaces.append({
                'qos_ifindex': snmpobj.oid_index,
                'ifmib_ifindex': snmpobj.value,
                'policy_map_id': policy_map_id.value
            })
            config_indexes = my_snmp_walk(args, "{}.{}".format(QOS_CONFIG_INDEX_OID, snmpobj.oid_index))
            for ci in config_indexes:
                index_parts = ci.oid_index.split(".")
                if index_parts[0] not in qos_config_index_mapping:
                    qos_config_index_mapping[index_parts[0]] = dict()
                qos_config_index_mapping[index_parts[0]][index_parts[1]] = ci.value
    elif snmpobj.oid.startswith('cbQosCM') and snmpobj.oid != 'cbQosCMName':
        index_parts = snmpobj.oid_index.split(".")
        iface = index_parts[0]
        qos_ifindex = index_parts[1]
        if iface not in cmstats:
            cmstats[iface] = dict()
        if qos_ifindex not in cmstats[iface]:
            cmstats[iface][qos_ifindex] = dict()
        if snmpobj.oid not in cmstats[iface][qos_ifindex]:
            cmstats[iface][qos_ifindex][snmpobj.oid] = snmpobj.value


# Generating graphite output
for qos_interface in qos_interfaces:
    ifmib_name = my_snmp_get(args, 'IF-MIB::ifDescr.{}'.format(qos_interface['ifmib_ifindex']))
    policy_map_name = policy_maps[qos_interface['policy_map_id']]
    for qcim_index, qcim_value in qos_config_index_mapping[qos_interface['qos_ifindex']].iteritems():
        if qcim_value in class_maps:
            if qcim_index not in cmstats[qos_interface['qos_ifindex']]:
                continue  # class-default doesn't have any policy stats
            for statsname, statsvalue in cmstats[qos_interface['qos_ifindex']][qcim_index].iteritems():
                send_metrics(
                    "qos.{}.{}.{}.{}.{}".format(
                        args.H,  # hostname
                        ifmib_name.value,  # interface name
                        policy_map_name,  # policy-map name
                        class_maps[qcim_value],  # class-map name
                        statsname  # Key for the value
                    ),
                    int(statsvalue)  # The value
                )
            # If we later want to get per-police-statement data we will have to use qcim_index
            # and check cbQosParentObjectsIndex and walk the entries which has a corresponding
            # cbQosObjectsType set to INTEGER: police(7), then bulkwalk
            # cbQosPolice(Conformed|Violated|Exceeded)BitRate to get the data
