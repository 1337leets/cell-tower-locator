#!/usr/bin/env python3
# =============================================================================
# trilaterate.py v2 - locate base stations from timing advance, and draw a map
#   input : cell_log.csv  (output of cell_logger.sh)
#   input : OpenCellID CSV for one country, optional
#   output: towers_map.html and a console summary
#
#   changes in v2:
#     - rows without TA or GPS (NaN) are dropped
#     - grouped per eNB, so the sectors of one mast are solved together
#     - says so when TA never changed, instead of returning a meaningless position
# OpenCelliD Project (CC-BY-SA) — https://opencellid.org/
# =============================================================================
import sys, math
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

TA_METERS  = 78.0
MIN_POINTS = 3
MIN_SPREAD = 150.0     # minimum spread between points (m)

OCID_COLS = ["radio","mcc","net","area","cell","unit","lon","lat",
             "range","samples","changeable","created","updated","avgSignal"]

def to_xy(lat, lon, lat0, lon0):
    R = 6371000.0
    return (math.radians(lon-lon0)*R*math.cos(math.radians(lat0)),
            math.radians(lat-lat0)*R)

def to_latlon(x, y, lat0, lon0):
    R = 6371000.0
    return (lat0 + math.degrees(y/R),
            lon0 + math.degrees(x/(R*math.cos(math.radians(lat0)))))

def spread_m(lats, lons):
    lat0, lon0 = lats[0], lons[0]
    xy = np.array([to_xy(la, lo, lat0, lon0) for la, lo in zip(lats, lons)])
    d = 0.0
    for i in range(len(xy)):
        for j in range(i+1, len(xy)):
            d = max(d, np.hypot(*(xy[i]-xy[j])))
    return d

def solve_tower(lats, lons, radii):
    lat0, lon0 = np.mean(lats), np.mean(lons)
    xy = np.array([to_xy(la, lo, lat0, lon0) for la, lo in zip(lats, lons)])
    xs, ys = xy[:,0], xy[:,1]
    rs = np.array(radii)
    p0 = np.array([xs[np.argmin(rs)], ys[np.argmin(rs)]])   # start at the closest measurement
    def resid(p):
        return np.sqrt((xs-p[0])**2 + (ys-p[1])**2) - rs
    sol = least_squares(resid, p0, method="lm")
    rms = float(np.sqrt(np.mean(resid(sol.x)**2)))
    lat, lon = to_latlon(sol.x[0], sol.x[1], lat0, lon0)
    return lat, lon, rms

def main():
    log_path  = sys.argv[1] if len(sys.argv) > 1 else "cell_log.csv"
    ocid_path = sys.argv[2] if len(sys.argv) > 2 else None

    df = pd.read_csv(log_path)
    n0 = len(df)
    df = df.dropna(subset=["lat","lon","ta"]).copy()      # <-- drop NaN rows
    df = df[df.ta >= 0]
    print(f"[+] {n0} rows read, {len(df)} valid (NaN or missing dropped)")

    ocid = None
    if ocid_path:
        ocid = pd.read_csv(ocid_path, header=None, names=OCID_COLS)
        print(f"[+] OpenCellID: {len(ocid)} cells")

    solved = []
    print("\n=== RESULTS (per eNB) ===")
    for enb, g in sorted(df.groupby("enb"), key=lambda kv: -len(kv[1])):
        lats = g.lat.values; lons = g.lon.values; tas = g.ta.values
        n = len(g)
        if n < MIN_POINTS:
            print(f"eNB {enb}: {n} points -> SKIPPED (too few, need >={MIN_POINTS})")
            continue
        if len(np.unique(tas)) == 1:
            print(f"eNB {enb}: {n} points -> SKIPPED (TA constant={int(tas[0])}, "
                  f"direction unknown, measurements from different DISTANCES needed)")
            continue
        sp = spread_m(lats, lons)
        if sp < MIN_SPREAD:
            print(f"eNB {enb}: {n} points -> SKIPPED (narrow spread {sp:.0f}m, "
                  f"need >={MIN_SPREAD:.0f}m)")
            continue
        lat, lon, rms = solve_tower(lats, lons, tas*TA_METERS)
        oc = ""
        if ocid is not None:
            for ci in g.ci.unique():
                hit = ocid[ocid.cell == ci]
                if len(hit):
                    olat, olon = hit.iloc[0].lat, hit.iloc[0].lon
                    dx, dy = to_xy(olat, olon, lat, lon)
                    oc = f" | OCID {olat:.5f},{olon:.5f} (off by {math.hypot(dx,dy):.0f}m)"
                    break
        print(f"eNB {enb}: {n} points, TA {int(tas.min())}-{int(tas.max())}, "
              f"spread {sp:.0f}m -> {lat:.6f},{lon:.6f} (rms {rms:.0f}m){oc}")
        solved.append((enb, n, lat, lon, rms))

    if solved:
        make_map(df, solved, ocid)
    else:
        print("\n[!] No mast could be solved. Needed: at least 3 points on the same eNB "
              "where TA CHANGES (move towards and away from it).")

def make_map(df, solved, ocid):
    import folium
    m = folium.Map(location=[df.lat.mean(), df.lon.mean()], zoom_start=14)
    for _, r in df.iterrows():
        folium.CircleMarker([r.lat, r.lon], radius=3, color="#1f77b4",
                            fill=True, fill_opacity=0.7,
                            popup=f"eNB{int(r.enb)} TA{int(r.ta)} RSRP{int(r.rsrp)}").add_to(m)
        if r.ta > 0:
            folium.Circle([r.lat, r.lon], radius=r.ta*TA_METERS, color="#1f77b4",
                          weight=1, fill=False, opacity=0.25).add_to(m)
    for enb, n, lat, lon, rms in solved:
        folium.Marker([lat, lon],
                      icon=folium.Icon(color="red", icon="tower-broadcast", prefix="fa"),
                      popup=f"<b>eNB {enb}</b><br>{n} points<br>rms {rms:.0f}m").add_to(m)
        folium.Circle([lat, lon], radius=max(rms,30), color="red",
                      weight=2, fill=True, fill_opacity=0.1).add_to(m)
    if ocid is not None:
        for enb, n, lat, lon, rms in solved:
            for ci in df[df.enb==enb].ci.unique():
                hit = ocid[ocid.cell==ci]
                if len(hit):
                    folium.Marker([hit.iloc[0].lat, hit.iloc[0].lon],
                                  icon=folium.Icon(color="green", icon="check", prefix="fa"),
                                  popup=f"OCID eNB {enb}").add_to(m)
                    break
    m.get_root().html.add_child(folium.Element(
        '<div style="position:fixed;bottom:8px;left:8px;z-index:9999;background:#fff;'
        'padding:4px 8px;font:12px sans-serif;border:1px solid #ccc">'
        'Data: OpenCelliD (CC-BY-SA) opencellid.org | red=estimate green=OCID blue=measurement</div>'))
    m.save("towers_map.html")
    print("\n[+] map: towers_map.html")

if __name__ == "__main__":
    main()
