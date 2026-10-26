# Cell Tower Locator

Shell and Python scripts for an Android phone running Termux that log the LTE cell the phone is connected to
together with its GPS position, and then estimate where the base station is from the timing advance. I wanted to
find out how close a phone can get to the real mast position with nothing but its own radio measurements, and to
check the result against OpenCellID.

No real measurements are included in this repository. The sample in `examples/` is synthetic.

## Scripts

| File | What it does |
|---|---|
| `cell_logger.sh` | Logs the serving cell every 15 s to `~/cell_log.csv` while it runs |
| `cell_log_once.sh` | Appends a single measurement, for use from a shortcut or Tasker |
| `trilaterate.py` | Estimates mast positions with numpy and scipy, draws a folium map |
| `trilaterate_nodep.py` | The same estimate in plain Python with a hand-written solver, draws a Leaflet map |
| `signal_align.sh` | Live RSRP meter with a bar, for pointing an antenna or a phone at the mast |

## Requirements

- Termux and the Termux:API app, with location and phone permissions
- `pkg install termux-api jq python`
- For `trilaterate.py` only, `pip install numpy pandas scipy folium`

## Usage

```bash
./cell_logger.sh                         # walk or drive around, Ctrl+C to stop
python trilaterate_nodep.py cell_log.csv
python trilaterate_nodep.py cell_log.csv opencellid.csv    # also compare with OpenCellID
termux-open towers_map.html
```

With the synthetic log in `examples/` the output is

```
$ python examples/make_sample_log.py sample_cell_log.csv
60 rows -> sample_cell_log.csv
  true position of eNB 1001: 34.004000,18.006000
  true position of eNB 1002: 33.994000,17.997000
$ python trilaterate_nodep.py sample_cell_log.csv
[+] 60 valid measurements (NaN or missing dropped)

=== RESULTS (per eNB) ===
eNB 1001: 30 points, TA 8-22, spread 2727m -> 34.003980,18.005979 (rms 39m)
eNB 1002: 30 points, TA 8-21, spread 2717m -> 33.994126,17.997074 (rms 38m)
```

`trilaterate.py` prints the same positions for this file. On synthetic data the error is a few metres because the
simulated timing advance has little noise. Real measurements are much worse, see Limitations.

`signal_align.sh` prints one line that updates every second and vibrates when a new best RSRP is reached. The line
below shows the format with made-up values.

```
RSRP  -97 [###############               ] fair      | RSRQ -11 | TA 12 | eNB 1001   B20 | peak  -95
```

## How it works

### Logging

`cell_logger.sh` reads a GPS fix with `termux-location` and the registered cell with `termux-telephony-cellinfo`.
Fixes with an accuracy worse than 25 m are skipped, and the same cell is not logged again until the phone has moved
at least 30 m. Each row holds the cell identity (`ci`), and from it the eNB (`ci >> 8`) and the sector (`ci & 255`),
plus PCI, TAC, band, timing advance, RSRP and RSRQ. It keeps a wake lock so Android does not stop it with the
screen off.

### From timing advance to distance

In LTE the timing advance tells the phone how early to transmit so that its signal arrives on time at the base
station. One TA step is about 78 m of distance, so `TA * 78` is a rough radius around the phone on which the mast
must lie.

### Solving for the mast

All rows of one eNB are grouped together, because the sectors of a site are on the same mast. The positions are
converted to metres on a local flat plane, and the scripts look for the point whose distances to all measurement
positions best match their TA radii, in the least squares sense. `trilaterate.py` uses scipy's Levenberg-Marquardt
solver and `trilaterate_nodep.py` runs its own Gauss-Newton iteration with a small damping term, starting from the
measurement with the smallest radius.

An eNB is skipped if it has fewer than three points, if all points are within 150 m of each other, or if the TA
never changed. With a constant TA all circles have the same radius and the direction of the mast cannot be found,
so the script says so instead of printing a meaningless position.

### OpenCellID

If a second argument is given, it is read as an OpenCellID CSV export (no header, columns radio, mcc, net, area,
cell, unit, lon, lat and so on). For every solved eNB the matching cell is looked up and the distance between the
estimate and the OpenCellID position is printed and drawn in green. OpenCellID data is CC-BY-SA and needs a free
account, so download your own export from <https://opencellid.org/> and keep the access token out of the
repository.

## Limitations

- A TA step is about 78 m, so a single measurement is only good to that much. Rows where the phone reported no TA are dropped.
- `termux-telephony-cellinfo` returns different fields on different phones and Android versions. The scripts expect
  LTE fields (`ci`, `pci`, `tac`, `timing_advance`, `rsrp`, `rsrq`).
- The flat-plane conversion is fine for a few kilometres around the measurements, not for much larger areas.
- Walking along a straight road away from the mast leaves the estimate mirrored across the road. Measurements from
  several sides of the mast are needed.

## Privacy

`cell_log.csv` is a GPS track of where you have been, tied to the cells of your operator. Keep it private.
