#!/usr/bin/env python
#
# @descr    Checks a keepalived cluster
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

import sys
import argparse
from lib.cnh_nm import STATE_OK, STATE_CRIT, STATE_WARN, trigger_not_ok, check_if_ok
from lib.cnh_nm import my_snmp_walk, my_snmp_get, snmpresult_to_dict


# Argument parsing
parser = argparse.ArgumentParser(description='Check a OSPF sessions status')
parser.add_argument('-C', metavar='<community>', required=True,
                    help='SNMP Community')
parser.add_argument('-H', metavar='<host>', required=True, action='append', nargs='+',
                    help='Hosts to check')
args = parser.parse_args()
hosts = args.H[0]


# OIDs
oid_routerid = 'KEEPALIVED-MIB::routerId.0'
oids_syncgroups = [
    'KEEPALIVED-MIB::vrrpSyncGroupName',
    'KEEPALIVED-MIB::vrrpSyncGroupState'
]
oids_instances = [
    'KEEPALIVED-MIB::vrrpInstanceName',
    'KEEPALIVED-MIB::vrrpInstanceState',
    'KEEPALIVED-MIB::vrrpInstancePreempt',
    'KEEPALIVED-MIB::vrrpInstanceSyncGroup'
]


# VRRP states
vrrp_state_mapper = {
    0: 'init',
    1: 'backup',
    2: 'master',
    3: 'fault',
    4: 'unknown',
    5: 'shutdown'
}


# Get data and shuffle into these dict's in a way that we can iterate them nicely
syncgroups_states = {}
states = {}
preempt = {}
for host in hosts:
    snmp_args = type('lambdaobject', (object,), {'H': host, 'C': args.C})()
    router_id = my_snmp_get(snmp_args, oid_routerid).value
    if router_id not in states:
        states[router_id] = {}
    if router_id not in preempt:
        preempt[router_id] = {}
    if router_id not in syncgroups_states:
        syncgroups_states[router_id] = {}
    raw_syncgroups = my_snmp_walk(snmp_args, oids_syncgroups)
    raw_instances = my_snmp_walk(snmp_args, oids_instances)
    syncgroups = snmpresult_to_dict(raw_syncgroups)
    instances = snmpresult_to_dict(raw_instances)
    for syncgroup_id, syncgroup in syncgroups.items():
        syncgroup_name = syncgroup['vrrpSyncGroupName'].value
        syncgroup_state = int(str(syncgroup['vrrpSyncGroupState'].value))
        syncgroups_states[router_id][syncgroup_name] = syncgroup_state
    for instance_id, instance in instances.items():
        instance_name = instance['vrrpInstanceName'].value
        instance_state = int(str(instance['vrrpInstanceState'].value))
        instance_preempt = int(str(instance['vrrpInstancePreempt'].value))
        instance_syncgroup = instance['vrrpInstanceSyncGroup'].value
        if instance_name not in states[router_id]:
            states[router_id][instance_name] = instance_state
        if instance_name not in preempt[router_id]:
            preempt[router_id][instance_name] = instance_preempt


# Verifying that we have a consistent state of all syncgroups and instances on each host
# and that all instances on all hosts have preempt enabled (perhaps this thing should
# be configurable, but we want it like this everywhere as of today)
status = STATE_OK
statusstr = ''

expected_state = {}
state_status_strs = []
state_status = STATE_OK
for host, syncgroups in syncgroups_states.items():
    if host not in expected_state:
        expected_state[host] = None
    for sg_name, sg_state in syncgroups.items():
        sg_state = vrrp_state_mapper[sg_state]
        state_status_strs.append('Syncgroup {} {}: {}'.format(host, sg_name, sg_state))
        if not expected_state[host]:
            expected_state[host] = sg_state
            continue
        if sg_state != expected_state[host]:
            state_status = STATE_CRIT
if state_status == STATE_CRIT:
    status, statusstr = trigger_not_ok(status, statusstr, state_status, 'Inconsistent syncgroup states: {}'.format(",".join(state_status_strs)))

state_status_strs = []
state_status = STATE_OK
for host, instance in states.items():
    for instance_name, instance_state in instance.items():
        instance_state = vrrp_state_mapper[instance_state]
        state_status_strs.append('Instance {} {}: {}'.format(host, instance_name, instance_state))
        if not expected_state[host]:
            expected_state[host] = instance_state
            continue
        if instance_state != expected_state[host]:
            state_status = STATE_CRIT
if state_status == STATE_CRIT:
    status, statusstr = trigger_not_ok(status, statusstr, state_status, 'Inconsistent instance states: {}'.format(",".join(state_status_strs)))

preempt_status_strs = []
preempt_status = STATE_OK
for host, instance in preempt.items():
    for instance_name, instance_preempt in instance.items():
        if instance_preempt != 1:
            preempt_status = STATE_CRIT
            preempt_status_strs.append('Instance {} {} have preempt disabled.'.format(host, instance_name))
if preempt_status == STATE_CRIT:
    status, statusstr = trigger_not_ok(status, statusstr, preempt_status, ','.join(preempt_status_strs))


# By this point we have handled inconsistencies within the hosts, now to check that we have exactly one master and the rest are slaves
# and that no host is in a weird state
num_masters = 0
num_backups = 0
masters = []
for host, state in expected_state.items():
    if state == 'master':
        num_masters += 1
        masters.append(host)
    elif state == 'shutdown':
        status, statusstr = trigger_not_ok(status, statusstr, STATE_WARN, 'Host {} is in {} state'.format(host, state))
    elif state == 'backup':
        num_backups += 1
    else:
        status, statusstr = trigger_not_ok(status, statusstr, STATE_CRIT, 'Host {} is in {} state'.format(host, state))
if num_masters > 1:
    status, statusstr = trigger_not_ok(status, statusstr, STATE_CRIT, 'Multiple masters ({})!'.format(",".join(masters)))
elif num_masters < 1:
    status, statusstr = trigger_not_ok(status, statusstr, STATE_CRIT, 'No masters!')
if num_backups < 1:
    status, statusstr = trigger_not_ok(status, statusstr, STATE_CRIT, 'No backups!')


# All done, exiting
check_if_ok(status, statusstr)
print ("OK: {} masters ({}) and {} backups with no inconsistencies.".format(num_masters, ",".join(masters), num_backups))
sys.exit(STATE_OK)
