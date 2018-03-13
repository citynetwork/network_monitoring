#!/usr/bin/env python
#
# @descr    Checks environment status of Cisco IOS-XR/XE and NX-OS devices
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
import argparse
from lib.cnh_nm import STATE_OK, STATE_CRIT, STATE_WARN
from lib.cnh_nm import my_snmp_get, my_snmp_walk, snmpresult_to_dict
from lib.cnh_nm import trigger_not_ok, check_if_ok


# Argument parsing
parser = argparse.ArgumentParser(description='Check environment of IOS-XR routers')
parser.add_argument('-C', metavar='<community>', required=True,
                    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Host to check')
args = parser.parse_args()


# Get all environmental modules and put in a nicely ordered dict
rawdata = my_snmp_walk(args, 'ENTITY-MIB::entPhysicalTable')
data = snmpresult_to_dict(rawdata)
from pprint import pprint

# Now we loop over the data and perform poweradmin/poweroper/sensorstatus checks
status = STATE_OK
statusstr = ''
for index in data:
    descr = data[index]['entPhysicalDescr'].value

    # First off we'll try getting some Power status for those that support it
    # 1/on - Admin power on
    # 2/off - Admin power off
    # 3/inlineAuto,4/inlineOn,5/powerCycle - PoE stuff, irrelevant for us so not much caring here
    # cefcFRUPowerAdminStatus - 1=on, 2=off, 3=inlineAuto, 4=inlineOn, 5=powerCycle
    pwr_adminstatus = my_snmp_get(args, "CISCO-ENTITY-FRU-CONTROL-MIB::cefcFRUPowerAdminStatus.{0}".format(index))
    if 'NOSUCHINSTANCE' not in pwr_adminstatus.value:
        pwr_adminstatus.value = int(str(pwr_adminstatus.value))
        if pwr_adminstatus.value == 1:
            pass  # ok
        elif pwr_adminstatus == 2:
            trigger_not_ok(status, statusstr, STATE_WARN, "PowerAdminStatus Off for {0}".format(descr))
        elif pwr_adminstatus == 3:
            pass  # ok - PoE stuff
        elif pwr_adminstatus == 4:
            pass  # ok - PoE stuff
        elif pwr_adminstatus == 5:
            pass  # ok - PoE stuff

    # cefcFRUPowerOperStatus
    # 1/offenvOther - Specifies that FRU is powered off because of a problem not listed below
    # 2/on - Specifies that FRU is powered on
    # 3/offAdmin - Specifies that Admin has turned off the FRU
    # 4/offDenied - Specifies that FRU is powered off because the available system power is insufficient
    # 5/offEnvPower - FRU is turned off beacuse of a power problem. For example power translation or distribution problems.
    # 6/offEnvTemp - FRU is turned off because of a temperature problem
    # 7/offEnvFan - FRU is turned off becauses of fan problems
    # 8/failed - FRU has failed
    # 9/onButFanFail - FRU is on but has fan failures
    # 10/offCooling - FRU is off and cooling
    # 11/offConnectorRating - FRU is off because of connector rating problems
    pwr_operstatus = my_snmp_get(args, "CISCO-ENTITY-FRU-CONTROL-MIB::cefcFRUPowerOperStatus.{0}".format(index))
    if 'NOSUCHINSTANCE' not in pwr_operstatus.value:
        pwr_operstatus.value = int(str(pwr_operstatus.value))
        if pwr_operstatus.value == 1:
            trigger_not_ok(status, statusstr, STATE_CRIT, "PowerOperStatus off due to unknown problems for {0}".format(descr))
        if pwr_operstatus.value == 2:
            pass  # ok
        if pwr_operstatus.value == 3:
            trigger_not_ok(status, statusstr, STATE_WARN, "PowerOperStatus Admin off for {0}".format(descr))
        if pwr_operstatus.value == 4:
            trigger_not_ok(status, statusstr, STATE_CRIT, "PowerOperStatus off due to insufficient system power for {0}".format(descr))
        if pwr_operstatus.value == 5:
            trigger_not_ok(status, statusstr, STATE_CRIT, "PowerOperStatus off due to power issues for {0}".format(descr))
        if pwr_operstatus.value == 6:
            trigger_not_ok(status, statusstr, STATE_CRIT, "PowerOperStatus off due to temperature issues for {0}".format(descr))
        if pwr_operstatus.value == 7:
            trigger_not_ok(status, statusstr, STATE_CRIT, "PowerOperStatus off due to fan issues for {0}".format(descr))
        if pwr_operstatus.value == 8:
            trigger_not_ok(status, statusstr, STATE_CRIT, "PowerOperStatus off because of failure for {0}".format(descr))
        if pwr_operstatus.value == 9:
            trigger_not_ok(status, statusstr, STATE_WARN, "PowerOperStatus on but fan has failed for {0}".format(descr))
        if pwr_operstatus.value == 10:
            trigger_not_ok(status, statusstr, STATE_CRIT, "PowerOperStatus off/cooling for {0}".format(descr))
        if pwr_operstatus.value == 11:
            trigger_not_ok(status, statusstr, STATE_CRIT, "PowerOperStatus off due to connector ratings for {0}".format(descr))

    # entSensorStatus
    # 1=ok, 2=unavailable, 3=nonoperational
    sensorstatus = my_snmp_get(args, "CISCO-ENTITY-SENSOR-MIB::entSensorStatus.{0}".format(index))
    if 'NOSUCHINSTANCE' not in sensorstatus.value:
        sensorstatus.value = int(str(sensorstatus.value))
        if sensorstatus.value == 1:
            pass  # ok
        elif sensorstatus.value == 2 and 'transceiver' in descr.lower():
            pass  # Also ok, because all transceivers are not equipped with that
        elif sensorstatus.value == 2:
            trigger_not_ok(status, statusstr, STATE_WARN, " Unavailable sensor status for {0}".format(descr))
        elif sensorstatus.value == 3:
            trigger_not_ok(status, statusstr, STATE_CRIT, " Nonoperational sensor status for {0}".format(descr))

# All checks completed, exiting with the relevant message
check_if_ok(status, statusstr)

print "OK: All environmental checks ok"
sys.exit(STATE_OK)
