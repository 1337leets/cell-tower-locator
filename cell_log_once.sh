#!/data/data/com.termux/files/usr/bin/bash
# cell_log_once.sh - appends one measurement row per run
CSV="$HOME/cell_log.csv"
[ -f "$CSV" ] || echo "time,lat,lon,acc,ci,enb,sector,pci,tac,band,ta,dist_m,rsrp,rsrq" > "$CSV"

LOC=$(termux-location -p gps 2>/dev/null)
LAT=$(echo "$LOC" | jq -r '.latitude')
LON=$(echo "$LOC" | jq -r '.longitude')
ACC=$(echo "$LOC" | jq -r '.accuracy')

# take only the registered (serving) cell
CELL=$(termux-telephony-cellinfo | jq -c '.[] | select(.registered==true)' | head -n1)
CI=$(echo "$CELL"  | jq -r '.ci')
PCI=$(echo "$CELL" | jq -r '.pci')
TAC=$(echo "$CELL" | jq -r '.tac')
BAND=$(echo "$CELL"| jq -r '.bands[0]')
TA=$(echo "$CELL"  | jq -r '.timing_advance')
RSRP=$(echo "$CELL"| jq -r '.rsrp')
RSRQ=$(echo "$CELL"| jq -r '.rsrq')

ENB=$(( CI >> 8 ))
SEC=$(( CI & 255 ))
DIST=$(( TA * 78 ))
NOW=$(date +%s)

echo "$NOW,$LAT,$LON,$ACC,$CI,$ENB,$SEC,$PCI,$TAC,$BAND,$TA,$DIST,$RSRP,$RSRQ" >> "$CSV"
echo "saved: eNB=$ENB sec=$SEC TA=$TA (~${DIST}m) RSRP=$RSRP @ $LAT,$LON ±${ACC}m"
