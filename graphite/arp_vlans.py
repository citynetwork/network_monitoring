#!/usr/bin/env python
#
# @descr    Output per-vlan ARP table size in graphite format
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import argparse
import os
import sys
from time import time
from socket import socket

sys.path.append(os.path.dirname('..'))

from lib.cnh_nm import my_snmp_walk, snmpresult_to_dict  # noqa


def send_metrics(name, value):
    global args
    sock = socket()
    sock.settimeout(5)
    sock.connect( (args.g, 2003) )
    sock.send("%s %d %d\n" % (name, value, int(time())))
    sock.close()


# Argument parsing
parser = argparse.ArgumentParser(description='Output per-vlan ARP table size in graphite format')
parser.add_argument('-C', metavar='<community>', required=True,
                    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Host to check')
parser.add_argument('-g', metavar='<host>', required=True,
                    help='Graphite host')
args = parser.parse_args()


rawdata = my_snmp_walk(args, 'IF-MIB::ifDescr')
data = snmpresult_to_dict(rawdata)

for if_index, if_data in data.iteritems():
    if if_data['ifDescr'].value.lower().startswith('vlan'):
        vlan_rawdata = my_snmp_walk(args, 'IP-MIB::ipNetToPhysicalType.{}.1'.format(if_index), True)
        vlan_data = snmpresult_to_dict(vlan_rawdata)
        cnt = 0
        for vl_index, vl_data in vlan_data.iteritems():
            if vl_data['ipNetToPhysicalType'].value == 'dynamic':
                cnt += 1
        send_metrics(
            "arp.{}.vlan.{}".format(args.H, if_data['ifDescr'].value.split(" ")[1]),
            cnt
        )
