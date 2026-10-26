#!/usr/bin/env python3
"""Write a synthetic cell_log.csv for trying the trilateration scripts.

All values are made up. Two imaginary masts stand in open sea, and a walk around
them records the timing advance a phone would see, with GPS noise added.
"""
import csv, math, random, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "sample_cell_log.csv"
rng = random.Random(7)
LAT0, LON0 = 34.0, 18.0                         # open sea, nowhere real
MASTS = [(1001, 0.004, 0.006), (1002, -0.006, -0.003)]   # eNB, offset from the walk centre in degrees

def metres(lat1, lon1, lat2, lon2):
    dy = (lat2 - lat1) * 111320
    dx = (lon2 - lon1) * 111320 * math.cos(math.radians(lat1))
    return math.hypot(dx, dy)

rows, t = [], 1700000000
for step in range(60):
    a = step / 60 * 2 * math.pi
    lat = LAT0 + 0.012 * math.sin(a) + rng.gauss(0, 0.00005)   # a loop of about 1.3 km radius
    lon = LON0 + 0.015 * math.cos(a) + rng.gauss(0, 0.00005)
    acc = round(rng.uniform(4, 15), 1)
    enb, dlat, dlon = min(MASTS, key=lambda m: metres(lat, lon, LAT0 + m[1], LON0 + m[2]))
    d = metres(lat, lon, LAT0 + dlat, LON0 + dlon)
    ta = max(0, round(d / 78 + rng.gauss(0, 0.4)))
    sector = 1 + int((math.degrees(math.atan2(lat - LAT0 - dlat, lon - LON0 - dlon)) + 180) // 120)
    ci = enb * 256 + sector
    rsrp = int(-60 - 25 * math.log10(max(d, 50) / 50) + rng.gauss(0, 3))
    rows.append([t, f"{lat:.6f}", f"{lon:.6f}", acc, ci, enb, sector, 100 + enb % 100, 40000, 20,
                 ta, ta * 78, rsrp, -10])
    t += 30

with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow("time,lat,lon,acc,ci,enb,sector,pci,tac,band,ta,dist_m,rsrp,rsrq".split(","))
    w.writerows(rows)
print(len(rows), "rows ->", OUT)
for enb, dlat, dlon in MASTS:
    print(f"  true position of eNB {enb}: {LAT0 + dlat:.6f},{LON0 + dlon:.6f}")
