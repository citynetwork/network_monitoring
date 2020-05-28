#!/usr/bin/env zsh
#
# @descr    Runs ping checks against a specified target, via SSH to a Cisco router
#
# @author   Johan Hedberg <jh@citynetwork.se>
#

# TODO:
# * Full support for SSH key authentication
# * Support for SSH password in a file


# Modules used
zmodload zsh/regex
zmodload zsh/zutil


# Nagios states
STATE_OK=0
STATE_WARN=1
STATE_CRIT=2
STATE_UNKNOWN=3


# Argument parsing
local -a arg_help arg_host arg_target arg_warn_pct_pl arg_crit_pct_pl arg_warn_rtt arg_crit_rtt arg_ssh_user arg_ssh_pass arg_size arg_repeat arg_timeout
zparseopts h=arg_help H:=arg_host T:=arg_target W:=arg_warn_pct_pl C:=arg_crit_pct_pl w:=arg_warn_rtt c:=arg_crit_rtt u:=arg_ssh_user p:=arg_ssh_pass s:=arg_size r:=arg_repeat t:=arg_timeout


# Usage function
function usage() {
  echo
  echo "$1 - Runs ping checks against a specified target, via SSH to a Cisco router"
  echo "@author: Johan Hedberg <jh@citynetwork.se>"
  echo
  echo "Usage: $1 [-h] -H <ip/hostname> -t <ip/hostname> [-W N%] [-C N%] [-w N] [-c N] -u <username> [-p <password>] [-s N]"
  echo "-h\tShow this usage information"
  echo "-H\tIP/hostname of router to run checks from"
  echo "-T\tIP/hostname to ping"
  echo "-W\tWarning limit in % for packetloss, only specify the number (default 20%)"
  echo "-C\tCritical limit in % for packetloss, only specify the number (default 40%)"
  echo "-w\tWarning limit in milliseconds for RTT (default 30)"
  echo "-c\tCritical limit in milliseconds for RTT (default 60)"
  echo "-u\tSSH username"
  echo "-p\tSSH password"
  echo "-r\tRepeat count (default 5)"
  echo "-s\tSize of ping packet (default 64)"
  echo "-t\tTimeout in seconds (default 1)"
  exit $STATE_UNKNOWN
}


# Default variables
myname=$(basename \"$0\" | tr -d '"')
warn_pct_pl=20
crit_pct_pl=40
warn_rtt=30
crit_rtt=60
pkt_size=64
repeat_cnt=5
timeout=1
state=$STATE_OK
statestr=""


# Argument handling
[[ -n "${arg_help}" ]] && usage "$myname"
[[ -z "${arg_host}" ]] && usage "$myname"
[[ -z "${arg_target}" ]] && usage "$myname"
[[ "${arg_host}" =~ [\-a-z0-9\.]+ ]] || usage "$myname"
[[ "${arg_target}" =~ [\-a-z0-9\.]+ ]] || usage "$myname"
[[ -z "${arg_ssh_user}" ]] && usage $myname
[[ -n "${arg_warn_pct_pl}" ]] && [[ "${arg_warn_pct_pl[2]}" = <-> ]] && let "warn_pct_pl=${arg_warn_pct_pl[2]}"
[[ -n "${arg_crit_pct_pl}" ]] && [[ "${arg_crit_pct_pl[2]}" = <-> ]] && let "crit_pct_pl=${arg_crit_pct_pl[2]}"
[[ -n "${arg_warn_rtt}" ]] && [[ "${arg_warn_rtt[2]}" = <-> ]] && let "warn_rtt=${arg_warn_rtt[2]}"
[[ -n "${arg_crit_rtt}" ]] && [[ "${arg_crit_rtt[2]}" = <-> ]] && let "crit_rtt=${arg_crit_rtt[2]}"
[[ -n "${arg_size}" ]] && [[ "${arg_size[2]}" = <-> ]] && let "pkt_size=${arg_size[2]}"
[[ -n "${arg_repeat}" ]] && [[ "${arg_repeat[2]}" = <-> ]] && let "repeat_cnt=${arg_repeat[2]}"
[[ -n "${arg_timeout}" ]] && [[ "${arg_timeout[2]}" = <-> ]] && let "timeout=${arg_timeout[2]}"

if [[ -n "${arg_ssh_pass}" ]]; then
  res=$(sshpass -p "${arg_ssh_pass[2]}" ssh -l "${arg_ssh_user[2]}" "${arg_host[2]}" "ping ${arg_target[2]} timeout $timeout size $pkt_size df-bit validate repeat $repeat_cnt" 2>/dev/null | grep Success.rate)
else
  res=$(ssh -l "${arg_ssh_user[2]}" "${arg_host[2]}" "ping ${arg_target[2]} timeout $timeout size $pkt_size df-bit validate repeat $repeat_cnt" 2>/dev/null | grep Success.rate)
fi
[[ -z "$res" ]] && {
  echo "UNKNOWN: SSH command failed (or unexpected output received)"
  exit $STATE_UNKNOWN
}


# Result parsing
success_pct=$(echo "$res" | awk '{print $4}')
avg_rtt=$(echo "$res" | awk '{print $(NF-1)}' | awk -F / '{print $2;}')
[[ "$success_pct" = <-> ]] || {
  echo "UNKNOWN: Unable to parse router output!"
  exit $STATE_UNKNOWN
}
[[ $success_pct -gt 0 ]] && {
  [[ "$avg_rtt" = <-> ]] || {
    echo "UNKNOWN: Unable to parse router output!"
    exit $STATE_UNKNOWN
  }
}
let "fail_pct=100-$success_pct"


# Warn/crit checking
if [ $fail_pct -ge $warn_pct_pl ] && [ $fail_pct -lt $crit_pct_pl ]; then
  statestr="$statestr $fail_pct% packetloss detected!"
  state=$STATE_WARN
elif [ $fail_pct -ge $crit_pct_pl ]; then
  statestr="$statestr $fail_pct% packetloss detected!"
  state=$STATE_CRIT
fi
if [ $success_pct -ne 0 ]; then  # If we didn't succeed a single ping, of course we don't have any RTT values
  if [ $avg_rtt -ge $warn_rtt ] && [ $avg_rtt -lt $crit_rtt ]; then
    statestr="$statestr Average RTT is $avg_rtt"
    if [ $state -lt $STATE_WARN ]; then
      state=$STATE_WARN
    fi
  elif [ $avg_rtt -ge $crit_rtt ]; then
    statestr="$statestr Average RTT is $avg_rtt"
    if [ $state -lt $STATE_CRIT ]; then
      state=$STATE_CRIT
    fi
  else  # This is the output in the 'OK' state
    statestr="$statestr Average RTT is $avg_rtt"
  fi
fi

# Perfdata
perfdata="packetloss=${fail_pct}%;${warn_pct_pl};${crit_pct_pl}"
if [ $success_pct -ne 0 ]; then
  perfdata="$perfdata avg_rtt=${avg_rtt}ms;${warn_rtt};${crit_rtt}"
fi

if [ $state -eq $STATE_CRIT ]; then
  echo -n "CRITICAL:"
elif [ $state -eq $STATE_WARN ]; then
  echo -n "WARNING:"
else
  echo -n "OK:"
fi
echo "$statestr | $perfdata"
exit $state
