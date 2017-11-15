#!/usr/bin/env php
<?php
/**
 * @package citynetwork/network-monitoring
 * @author Johan Hedberg <jh@citynetwork.se>
 * @license 2-clause BSD License
 **/

// Nagios return values
$STATE_OK = 0;
$STATE_WARNING = 1;
$STATE_CRITICAL = 2;
$STATE_UNKNOWN = 3;
$STATE_DEPENDENT = 4;

function usage() {
	global $STATE_UNKNOWN;
	$me = basename($_SERVER['PHP_SELF']);
	fwrite(STDERR, "{$me} - Check status of a Cisco routers OSPFv3 sessions\n");
	fwrite(STDERR, "Usage: {$me} -H <router> -C <community> -i <interface>\n");
	fwrite(STDERR, "\t-H <Router to check>\n");
	fwrite(STDERR, "\t-C <SNMP community>\n");
	fwrite(STDERR, "\t-i <Interface on which we expect a session>\n");
	exit($STATE_UNKNOWN);
}

// Helper function to get a required option, or bail out with a failure
function _getopt($opt, $options) {
	if (!isset($options[$opt])) {
		usage();
	}
	else {
		return $options[$opt];
	}
}

// Get options
$shortopts = "i:H:C:";
$options = getopt($shortopts);
if (empty($options)) usage();
$target = _getopt('H', $options);
$community = _getopt('C', $options);
$interface = _getopt('i', $options);

// Load required mibs
snmp_read_mib('/usr/share/snmp/mibs/IF-MIB.my');
snmp_read_mib('/usr/share/snmp/mibs/OSPFV3-MIB.my');

// Get all interface descriptions
@$rawdata = snmp2_real_walk($target, $community, 'IF-MIB::ifDescr');
if (false === $rawdata) {
	echo "UNKNOWN: SNMP query failed, host down? Community wrong?\n";
	exit($STATE_UNKNOWN);
}

// Get the interface index for our $interface
$ifindex = NULL;
foreach ($rawdata as $rawkey => $rawval) {
	if (strpos($rawval, $interface)!==false) {
		$ifindex = array_pop(explode('.', $rawkey));
		break;
	}
}
if ( NULL == $ifindex) {
	echo "UNKNOWN: Index not found, does the interface exist?\n";
	exit($STATE_UNKNOWN);
}

// Get the neighbor state for that link
@$rawdata = snmp2_real_walk($target, $community, "OSPFV3-MIB::ospfv3NbrState.{$ifindex}");
if (false === $rawdata) {
	echo "UNKNOWN: SNMP query failed, host down? Community wrong?\n";
	exit($STATE_UNKNOWN);
}

// Check that we actually got a result
if (!is_array($rawdata) || (count($rawdata)<1)) {
	echo "CRITICAL: No OSPF sessions running on $interface\n";
	exit($STATE_CRITICAL);
}

// As the SNMP key contains a session index, we can't know the key
$key = array_shift(array_keys($rawdata));

// Get the state and check if it's valid
$state = preg_split('/\(|\)/', $rawdata[$key]);
if (!is_array($state) || !isset($state[1])) {
	echo "UNKNOWN: Cannot get neighbor state for {$peer}, link down?\n";
	exit($STATE_UNKNOWN);
}

// Check if state is OK or not and output accordinly for Nagios
switch ($state[1]) {
case 1: // down
case 2: // attempt
case 3: // init
case 5: // exchangeStart
case 6: // exchange
	echo "CRITICAL: OSPF down on {$interface}\n";
	exit($STATE_CRITICAL);
	break;
case 7: // loading
	echo "WARNING: OSPF in state loading on {$interface}\n";
	exit($STATE_WARNING);
	break;
case 4: // twoWay
	echo "OK: OSPF in state twoWay on {$interface}\n";
	exit($STATE_OK);
	break;
case 8: // full
	echo "OK: OSPF up on {$interface}\n";
	exit($STATE_OK);
	break;
}
