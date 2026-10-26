#!/data/data/com.termux/files/usr/bin/bash
# =============================================================================
# signal_align.sh - live signal monitor for aligning an antenna
#   turn the antenna slowly and catch the RSRP peak. A new peak vibrates the phone.
#   quit: Ctrl+C
# =============================================================================
INTERVAL=1            # seconds
BEST=-999            # best RSRP seen so far
BEST_TA=""

# RSRP -> bar (-120 bad .. -75 excellent)
bar() {
  local v=$1 n
  n=$(( (v + 120) * 30 / 45 ))       # -120..-75  ->  0..30
  [ "$n" -lt 0 ] && n=0; [ "$n" -gt 30 ] && n=30
  printf '['
  for ((i=0;i<30;i++)); do [ "$i" -lt "$n" ] && printf '#' || printf ' '; done
  printf ']'
}

# RSRP quality label
label() {
  local v=$1
  if   [ "$v" -ge -85  ]; then echo "EXCELLENT"
  elif [ "$v" -ge -95  ]; then echo "good"
  elif [ "$v" -ge -105 ]; then echo "fair"
  elif [ "$v" -ge -115 ]; then echo "weak"
  else echo "VERY WEAK"; fi
}

trap 'echo; echo "Best RSRP: $BEST dBm (TA=$BEST_TA)"; exit' INT TERM
clear
echo "Turn the antenna slowly and stop at the highest RSRP. (Ctrl+C = quit)"
echo

while true; do
  C=$(termux-telephony-cellinfo 2>/dev/null | jq -c '.[] | select(.registered==true)' | head -n1)
  if [ -z "$C" ]; then echo -ne "\r(no registered cell)       "; sleep "$INTERVAL"; continue; fi
  RSRP=$(echo "$C"|jq -r '.rsrp'); RSRQ=$(echo "$C"|jq -r '.rsrq')
  TA=$(echo "$C"|jq -r '.timing_advance'); PCI=$(echo "$C"|jq -r '.pci')
  ENB=$(( $(echo "$C"|jq -r '.ci') >> 8 )); BAND=$(echo "$C"|jq -r '.bands[0]')

  # new peak?
  NEW=""
  if [ "$RSRP" -gt "$BEST" ]; then
    BEST=$RSRP; BEST_TA=$TA; NEW=" <== NEW PEAK"
    termux-vibrate -d 120 2>/dev/null
  fi

  printf "\rRSRP %4d %s %-9s | RSRQ %3d | TA %2s | eNB %-6s B%s | peak %4d%s   " \
    "$RSRP" "$(bar "$RSRP")" "$(label "$RSRP")" "$RSRQ" "$TA" "$ENB" "$BAND" "$BEST" "$NEW"
  sleep "$INTERVAL"
done
