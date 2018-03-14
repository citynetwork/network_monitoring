#!/usr/bin/env python
#
# @descr    Checks VLT status for FTOS switches
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
import argparse
from lib.cnh_nm import STATE_OK, STATE_CRIT
from lib.cnh_nm import trigger_not_ok, check_if_ok, my_snmp_walk
from lib.cnh_nm import snmpresult_to_dict

# Argument parsing
parser = argparse.ArgumentParser(description='Check FTOS environmental status')
parser.add_argument('-C', metavar='<community>', required=True,
                    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Host to check')
args = parser.parse_args()


vlt_detection_oid = 'DELL-NETWORKING-VIRTUAL-LINK-TRUNK-MIB::dellNetVLTDomainId'
oids = [
        'DELL-NETWORKING-VIRTUAL-LINK-TRUNK-MIB::dellNetVLTPeerStatus',
        'DELL-NETWORKING-VIRTUAL-LINK-TRUNK-MIB::dellNetVLTIclStatus',
        'DELL-NETWORKING-VIRTUAL-LINK-TRUNK-MIB::dellNetVLTHBeatStatus',
        'DELL-NETWORKING-VIRTUAL-LINK-TRUNK-MIB::dellNetVLTIclBwStatus'
]


# Check if we can do anything useful against this switch
res = my_snmp_walk(args, vlt_detection_oid)
if not res or not res[0] or res[0].value in [u'NOSUCHOBJECT', u'NOSUCHINSTANCE']:
    print "OK: Either switch doesn't support the VLT MIB, or it doesn't run VLT."
    sys.exit(STATE_OK)


# Check VLT status
rawdata = my_snmp_walk(args, oids)
data = snmpresult_to_dict(rawdata)
status = STATE_OK
statusstr = ""
for index, vltdomain in data.iteritems():
    vlt_domain_id = int(str(index))
    peer_status = int(str(vltdomain['dellNetVLTPeerStatus'].value))
    if peer_status == 0:
        trigger_not_ok(
                status,
                statusstr,
                STATE_CRIT,
                'VLT domain {}: Peer session is not established'.format(vlt_domain_id))
    if peer_status in [2, 3]:
        trigger_not_ok(
                status,
                statusstr,
                STATE_CRIT,
                'VLT domain {}: Peer is down!'.format(vlt_domain_id))

    icl_status = int(str(vltdomain['dellNetVLTIclStatus'].value))
    if peer_status == 0:
        trigger_not_ok(
                status,
                statusstr,
                STATE_CRIT,
                'VLT domain {}: ICL link is not established'.format(vlt_domain_id))
    if peer_status in [2, 3]:
        trigger_not_ok(
                status,
                statusstr,
                STATE_CRIT,
                'VLT domain {}: ICL link is down!'.format(vlt_domain_id))

    hbeat_status = int(str(vltdomain['dellNetVLTHBeatStatus'].value))
    if peer_status == 0:
        trigger_not_ok(
                status,
                statusstr,
                STATE_CRIT,
                'VLT domain {}: Heartbeat link is not established'.format(vlt_domain_id))
    if peer_status in [2, 3]:
        trigger_not_ok(
                status,
                statusstr,
                STATE_CRIT,
                'VLT domain {}: Heartbeat link is down!'.format(vlt_domain_id))

    icl_bwstatus = int(str(vltdomain['dellNetVLTIclBwStatus'].value))
    if icl_bwstatus == 1:
        trigger_not_ok(
                status,
                statusstr,
                STATE_CRIT,
                'VLT domain {}: ICL Bandwidth usage above threshold!'.format(vlt_domain_id))


check_if_ok(status, statusstr)

print "OK: VLT and ICL status good"
sys.exit(STATE_OK)
