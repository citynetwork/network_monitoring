#!/usr/bin/env python
#
# @descr    Checks OSPF session status
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
import argparse
from lib.cnh_nm import STATE_OK, STATE_CRIT
from lib.cnh_nm import my_snmp_get

# OSPF states:
# 1=down, 2=attempt, 3=init, 4=twoway
# 5=exchangestart, 6=exchange, 7=loading
# 8=full
ospf_ok_states = [4, 8]


# Argument parsing
parser = argparse.ArgumentParser(description='Check a OSPF sessions status')
parser.add_argument('-C', metavar='<community>', required=True,
                    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Host to check')
parser.add_argument('-p', metavar='<peer>', required=True,
                    help='IPv4 of peer to check')
args = parser.parse_args()


# Get all interfaces, and then get OSPF data for that interface
rawdata = my_snmp_get(args, 'OSPF-MIB::ospfNbrState.{}.0'.format(args.p))
if not rawdata or 'NOSUCH' in rawdata.value:
    print "CRITICAL: No OSPF session detected for peer {}".format(args.p)
    sys.exit(STATE_CRIT)


nei_state = int(str(rawdata.value))
if nei_state not in ospf_ok_states:
    print "CRITICAL: OSPF session for peer {} down".format(args.p)
    sys.exit(STATE_CRIT)


print "OK: OSPF session for {} is up".format(args.p)
sys.exit(STATE_OK)
