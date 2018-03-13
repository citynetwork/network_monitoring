#!/usr/bin/env python
#
# @descr    Network monitoring, common functions
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
from collections import defaultdict
from easysnmp import snmp_get, snmp_bulkwalk, EasySNMPConnectionError, EasySNMPTimeoutError
from struct import unpack

# Nagios states
STATE_OK = 0
STATE_WARN = 1
STATE_CRIT = 2
STATE_UNKNOWN = 3

status_txt_mapper = {
        0: 'OK',
        1: 'WARNING',
        2: 'CRITICAL',
        3: 'UNKNOWN'
}


# Handle (or rather not handle) SNMP errors
def snmp_err(err):
    global STATE_UNKNOWN
    print "UNKNOWN: SNMP Error: {0}".format(err)
    sys.exit(STATE_UNKNOWN)


# SNMP get wrapper with error handling
def my_snmp_get(args, oid):
    try:
        retval = snmp_get(oid, hostname=args.H, community=args.C, version=2)
    except (EasySNMPConnectionError, EasySNMPTimeoutError) as err:
        snmp_err(err)
    return retval


# SNMP walk wrapper
def my_snmp_walk(args, oids):
    try:
        retval = snmp_bulkwalk(oids, hostname=args.H, community=args.C, version=2)
    except (EasySNMPConnectionError, EasySNMPTimeoutError) as err:
        snmp_err(err)
    return retval


# Getting an integer value and nothing else
def my_snmp_get_int(args, oid):
    retval = my_snmp_get(args, oid)
    return int(str(retval.value))


# Status change wrapper
def trigger_not_ok(status, statusstr, req_state, txt):
    if req_state > status:
        status = req_state
    statusstr += txt + ","


# Status check and alert wrapper
def check_if_ok(status, statusstr):
    global status_txt_wrapper
    if status != STATE_OK:
        print "{}:{}".format(status_txt_wrapper[status], statusstr)
        sys.exit(status)
    else:
        statusstr = ""
        status = None


# Re-formatting the SNMP walk result into something more workable
def snmpresult_to_dict(snmpresult):
    retval = defaultdict(dict)
    for obj in snmpresult:
        retval[obj.oid_index][obj.oid] = obj
    return retval


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


# Parse Dell timeticks
def dell_parse_snmp_uptime(timeticks):
    return int(str(timeticks)[:-2])
