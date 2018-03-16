#!/usr/bin/env python
#
# @descr    Checks LAG status of FTOS devices
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
import argparse
from lib.cnh_nm import STATE_OK, STATE_WARN, STATE_CRIT
from lib.cnh_nm import snmpresult_to_dict, my_snmp_walk, my_snmp_get
from lib.cnh_nm import trigger_not_ok, check_if_ok


# Argument parsing
parser = argparse.ArgumentParser(description='Check LAG ports status')
parser.add_argument('-C', metavar='<community>', required=True,
                    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Host to check')
args = parser.parse_args()


def ftos_parse_lag_active_ports(portlist):
    portlist = str(portlist)
    portlist = portlist.replace('Te ', 'Te')
    portlist = portlist.replace('fo ', 'fo')
    portlist = portlist.replace('Gi ', 'Gi')
    portlist = portlist.split(' ')
    portlist = filter(None, portlist)
    return len(portlist)


# Get all LAG ports
oids = [
        'DELL-NETWORKING-LINK-AGGREGATION-MIB::dot3aAggCfgNumPorts',
        'DELL-NETWORKING-LINK-AGGREGATION-MIB::dot3aAggCfgOperStatus',
        'DELL-NETWORKING-LINK-AGGREGATION-MIB::dot3aAggCfgIfIndex',
        'DELL-NETWORKING-LINK-AGGREGATION-MIB::dot3aAggCfgPortListString'
]
rawdata = my_snmp_walk(args, oids)
data = snmpresult_to_dict(rawdata)


# Loop through them and check num ports vs num active ports and operational status
status = STATE_OK
statusstr = ""
for index, lag in data.iteritems():
    lag_name = my_snmp_get(args, 'IF-MIB::ifDescr.{}'.format(lag['dot3aAggCfgIfIndex'].value)).value

    num_ports = int(str(lag['dot3aAggCfgNumPorts'].value))
    if num_ports < 1:
        status, statusstr = trigger_not_ok(
                status,
                statusstr,
                STATE_WARN,
                '{} has no configured members'.format(lag_name))
        continue

    active_ports = ftos_parse_lag_active_ports(lag['dot3aAggCfgPortListString'].value)
    if active_ports < num_ports and active_ports > 1:
        status, statusstr = trigger_not_ok(
                status,
                statusstr,
                STATE_WARN,
                '{}: Only {} ports of configured {} is up'.format(lag_name, active_ports, num_ports))
    elif active_ports < 1:
        status, statusstr = trigger_not_ok(
                status,
                statusstr,
                STATE_CRIT,
                '{}: All ports down'.format(lag_name))
        continue

    oper_status = int(str(lag['dot3aAggCfgOperStatus'].value))
    if oper_status == 2:  # 1=up, 2=down
        status, statusstr = trigger_not_ok(
                status,
                statusstr,
                STATE_CRIT,
                '{} is down'.format(lag_name))


# All done, check status and exit
check_if_ok(status, statusstr)

print "OK: All port-channels is ok"
sys.exit(STATE_OK)
