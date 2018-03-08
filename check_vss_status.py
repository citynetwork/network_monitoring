#!/usr/bin/env python

import sys
import argparse
from collections import defaultdict
from easysnmp import snmp_get, snmp_bulkwalk, EasySNMPConnectionError, EasySNMPTimeoutError
from time import time, mktime
from dateutil.parser import parse
from struct import unpack

# Nagios states
STATE_OK = 0
STATE_WARN = 1
STATE_CRIT = 2
STATE_UNKNOWN = 3

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


# Handle (or rather not handle) SNMP errors
def snmp_err(err):
    global STATE_UNKNOWN
    print "UNKNOWN: SNMP Error: {0}".format(err)
    sys.exit(STATE_UNKNOWN)


# SNMP get wrapper with error handling
def my_snmp_get(oid):
    global args
    try:
        retval = snmp_get(oid, hostname=args.H, community=args.C, version=2)
    except (EasySNMPConnectionError, EasySNMPTimeoutError) as err:
        snmp_err(err)
    return retval


# SNMP walk wrapper
def my_snmp_walk(oids):
    global args
    return snmp_bulkwalk(oids, hostname=args.H, community=args.C, version=2)


# Status change wrapper
def trigger_not_ok(req_state, txt):
    global status
    global statusstr
    if req_state > status:
        status = req_state
    statusstr += txt + ","


# Parser for SNMP datetime (Needed by cvsVSLLastConnectionStateChange)
def parse_snmp_datetime(input):
    octval = input.encode('latin1')
    dt_tuple = unpack('>HBBBBBB', octval)
    dt = "{}-{}-{} {}:{}:{}.0".format(
            dt_tuple[0],
            str(dt_tuple[1]).zfill(2),
            str(dt_tuple[2]).zfill(2),
            str(dt_tuple[3]).zfill(2),
            str(dt_tuple[4]).zfill(2),
            str(dt_tuple[5]).zfill(2),
    )
    return dt


# Get all VSS info and check whether the device is actually capable of VSS and have it enabled
try:
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
    cvsSwitchCapability = my_snmp_get(oids_switch[0])
    cvsSwitchMode = my_snmp_get(oids_switch[1])
    if cvsSwitchCapability.value != u'\xc0' and cvsSwitchCapability.value != u'\x80':
        print "UNKNOWN: Switch is not VSS capable!"
        sys.exit(STATE_UNKNOWN)
    if cvsSwitchMode.value != u'2':
        print "OK: Switch is VSS capable, but isn't running in VSS mode"
        sys.exit(STATE_OK)
    rawdata_chassis = my_snmp_walk(oids_chassis)
    rawdata_VSL = my_snmp_walk(oids_VSL)
except (EasySNMPConnectionError, EasySNMPTimeoutError) as err:
    snmp_err(err)

# Sort the walked data into a nicer format
chassis = defaultdict(dict)
for obj in rawdata_chassis:
    chassis[obj.oid_index][obj.oid] = obj
VSL = defaultdict(dict)
for obj in rawdata_VSL:
    VSL[obj.oid_index][obj.oid] = obj

# A valid and healthy VSS cluster is always 2 members
if len(chassis) < 2:
    print "CRITICAL: Only one chassis found, possible cluster member outage!"
    sys.exit(STATE_CRIT)

chassis1 = chassis[list(chassis.keys())[0]]
chassis2 = chassis[list(chassis.keys())[1]]

# We want to catch: standby/standby active/active and whether either are in standalone
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
chassis1_tt = float(int(str(chassis1['cvsChassisUpTime'].value)))*0.01
chassis2_tt = float(int(str(chassis1['cvsChassisUpTime'].value)))*0.01
if chassis1_tt < vss_uptime_warn:
    chassis1_str = "Chassis 1 uptime {} seconds".format(int(chassis1_tt))
    if chassis1_tt < vss_uptime_crit:
        trigger_not_ok(STATE_CRIT, chassis1_str)
    else:
        trigger_not_ok(STATE_WARN, chassis1_str)
if chassis2_tt < vss_uptime_warn:
    chassis2_str = "Chassis 2 uptime {} seconds".format(int(chassis2_tt))
    if chassis2_tt < vss_uptime_crit:
        trigger_not_ok(STATE_CRIT, chassis2_str)
    else:
        trigger_not_ok(STATE_WARN, chassis2_str)
if status != STATE_OK:
    if status == STATE_CRIT:
        statusstr = "CRITICAL:" + statusstr
    else:
        statusstr = "WARNING:" + statusstr
    print statusstr
    sys.exit(status)


# Checking VSL
chassis1_vsl = VSL[list(VSL.keys())[0]]
chassis2_vsl = VSL[list(VSL.keys())[1]]

# Operational status on VSL connection
status = STATE_OK
statusstr = ""
if chassis1_vsl['cvsVSLConnectOperStatus'].value != u'1':
    trigger_not_ok(STATE_CRIT, "Chassis 1 VSL ports down")
if chassis2_vsl['cvsVSLConnectOperStatus'].value != u'1':
    trigger_not_ok(STATE_CRIT, "Chassis 2 VSL ports down")
if status != STATE_OK:
    print "CRITICAL:" + statusstr
    sys.exit(STATE_CRIT)

# Checking that all VSL ports is operational
status = STATE_OK
statusstr = ""
if chassis1_vsl['cvsVSLConfiguredPortCount'].value != chassis1_vsl['cvsVSLOperationalPortCount'].value:
    ports_down = int(chassis1_vsl['cvsVSLConfiguredPortCount'].value) - int(chassis1_vsl['cvsVSLOperationalPortCount'].value)
    trigger_not_ok(STATE_CRIT, "{} VSL ports down on Chassis 1".format(ports_down))
if chassis2_vsl['cvsVSLConfiguredPortCount'].value != chassis2_vsl['cvsVSLOperationalPortCount'].value:
    ports_down = int(chassis2_vsl['cvsVSLConfiguredPortCount'].value) - int(chassis2_vsl['cvsVSLOperationalPortCount'].value)
    trigger_not_ok(STATE_CRIT, "{} VSL ports down on Chassis 1".format(ports_down))
if status != STATE_OK:
    print "CRITICAL:" + statusstr
    sys.exit(STATE_CRIT)

# Check last VSL state change
status = STATE_OK
statusstr = ""
chassis1_dt = parse_snmp_datetime(chassis1_vsl['cvsVSLLastConnectionStateChange'].value)
chassis2_dt = parse_snmp_datetime(chassis1_vsl['cvsVSLLastConnectionStateChange'].value)
chassis1_ts = int(mktime(parse(chassis1_dt).timetuple()))
chassis2_ts = int(mktime(parse(chassis2_dt).timetuple()))
cur_time = int(time())
if (cur_time - chassis1_ts) < vsl_statechange_warn:
    chassis1_str = "Chassis 1 VSL statechange {} seconds ago".format(cur_time - chassis1_ts)
    if (cur_time - chassis1_ts) < vsl_statechange_crit:
        trigger_not_ok(STATE_CRIT, chassis1_str)
    else:
        trigger_not_ok(STATE_WARN, chassis1_str)
if (cur_time - chassis2_ts) < vsl_statechange_warn:
    chassis2_str = "Chassis 2 VSL statechange {} seconds ago".format(cur_time - chassis2_ts)
    if (cur_time - chassis2_ts) < vsl_statechange_crit:
        trigger_not_ok(STATE_CRIT, chassis2_str)
    else:
        trigger_not_ok(STATE_WARN, chassis2_str)
if status != STATE_OK:
    if status == STATE_CRIT:
        statusstr = "CRITICAL:" + statusstr
    else:
        statusstr = "WARNING:" + statusstr
    print statusstr
    sys.exit(status)

# We default to an OK status
print "OK: VSS and VSL status is healthy"
sys.exit(STATE_OK)
