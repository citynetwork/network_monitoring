#!/usr/bin/env python
#
# @descr    Checks environment status of Mellanox devices
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
import argparse
from lib.cnh_nm import STATE_OK, STATE_CRIT, STATE_WARN
from lib.cnh_nm import my_snmp_get, my_snmp_walk, snmpresult_to_dict, my_snmp_get_int
from lib.cnh_nm import trigger_not_ok, check_if_ok
from struct import unpack


# Argument parsing
parser = argparse.ArgumentParser(description='Check environment of Mellanox switches')
parser.add_argument('-C', metavar='<community>', required=True,
                    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True,
                    help='Host to check')
args = parser.parse_args()


oid_sensor_operstatus = 'ENTITY-SENSOR-MIB::entPhySensorOperStatus.{}'

oid_state_oper = 'ENTITY-STATE-MIB::entStateOper.{}'
oid_state_usage = 'ENTITY-STATE-MIB::entStateUsage.{}'
oid_state_alarm = 'ENTITY-STATE-MIB::entStateAlarm.{}'
oid_state_standby = 'ENTITY-STATE-MIB::entStateStandby.{}'


# Checking status of an entity, including alarm states
# And skipping checking for standby units as those will
# most likely show up as disabled
def check_entity_state(index, entity_name):
    global args, status, statusstr, oid_state_oper
    global oid_state_usage, oid_state_alarm, oid_state_standby

    standby_status = my_snmp_get_int(args, oid_state_standby.format(index))
    if standby_status in [2, 3]:  # Entity is standby unit
        return

    oper_status = my_snmp_get_int(args, oid_state_oper.format(index))
    if oper_status == 2:  # disabled
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            'Entity {} is in a disabled state'.format(entity_name))

    usage_status = my_snmp_get_int(args, oid_state_usage.format(index))
    if usage_status == 4:  # busy
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            'Entity {} is fully utilized, no capacity left'.format(entity_name))

    alarm_status = my_snmp_get(args, oid_state_alarm.format(index)).value.encode('latin1')
    alarm_bit = unpack("B", alarm_status)[0]
    if alarm_bit == 0:  # unknown, but also ok
        return
    elif alarm_bit == 1:  # underRepair
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_WARN,
            'Entity {} is undergoing repair'.format(entity_name))
    elif alarm_bit == 2:  # Critical
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            'Entity {} is in critical state'.format(entity_name))
    elif alarm_bit == 3:  # Major
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_CRIT,
            'Entity {} is in major alarm state'.format(entity_name))
    elif alarm_bit == 4:  # Minor
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_WARN,
            'Entity {} is in minor alarm state'.format(entity_name))
    elif alarm_bit == 5:  # Warning
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_WARN,
            'Entity {} is in warning state'.format(entity_name))
    elif alarm_bit == 6:  # Indeterminate
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_WARN,
            'Entity {} is in an indeterminative state'.format(entity_name))


# Checking operational status of a sensor
# Not checking temps, fan speeds etc as only values are available
# There are no thresholds exposed over SNMP
def check_sensor_oper_status(index, sensor_name):
    global args, status, statusstr, oid_sensor_operstatus
    oper_status = my_snmp_get(args, oid_sensor_operstatus.format(index))
    if oper_status.value == u'1':  # Ok
        return
    elif oper_status.value == u'2':  # Unavailable
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_WARN,
            '{} sensor status: Unavailable'.format(sensor_name))
    elif oper_status.value == u'3':  # Non-operational
        status, statusstr = trigger_not_ok(
            status,
            statusstr,
            STATE_WARN,
            '{} sensor status: Non-operational'.format(sensor_name))


# Get all environmental modules and put in a nicely ordered dict
rawdata = my_snmp_walk(args, 'ENTITY-MIB::entPhysicalTable')
data = snmpresult_to_dict(rawdata)


# Now we loop over the data and perform poweradmin/poweroper/sensorstatus checks
status = STATE_OK
statusstr = ''
serial_number = ''
model_name = ''
for index, entity in data.iteritems():
    descr = entity['entPhysicalDescr'].value
    physical_class = int(str(entity['entPhysicalClass'].value))
    physical_name = entity['entPhysicalName'].value

    # These two only useful where entPhysicalName == 'Chassis'
    if physical_name == u'Chassis':
        serial_number = entity['entPhysicalSerialNum'].value
        model_name = entity['entPhysicalModelName'].value

    hr_name = "{} ({})".format(physical_name, descr)

    if physical_class == 1 and 'MGMT' in descr:  # MGMT interfaces
        continue
    elif physical_class == 3:  # Chassis - No sensors on this index
        continue
    elif physical_class == 5:  # Container - (Port modules), no sensors here either
        continue
    elif physical_class == 6:  # Power Supply
        check_entity_state(index, hr_name)
    elif physical_class == 8:  # Sensor (includes fans in Mellanox world)
        check_entity_state(index, hr_name)
        check_sensor_oper_status(index, hr_name)
    elif physical_class == 12:  # CPU
        check_entity_state(index, hr_name)


# All done, check status and exit
check_if_ok(status, statusstr)

print "OK: Health ok on {} switch with serial {}".format(model_name, serial_number)
sys.exit(STATE_OK)
