#!/bin/sh

. /opt/plugins/utils.sh

snmpwalk="/usr/bin/snmpwalk"

host="$1"
community="$2"
interface="$3"

state_down=1
state_attempt=2
state_init=3
state_twoway=4
state_exchangestart=5
state_exchange=6
state_loading=7
state_full=8

nextq=$($snmpwalk -m IF-MIB -v2c -c "$community" "$host" IF-MIB::ifDescr | grep "$interface\$" | awk '{print $1;}' | sed 's,IF-MIB,OSPFV3-MIB,g;s,ifDescr,ospfv3NbrState,g')
if [ "$nextq" = "" ]; then
	echo "UNKNOWN: Query failed, correct interface?"
	exit "$STATE_UNKNOWN"
fi
line=$($snmpwalk -m OSPFV3-MIB -v2c -c "$community" "$host" "$nextq")
if [ "$line" = "" ]; then
	echo "UNKNOWN: OSPFv3 session not configured?"
	exit "$STATE_UNKNOWN"
fi
nbr_state=$(echo "$line" | awk '{print $NF}')
nbr_intstate=$(echo "$nbr_state" | grep -oE '[0-9]')
peer_orig="on $interface"

case $nbr_intstate in
	$state_down)
		echo "CRITICAL: Neighbor $peer_orig is in state $nbr_state!"
		exit "$STATE_CRITICAL"
		;;
	$state_attempt)
		echo "CRITICAL: Neighbor $peer_orig is in state $nbr_state!"
		exit "$STATE_CRITICAL"
		;;
	$state_init)
		echo "CRITICAL: Neighbor $peer_orig is in state $nbr_state!"
		exit "$STATE_CRITICAL"
		;;
	$state_exchangestart)
		echo "CRITICAL: Neighbor $peer_orig is in state $nbr_state!"
		exit "$STATE_CRITICAL"
		;;
	$state_exchange)
		echo "CRITICAL: Neighbor $peer_orig is in state $nbr_state!"
		exit "$STATE_CRITICAL"
		;;
	$state_loading)
		echo "WARNING: Neighbor $peer_orig is in state $nbr_state!"
		exit "$STATE_WARNING"
		;;
	$state_twoway)
		echo "OK: Neighbor $peer_orig is in state $nbr_state!"
		exit "$STATE_OK"
		;;
	$state_full)
		echo "OK: Neighbor $peer_orig is in state $nbr_state!"
		exit "$STATE_OK"
		;;
	*)
		echo "CRITICAL: Neighbor $peer_orig is in an unknown state!"
		exit "$STATE_CRITICAL"
esac
