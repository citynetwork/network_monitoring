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
	fwrite(STDERR, "{$me} - Check status of a Cisco routers OSPF sessions\n");
	fwrite(STDERR, "Usage: {$me} -H <router> -C <community> -p <peer>\n");
	fwrite(STDERR, "\t-H <Router to check>\n");
	fwrite(STDERR, "\t-C <SNMP community>\n");
	fwrite(STDERR, "\t-p <Peer with which we expect to have a session>\n");
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

// Helper function for when no data is available about the requested peer
function _peerNotFound() {
	global $peer;
	echo "UNKNOWN: Cannot get neighbor state for {$peer}, link down?\n";
	exit($STATE_UNKNOWN);
}

// Get options
$shortopts = "p:H:C:";
$options = getopt($shortopts);
if (empty($options)) usage();
$target = _getopt('H', $options);
$community = _getopt('C', $options);
$peer = _getopt('p', $options);

// Load required mibs
snmp_read_mib('/usr/share/snmp/mibs/IF-MIB.my');
snmp_read_mib('/usr/share/snmp/mibs/OSPF-MIB.my');

// Perform SNMP query
$rawdata = snmp2_real_walk($target, $community, 'OSPF-MIB::ospfNbrTable');
if (false === $rawdata) {
	echo "UNKNOWN: SNMP query failed, host down? Community wrong?\n";
	exit($STATE_UNKNOWN);
}

// Parse the SNMP result into an array of peers
$data = array();
foreach ($rawdata as $rawkey => $rawval) {
	$key = str_replace('IF-MIB::ifDescr.', '', $rawkey);
	list($snmp_prefix, $identifier) = explode('.', $key, 2);
	$data[$identifier][$snmp_prefix] = $rawval;
}

// Check if we got data about the requested peer
if (!in_array("{$peer}.0", array_keys($data))) {
	_peerNotFound();
}
if (!isset($data[$peer.".0"]["OSPF-MIB::ospfNbrState"])) {
	_peerNotFound();
}

// Get the state and check if it's valid
$state = preg_split('/\(|\)/', $data[$peer.".0"]["OSPF-MIB::ospfNbrState"]);
if (!is_array($state) || !isset($state[1])) {
	_peerNotFound();
}

// Check if state is OK or not and output accordinly for Nagios
switch ($state[1]) {
case 1: // down
case 2: // attempt
case 3: // init
case 5: // exchangeStart
case 6: // exchange
	echo "CRITICAL: OSPF down for peer {$peer}\n";
	exit($STATE_CRITICAL);
	break;
case 7: // loading
	echo "WARNING: OSPF in state loading for peer {$peer}\n";
	exit($STATE_WARNING);
	break;
case 4: // twoWay
	echo "OK: OSPF in state twoWay for peer {$peer}\n";
	exit($STATE_OK);
	break;
case 8: // full
	echo "OK: OSPF up for peer {$peer}\n";
	exit($STATE_OK);
	break;
}
