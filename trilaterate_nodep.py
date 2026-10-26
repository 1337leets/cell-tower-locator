#!/usr/bin/env python3
# =============================================================================
# trilaterate_nodep.py - PLAIN PYTHON (no numpy, scipy, pandas or folium)
#   locate base stations from timing advance, and draw a Leaflet map
#   input : cell_log.csv   (output of cell_logger.sh)
#   input : OpenCellID CSV, optional
#   output: towers_map.html
#
#   least squares: hand-written Gauss-Newton, 2x2 solve, light LM damping
# OpenCelliD Project (CC-BY-SA) — https://opencellid.org/
# =============================================================================
import sys, csv, math, json

TA_METERS  = 78.0
MIN_POINTS = 3
MIN_SPREAD = 150.0

def to_xy(lat, lon, lat0, lon0):
    R = 6371000.0
    return (math.radians(lon-lon0)*R*math.cos(math.radians(lat0)),
            math.radians(lat-lat0)*R)

def to_latlon(x, y, lat0, lon0):
    R = 6371000.0
    return (lat0 + math.degrees(y/R),
            lon0 + math.degrees(x/(R*math.cos(math.radians(lat0)))))

def fnum(s):
    try:
        v = float(s)
        return v if v == v else None      # NaN -> None
    except (TypeError, ValueError):
        return None

def spread_m(pts):
    d = 0.0
    for i in range(len(pts)):
        for j in range(i+1, len(pts)):
            dx = pts[i][0]-pts[j][0]; dy = pts[i][1]-pts[j][1]
            d = max(d, math.hypot(dx, dy))
    return d

def solve_tower(xy, radii):
    # start at the measurement with the smallest radius
    i0 = min(range(len(radii)), key=lambda i: radii[i])
    px, py = xy[i0]
    lam = 1e-3
    for _ in range(60):
        a=b=d=0.0; gx=gy=0.0; cost=0.0
        for (xi,yi), ri in zip(xy, radii):
            dist = math.hypot(px-xi, py-yi) or 1e-9
            r = dist - ri                       # residual
            jx = (px-xi)/dist; jy = (py-yi)/dist
            a += jx*jx; b += jx*jy; d += jy*jy   # J^T J
            gx += jx*r;  gy += jy*r              # J^T r
            cost += r*r
        # LM damping
        A = a+lam; D = d+lam
        det = A*D - b*b
        if abs(det) < 1e-12: break
        dx = -( D*gx - b*gy)/det
        dy = -(-b*gx + A*gy)/det
        px += dx; py += dy
        if math.hypot(dx,dy) < 1e-4: break
    # rms
    ss = 0.0
    for (xi,yi), ri in zip(xy, radii):
        ss += (math.hypot(px-xi,py-yi) - ri)**2
    return px, py, math.sqrt(ss/len(radii))

def load_log(path):
    rows=[]
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            lat=fnum(row.get('lat')); lon=fnum(row.get('lon')); ta=fnum(row.get('ta'))
            if None in (lat,lon,ta) or ta < 0: continue
            rows.append(dict(lat=lat, lon=lon, ta=ta,
                             ci=int(float(row['ci'])), enb=int(float(row['enb'])),
                             rsrp=fnum(row.get('rsrp')) or 0))
    return rows

def load_ocid(path):
    cols=["radio","mcc","net","area","cell","unit","lon","lat","range",
          "samples","changeable","created","updated","avgSignal"]
    by_cell={}
    with open(path, newline='') as f:
        for row in csv.reader(f):
            if len(row)<8: continue
            try: by_cell[int(row[4])] = (float(row[7]), float(row[6]))  # cell -> (lat,lon)
            except ValueError: continue
    return by_cell

def main():
    log_path  = sys.argv[1] if len(sys.argv)>1 else "cell_log.csv"
    ocid_path = sys.argv[2] if len(sys.argv)>2 else None
    rows = load_log(log_path)
    print(f"[+] {len(rows)} valid measurements (NaN or missing dropped)")
    ocid = load_ocid(ocid_path) if ocid_path else {}
    if ocid: print(f"[+] OpenCellID: {len(ocid)} cells")

    # group per eNB
    groups={}
    for r in rows: groups.setdefault(r['enb'], []).append(r)

    solved=[]
    print("\n=== RESULTS (per eNB) ===")
    for enb, g in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        tas=[r['ta'] for r in g]; n=len(g)
        if n < MIN_POINTS:
            print(f"eNB {enb}: {n} points -> SKIPPED (too few, need >={MIN_POINTS})"); continue
        if len(set(tas))==1:
            print(f"eNB {enb}: {n} points -> SKIPPED (TA constant={int(tas[0])}, direction unknown, "
                  f"measurements from different DISTANCES needed)"); continue
        lat0=sum(r['lat'] for r in g)/n; lon0=sum(r['lon'] for r in g)/n
        xy=[to_xy(r['lat'],r['lon'],lat0,lon0) for r in g]
        sp=spread_m(xy)
        if sp < MIN_SPREAD:
            print(f"eNB {enb}: {n} points -> SKIPPED (narrow spread {sp:.0f}m, need >={MIN_SPREAD:.0f}m)"); continue
        radii=[r['ta']*TA_METERS for r in g]
        tx,ty,rms=solve_tower(xy,radii)
        tlat,tlon=to_latlon(tx,ty,lat0,lon0)
        oc=""
        for ci in {r['ci'] for r in g}:
            if ci in ocid:
                olat,olon=ocid[ci]; ox,oy=to_xy(olat,olon,tlat,tlon)
                oc=f" | OCID {olat:.5f},{olon:.5f} (off by {math.hypot(ox,oy):.0f}m)"; break
        print(f"eNB {enb}: {n} points, TA {int(min(tas))}-{int(max(tas))}, spread {sp:.0f}m "
              f"-> {tlat:.6f},{tlon:.6f} (rms {rms:.0f}m){oc}")
        solved.append(dict(enb=enb,n=n,lat=tlat,lon=tlon,rms=rms))

    if solved:
        write_map(rows, solved, ocid)
    else:
        print("\n[!] No mast could be solved. Needed: at least 3 points on the same eNB "
              "where TA CHANGES (move towards and away from it).")

def write_map(rows, solved, ocid):
    clat=sum(r['lat'] for r in rows)/len(rows)
    clon=sum(r['lon'] for r in rows)/len(rows)
    meas=[[r['lat'],r['lon'],r['enb'],int(r['ta']),int(r['rsrp']),r['ta']*TA_METERS] for r in rows]
    tw=[[s['lat'],s['lon'],s['enb'],s['n'],round(s['rms'])] for s in solved]
    oc=[]
    for s in solved:
        for r in rows:
            if r['enb']==s['enb'] and r['ci'] in ocid:
                oc.append([*ocid[r['ci']], s['enb']]); break
    html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>html,body,#map{height:100%;margin:0}#att{position:fixed;bottom:4px;left:4px;z-index:9999;background:#fff;padding:3px 6px;font:12px sans-serif}</style>
</head><body><div id="map"></div><div id="att">Data: OpenCelliD (CC-BY-SA) opencellid.org | red=estimate green=OCID blue=measurement</div>
<script>
var map=L.map('map').setView([%CLAT%,%CLON%],14);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap'}).addTo(map);
var meas=%MEAS%, tw=%TW%, oc=%OC%;
meas.forEach(function(m){
  L.circleMarker([m[0],m[1]],{radius:4,color:'#1f77b4',fillOpacity:.7})
   .bindPopup('eNB'+m[2]+' TA'+m[3]+' RSRP'+m[4]).addTo(map);
  if(m[3]>0) L.circle([m[0],m[1]],{radius:m[5],color:'#1f77b4',weight:1,fill:false,opacity:.25}).addTo(map);
});
tw.forEach(function(t){
  L.marker([t[0],t[1]]).bindPopup('<b>eNB '+t[2]+'</b><br>'+t[3]+' points<br>rms '+t[4]+'m').addTo(map);
  L.circle([t[0],t[1]],{radius:Math.max(t[4],30),color:'red',weight:2,fillOpacity:.1}).addTo(map);
});
oc.forEach(function(o){
  L.circleMarker([o[0],o[1]],{radius:6,color:'green',fillOpacity:.8}).bindPopup('OCID eNB '+o[2]).addTo(map);
});
</script></body></html>"""
    html=(html.replace("%CLAT%",str(clat)).replace("%CLON%",str(clon))
              .replace("%MEAS%",json.dumps(meas)).replace("%TW%",json.dumps(tw))
              .replace("%OC%",json.dumps(oc)))
    with open("towers_map.html","w") as f: f.write(html)
    print("\n[+] map: towers_map.html (open it in a browser)")

if __name__=="__main__":
    main()
