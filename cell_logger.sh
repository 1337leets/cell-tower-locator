#!/data/data/com.termux/files/usr/bin/bash
# cell_logger.sh - continuous background logger
CSV="$HOME/cell_log.csv"
INTERVAL=15          # seconds
MAX_ACC=25           # metres, skip GPS fixes worse than this
MOVE_MIN=30          # metres, do not log the same cell again until we moved this far

[ -f "$CSV" ] || echo "time,lat,lon,acc,ci,enb,sector,pci,tac,band,ta,dist_m,rsrp,rsrq" > "$CSV"

termux-wake-lock                       # keep the CPU awake
trap 'termux-wake-unlock; exit' INT TERM

PREV_CI=""; PREV_LAT=""; PREV_LON=""

# haversine distance between two points in metres
dist() { awk -v a=$1 -v b=$2 -v c=$3 -v d=$4 'BEGIN{
  r=6371000; p=atan2(0,-1)/180;
  dl=(c-a)*p; do_=(d-b)*p;
  h=sin(dl/2)^2 + cos(a*p)*cos(c*p)*sin(do_/2)^2;
  print r*2*atan2(sqrt(h),sqrt(1-h))}'; }

while true; do
  LOC=$(termux-location -p gps 2>/dev/null)
  LAT=$(echo "$LOC" | jq -r '.latitude // empty')
  ACC=$(echo "$LOC" | jq -r '.accuracy // empty')
  LON=$(echo "$LOC" | jq -r '.longitude // empty')

  # skip when there is no GPS fix or it is poor
  if [ -z "$LAT" ] || [ "$(awk -v a=$ACC -v m=$MAX_ACC 'BEGIN{print (a>m)}')" = "1" ]; then
    sleep "$INTERVAL"; continue
  fi

  CELL=$(termux-telephony-cellinfo | jq -c '.[] | select(.registered==true)' | head -n1)
  [ -z "$CELL" ] && { sleep "$INTERVAL"; continue; }

  CI=$(echo "$CELL"|jq -r '.ci'); PCI=$(echo "$CELL"|jq -r '.pci')
  TAC=$(echo "$CELL"|jq -r '.tac'); BAND=$(echo "$CELL"|jq -r '.bands[0]')
  TA=$(echo "$CELL"|jq -r '.timing_advance'); RSRP=$(echo "$CELL"|jq -r '.rsrp')
  RSRQ=$(echo "$CELL"|jq -r '.rsrq')

  # same cell and hardly moved, skip
  if [ "$CI" = "$PREV_CI" ] && [ -n "$PREV_LAT" ]; then
    D=$(dist "$PREV_LAT" "$PREV_LON" "$LAT" "$LON")
    [ "$(awk -v d=$D -v m=$MOVE_MIN 'BEGIN{print (d<m)}')" = "1" ] && { sleep "$INTERVAL"; continue; }
  fi

  ENB=$((CI>>8)); SEC=$((CI&255)); DIST=$((TA*78)); NOW=$(date +%s)
  echo "$NOW,$LAT,$LON,$ACC,$CI,$ENB,$SEC,$PCI,$TAC,$BAND,$TA,$DIST,$RSRP,$RSRQ" >> "$CSV"
  echo "[$(date +%H:%M:%S)] eNB=$ENB sec=$SEC TA=$TA (~${DIST}m) RSRP=$RSRP acc=${ACC}m"
  PREV_CI=$CI; PREV_LAT=$LAT; PREV_LON=$LON
  sleep "$INTERVAL"
done
