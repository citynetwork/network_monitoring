#!/usr/bin/env python
#
# @descr    Checks that *someone* didn't forget to save the configuration
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
import argparse
from lib.cnh_nm import STATE_OK, STATE_CRIT, STATE_WARN
from lib.cnh_nm import my_snmp_walk, snmpresult_to_dict
from lib.cnh_nm import check_if_ok, my_snmp_get


# Argument parsing
parser = argparse.ArgumentParser(description='Checks that someone didnt forget to save the configuration')
parser.add_argument('-C', metavar='<community>', required=True,
                    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Host to check')
args = parser.parse_args()


# Get data
oids = [
    'CISCO-CONFIG-MAN-MIB::ccmHistoryRunningLastChanged',
    'CISCO-CONFIG-MAN-MIB::ccmHistoryStartupLastChanged',
    'CISCO-CONFIG-MAN-MIB::ccmCTIDWhoChanged'
]
rawdata = my_snmp_walk(args, oids)
data = snmpresult_to_dict(rawdata)['0']
uptime = my_snmp_get(args, 'SNMPv2-MIB::sysUpTime.0')


# Check the data
status = STATE_OK
statusstr = ''
try:
    culprit = data['ccmCTIDWhoChanged'].value
except KeyError:
    culprit = 'unknown'  # IOS-XR
if float(data['ccmHistoryStartupLastChanged'].value) < float(data['ccmHistoryRunningLastChanged'].value):
    status = STATE_WARN
    statusstr = "Either {} is still doing changes or {} just forgot to save the config.".format(culprit, culprit)
    if ((float(uptime.value) - float(data['ccmHistoryRunningLastChanged'].value)) / 100) > (3600 * 3):
        status = STATE_CRIT
        statusstr = "Okay, {} has definately forgotten to save the configuration!".format(culprit)


# All checks completed, exiting with the relevant message
check_if_ok(status, statusstr)

print "OK: Configuration was properly saved after editing, last touched by {}".format(culprit)
sys.exit(STATE_OK)
