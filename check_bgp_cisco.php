#!/usr/bin/env php
<?php
/**
 * @package citynetwork/network-monitoring
 * @author Johan Hedberg <jh@citynetwork.se>
 * @license 2-clause BSD License
 **/

// Pear Net::IPv6 is required for the condensing of IPv6 addresses
require 'Net/IPv6.php';

// Nagios return values
$STATE_OK = 0;
$STATE_WARNING = 1;
$STATE_CRITICAL = 2;
$STATE_UNKNOWN = 3;
$STATE_DEPENDENT = 4;

function usage() {
	global $STATE_UNKNOWN;
	$me = basename($_SERVER['PHP_SELF']);
	fwrite(STDERR, "{$me} - Check status of a Cisco routers BGP sessions\n");
	fwrite(STDERR, "Usage: {$me} -H <router> -C <community> -a <asnum>\n");
	fwrite(STDERR, "\t-H <Router to check>\n");
	fwrite(STDERR, "\t-C <SNMP community>\n");
	fwrite(STDERR, "\t-a <Local AS number>\n");
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
$shortopts = "a:H:C:";
$options = getopt($shortopts);
if (empty($options)) usage();
$target = _getopt('H', $options);
$community = _getopt('C', $options);
$my_as = _getopt('a', $options);

// Reformat the IPv6 address from SNMP oid format to human-readable
function _fixV6Addr($addr) {
	$addr = str_replace(':', '', $addr);
	$str ="";
	for($i=1; $i <= strlen($addr); $i++) {
		$str .= $addr[$i-1];
		if ( ($i%4)==0 && ($i != strlen($addr))) {
			$str .= ':';
		}
	}
	return Net_IPv6::compress($str);
}

// Parse the SNMP values we care about into something a bit easier to use in the checks
function _parseValue($val) {
	if (strpos($val, 'STRING: ')===0) {
		list($temp, $str) = explode('STRING: ', $val);
		return $str;
	}
	if (strpos($val, 'Gauge32: ')===0) {
		list($temp, $str) = explode('Gauge32: ', $val);
		if (strpos($str, 'seconds')!==false) {
			list($strval, $strunit) = explode(' ', $str);
			return $strval;
		}
		else {
			return $str;
		}
	}
	if (strpos($val, 'INTEGER: ')===0) {
		$val = str_replace(array('(', ')'), ' ', $val);
		$parts = explode(' ', $val);
		if (isset($parts[2]) && $parts[2] == 'seconds') {
			return $parts[1];
		}
		else if (!isset($parts[2])) {
			return $parts[1];
		}
		else {
			return $parts[2];
		}
	}
	else {
		return $val;
	}
}

// Translation of BGP states between SNMP id and human readable description
$statemapping = array(
	'bgp_states' => array(
		0 => 'none',
		1 => 'idle',
		2 => 'connect',
		3 => 'active',
		4 => 'opensent',
		5 => 'openconfirm',
		6 => 'established',
		'none' => 0,
		'idle' => 1,
		'connect' => 2,
		'active' => 3,
		'opensent' => 4,
		'openconfirm' => 5,
		'established' => 6
	),
	'admin_states' => array(
		1 => 'down',
		2 => 'up',
		'down' => 1,
		'up' => 2
	)
);

// Load Cisco BGP4 mib and perform SNMP query
snmp_read_mib('/usr/share/snmp/mibs/CISCO-BGP4-MIB.my');
$rawdata = snmp2_real_walk($target, $community, 'CISCO-BGP4-MIB::cbgpPeer2Table');
if (false === $rawdata) {
	echo "UNKNOWN: SNMP query failed, host down? Community wrong?\n";
	exit($STATE_UNKNOWN);
}

// Loop over the $rawdata from SNMP and sort it nicely in another array
$data = array();
foreach ($rawdata as $rawkey => $rawval) {
	list($snmp_prefix, $ipver, $identifier) = explode('.', $rawkey, 3);
	$identifier = str_replace('"', '', $identifier);
	if ( $ipver == 'ipv6' ) {
		$identifier = _fixV6Addr($identifier);
	}
	$snmp_prefix = str_replace('CISCO-BGP4-MIB::', '', $snmp_prefix);
	$data[$identifier][$snmp_prefix] = _parseValue($rawval);
}

// As we are potentially checking many sessions, default to OK, then fail later
$status = $STATE_OK;
$status_str = "";

// Loop over all detected BGP sessions and check the Admin state and BGP session state
foreach ($data as $bgp_peer => $peerdata) {
	if ( $my_as == $peerdata['cbgpPeer2RemoteAs']) {
		$remote_as = 'iBGP';
	}
	else {
		$remote_as = $peerdata['cbgpPeer2RemoteAs'];
	}
	if ($peerdata['cbgpPeer2AdminStatus'] == $statemapping['admin_states']['down']) {
		$status = ($status == $STATE_OK) ? $STATE_WARNING : $status;
		$status_str .= " {$bgp_peer}:AdminDown({$remote_as})";
		continue;
	}
	if ($peerdata['cbgpPeer2State'] != $statemapping['bgp_states']['established']) {
		$status = $STATE_CRITICAL;
		$status_str .= " {$bgp_peer}:{$statemapping['bgp_states'][$peerdata['cbgpPeer2State']]}({$remote_as})";
	}
	else { // none, idle, connect, active, opensent, openconfirm
		continue;
	}
}

// Check status and print with an OK/WARNING/CRITICAL/UNKNOWN prefix
$status_str = str_replace(' ', ' // ', trim($status_str));

switch ($status) {
case $STATE_OK:
	$status_str = 'OK: ' . $status_str;
	break;
case $STATE_WARNING:
	$status_str = 'WARNING: ' . $status_str;
	break;
case $STATE_CRITICAL:
	$status_str = 'CRITICAL: ' . $status_str;
	break;
case $STATE_UNKNOWN:
	$status_str = 'UNKNOWN: ' . $status_str;
	break;
}

echo $status_str . "\n";
exit($status);
