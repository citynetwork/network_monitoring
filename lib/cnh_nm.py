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
from time import mktime
from dateutil.parser import parse
from ipaddress import ip_address

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
    return [status, statusstr]


# Status check and alert wrapper
def check_if_ok(status, statusstr):
    global status_txt_mapper
    if status != STATE_OK:
        print "{}: {}".format(status_txt_mapper[status], statusstr)
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


# Convert output of parse_snmp_datetime into a timestamp
def strtime_to_timestamp(input):
    return int(mktime(parse(input).timetuple()))


# Parse Dell timeticks
def dell_parse_snmp_uptime(timeticks):
    return int(str(timeticks)[:-2])


# Detecting IP version of SNMP OID index
def snmp_oid_ipver(oid):
    if oid.startswith("1.4"):
        return 'IPv4'
    elif oid.startswith("2.16"):
        return 'IPv6'
    else:
        return None


# Decoding IP from SNMP OID index
def snmp_oid_decode_ip(oid):
    ipver = snmp_oid_ipver(oid)
    if 'IPv4' == ipver:
        return oid[4:]
    else:
        ip_coded = oid[5:].split('.')
        ip_decoded = ""
        i = 1
        for part in ip_coded:
            ip_decoded += str(hex(int(part, 10)))[2:].zfill(2)
            if i % 2 == 0:
                ip_decoded += ':'
            i += 1
        if isinstance(ip_decoded, unicode):
            return ip_decoded.lower().rstrip(':')
        else:
            return unicode(ip_decoded.lower().rstrip(':'))


# Decode the dellNetBgpM2PeerRemoteAddr field from FTOS devices
def ftos_get_peer_ip(peeraddr, peeraddr_type):
    packed = peeraddr.value.encode('latin1')
    if int(str(peeraddr_type.value)) == 1:  # IPv4
        int_tuple = unpack('>BBBB', packed)
        str_tuple = [str(item) for item in int_tuple]
        return ".".join(str_tuple)
    else:  # IPv6
        int_tuple = unpack('>BBBBBBBBBBBBBBBB', packed)
        str_tuple = [str(hex(item))[2:].zfill(2) for item in int_tuple]
        ip6_decoded = ""
        i = 1
        for part in str_tuple:
            ip6_decoded += part
            if i % 2 == 0:
                ip6_decoded += ':'
            i += 1
        ip6 = ip_address(unicode(ip6_decoded.rstrip(':')))
        return str(ip6.compressed)
