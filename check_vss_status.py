#!/usr/bin/env python
#
# @descr    Checks VSS status of Cisco IOS devices
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
import argparse
from time import time
from lib.cnh_nm import STATE_OK, STATE_CRIT, STATE_WARN, STATE_UNKNOWN
from lib.cnh_nm import my_snmp_get, my_snmp_walk, snmpresult_to_dict
from lib.cnh_nm import parse_snmp_datetime, strtime_to_timestamp
from lib.cnh_nm import trigger_not_ok, check_if_ok


# Defaults
vss_uptime_crit = 300
vss_uptime_warn = 1800
vsl_statechange_crit = 300
vsl_statechange_warn = 1800


# Argument parsing
parser = argparse.ArgumentParser(description='Check VSS cluster status')
parser.add_argument('-C', metavar='<community>', required=True,
                    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Host to check')
args = parser.parse_args()


# Get all VSS info and check whether the device is actually capable of VSS and have it enabled
oids_chassis = [
    'CISCO-VIRTUAL-SWITCH-MIB::cvsChassisRole',  # 1=standalone, 2=active, 3=standby
    'CISCO-VIRTUAL-SWITCH-MIB::cvsChassisUpTime'
]
oids_VSL = [
    'CISCO-VIRTUAL-SWITCH-MIB::cvsVSLConnectOperStatus',  # 1=up, 2=down
    'CISCO-VIRTUAL-SWITCH-MIB::cvsVSLLastConnectionStateChange',
    'CISCO-VIRTUAL-SWITCH-MIB::cvsVSLConfiguredPortCount',
    'CISCO-VIRTUAL-SWITCH-MIB::cvsVSLOperationalPortCount'
]
oids_switch = [
    'CISCO-VIRTUAL-SWITCH-MIB::cvsSwitchCapability.0',  # 0=standalone, 1=core(part of vss cluster)
    'CISCO-VIRTUAL-SWITCH-MIB::cvsSwitchMode.0'  # 1=standalone, 2=multiNode(VSS)
]
cvsSwitchCapability = my_snmp_get(args, oids_switch[0])
cvsSwitchMode = my_snmp_get(args, oids_switch[1])
if cvsSwitchCapability.value != u'\xc0' and cvsSwitchCapability.value != u'\x80':
    print "UNKNOWN: Switch is not VSS capable!"
    sys.exit(STATE_UNKNOWN)
if cvsSwitchMode.value != u'2':
    print "OK: Switch is VSS capable, but isn't running in VSS mode"
    sys.exit(STATE_OK)
rawdata_chassis = my_snmp_walk(args, oids_chassis)
rawdata_VSL = my_snmp_walk(args, oids_VSL)


# Sort the walked data into a nicer format
chassis = snmpresult_to_dict(rawdata_chassis)
VSL = snmpresult_to_dict(rawdata_VSL)


# A valid and healthy VSS cluster is always 2 members
if len(chassis) < 2:
    print "CRITICAL: Only one chassis found, possible cluster member outage!"
    sys.exit(STATE_CRIT)

chassis1 = chassis[list(chassis.keys())[0]]
chassis2 = chassis[list(chassis.keys())[1]]


# We want to catch: standby/standby active/active and whether either are in standalone
# Critting immediately here as all of this are much more critical than all other checks
if chassis1['cvsChassisRole'].value == chassis2['cvsChassisRole'].value:
    if chassis1['cvsChassisRole'].value == u'1':
        print "CRITICAL: Both VSS members are in standalone role? Shouldn't be possible.."
        sys.exit(STATE_CRIT)
    if chassis1['cvsChassisRole'].value == u'2':
        print "CRITICAL: Both VSS members are in active role!"
        sys.exit(STATE_CRIT)
    if chassis1['cvsChassisRole'].value == u'3':
        print "CRITICAL: Both VSS members are in standby role!"
        sys.exit(STATE_CRIT)
if chassis1['cvsChassisRole'].value == u'1':
    print "CRITICAL: VSS Chassis 1 is in standalone mode!"
    sys.exit(STATE_CRIT)
if chassis2['cvsChassisRole'].value == u'1':
    print "CRITICAL: VSS Chassis 2 is in standalone mode!"
    sys.exit(STATE_CRIT)


# Chassis uptime is an indicator of recent VSS member failure
status = STATE_OK
statusstr = ""
chassis1_tt = float(int(str(chassis1['cvsChassisUpTime'].value))) * 0.01
chassis2_tt = float(int(str(chassis1['cvsChassisUpTime'].value))) * 0.01
if chassis1_tt < vss_uptime_warn:
    chassis1_str = "Chassis 1 uptime {} seconds".format(int(chassis1_tt))
    if chassis1_tt < vss_uptime_crit:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            chassis1_str)
    else:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_WARN,
            chassis1_str)
if chassis2_tt < vss_uptime_warn:
    chassis2_str = "Chassis 2 uptime {} seconds".format(int(chassis2_tt))
    if chassis2_tt < vss_uptime_crit:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            chassis2_str)
    else:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_WARN,
            chassis2_str)
check_if_ok(status, statusstr)


# Getting VSL info per chassis
chassis1_vsl = VSL[list(VSL.keys())[0]]
chassis2_vsl = VSL[list(VSL.keys())[1]]


# Operational status on VSL connection
status = STATE_OK
statusstr = ""
if chassis1_vsl['cvsVSLConnectOperStatus'].value != u'1':
    status, statusstr = trigger_not_ok(
        status,
        statusstr,
        STATE_CRIT,
        "Chassis 1 VSL ports down")
if chassis2_vsl['cvsVSLConnectOperStatus'].value != u'1':
    status, statusstr = trigger_not_ok(
        status,
        statusstr,
        STATE_CRIT,
        "Chassis 2 VSL ports down")
check_if_ok(status, statusstr)


# Checking that all VSL ports is operational
status = STATE_OK
statusstr = ""
if chassis1_vsl['cvsVSLConfiguredPortCount'].value != chassis1_vsl['cvsVSLOperationalPortCount'].value:
    ports_down = int(chassis1_vsl['cvsVSLConfiguredPortCount'].value) - int(chassis1_vsl['cvsVSLOperationalPortCount'].value)
    status, statusstr = trigger_not_ok(
        status,
        statusstr,
        STATE_CRIT,
        "{} VSL ports down on Chassis 1".format(ports_down))
if chassis2_vsl['cvsVSLConfiguredPortCount'].value != chassis2_vsl['cvsVSLOperationalPortCount'].value:
    ports_down = int(chassis2_vsl['cvsVSLConfiguredPortCount'].value) - int(chassis2_vsl['cvsVSLOperationalPortCount'].value)
    status, statusstr = trigger_not_ok(
        status,
        statusstr,
        STATE_CRIT,
        "{} VSL ports down on Chassis 1".format(ports_down))
check_if_ok(status, statusstr)


# Check last VSL state change
status = STATE_OK
statusstr = ""
chassis1_dt = parse_snmp_datetime(chassis1_vsl['cvsVSLLastConnectionStateChange'].value)
chassis2_dt = parse_snmp_datetime(chassis1_vsl['cvsVSLLastConnectionStateChange'].value)
chassis1_ts = strtime_to_timestamp(chassis1_dt)
chassis2_ts = strtime_to_timestamp(chassis2_dt)
cur_time = int(time())

if (cur_time - chassis1_ts) < vsl_statechange_warn:
    chassis1_str = "Chassis 1 VSL statechange {} seconds ago".format(cur_time - chassis1_ts)
    if (cur_time - chassis1_ts) < vsl_statechange_crit:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            chassis1_str)
    else:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_WARN,
            chassis1_str)
if (cur_time - chassis2_ts) < vsl_statechange_warn:
    chassis2_str = "Chassis 2 VSL statechange {} seconds ago".format(cur_time - chassis2_ts)
    if (cur_time - chassis2_ts) < vsl_statechange_crit:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            chassis2_str)
    else:
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_WARN,
            chassis2_str)


# Check status and exit accordingly
check_if_ok(status, statusstr)

print "OK: VSS and VSL status is healthy"
sys.exit(STATE_OK)
