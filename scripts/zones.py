"""Non-uniform pitch zones: coarse at the back, fine in the attacking box.

The 101x101 grid is finer than the data deserves and treats a metre near the
own corner flag as seriously as a metre on the penalty spot.  These zones do
the opposite: they get smaller the closer you get to the goal being attacked,
so two strikers are compared on where they are inside the box, while two
centre-backs are not split apart by noise in their own half.

Attacking direction is left -> right (+x).  y = 0 is the player's RIGHT
touchline, matching the raw data and the viewer.

Run from the repo root:  python3 scripts/zones.py   ->  heatmap_viewer/zones.html
"""
import os

PITCH_W, PITCH_H = 105.0, 68.0  # metres
GRID = 101                      # data coords are 0-100 inclusive

# Column edges along the pitch.  They get shorter towards the attacked goal and
# land on real markings: 16.5 box, 52.5 halfway, 88.5 box, 99.5 six-yard line.
COLUMN_EDGES = [0, 16.5, 35, 52.5, 63, 72, 80.5, 88.5, 94, 99.5, 105]

# How wide the lateral bands are depends on the tier the column falls in.
TIERS = [
    # name          ends at x   band edges (y, metres)                                     band codes
    ("defensive", 35.0,  [0, 24.84, 43.16, 68],                          ["R", "C", "L"]),
    ("middle",    72.0,  [0, 13.84, 24.84, 43.16, 54.16, 68],            ["R", "RH", "C", "LH", "L"]),
    ("attacking", 105.0, [0, 13.84, 24.84, 34, 43.16, 54.16, 68],        ["R", "RH", "RC", "LC", "LH", "L"]),
]
# 13.84 / 54.16 are the penalty-box edges, 24.84 / 43.16 the six-yard-box edges.

TIER_CODE = {"defensive": "D", "middle": "M", "attacking": "A"}
BAND_NAMES = {
    "R": "right", "L": "left", "C": "centre",
    "RH": "right half-space", "LH": "left half-space",
    "RC": "right centre", "LC": "left centre",
}


def tier_for(x_end):
    """The tier a column belongs to, chosen by where the column ends."""
    for tier in TIERS:
        if x_end <= tier[1] + 1e-9:
            return tier
    raise ValueError(x_end)


def build_zones():
    """Every zone, in a fixed order.  The index is the position in the feature vector."""
    zones = []
    tier_col_no = {}
    for x0, x1 in zip(COLUMN_EDGES, COLUMN_EDGES[1:]):
        tier_name, _, band_edges, band_codes = tier_for(x1)
        col_no = tier_col_no[tier_name] = tier_col_no.get(tier_name, 0) + 1
        col_code = f"{TIER_CODE[tier_name]}{col_no}"
        for (y0, y1), band in zip(zip(band_edges, band_edges[1:]), band_codes):
            zones.append({
                "index": len(zones),
                "name": f"{col_code}-{band}",
                "tier": tier_name,
                "x0": x0, "x1": x1, "y0": y0, "y1": y1,
                "area": (x1 - x0) * (y1 - y0),
            })
    return zones


ZONES = build_zones()


def zone_of(x_m, y_m):
    """Index of the zone containing a point in metres (edges belong to the lower zone)."""
    for z in ZONES:
        if z["x0"] <= x_m < z["x1"] and z["y0"] <= y_m < z["y1"]:
            return z["index"]
    return ZONES[-1]["index"] if x_m >= PITCH_W or y_m >= PITCH_H else None


def grid_zone_map():
    """101x101 array [x, y] -> zone index, so a raw grid can be summed into zones."""
    import numpy as np
    out = np.empty((GRID, GRID), dtype=np.int16)
    for gx in range(GRID):
        x_m = min((gx + 0.5) / GRID * PITCH_W, PITCH_W - 1e-6)
        for gy in range(GRID):
            # data y runs from the right touchline up to the left one
            y_m = min((gy + 0.5) / GRID * PITCH_H, PITCH_H - 1e-6)
            out[gx, gy] = zone_of(x_m, y_m)
    return out


# --- visualisation -----------------------------------------------------------

OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "heatmap_viewer", "zones.html")

TIER_FILL = {"defensive": "#2f6fd0", "middle": "#f2b53a", "attacking": "#e3342f"}
TIER_BLURB = {
    "defensive": "broad blocks, wings merged into the centre",
    "middle": "wings and half-spaces split out",
    "attacking": "finest; centre split down the middle, box sliced every 5.5 m",
}


def svg_pitch_lines():
    """The same markings the viewer draws, laid over the zones."""
    mid = PITCH_H / 2
    dy = (9.15 ** 2 - 5.5 ** 2) ** 0.5
    out = [
        f'<rect x="0" y="0" width="{PITCH_W:g}" height="{PITCH_H:g}" rx="1.5"/>',
        f'<line x1="{PITCH_W / 2:g}" y1="0" x2="{PITCH_W / 2:g}" y2="{PITCH_H:g}"/>',
        f'<circle cx="{PITCH_W / 2:g}" cy="{mid:g}" r="9.15"/>',
    ]
    for side in (0, 1):
        x = lambda d: PITCH_W - d if side else d
        for depth, width in ((16.5, 40.32), (5.5, 18.32)):
            out.append(f'<rect x="{min(x(0), x(depth)):g}" y="{mid - width / 2:g}" '
                       f'width="{depth:g}" height="{width:g}"/>')
        out.append(f'<path d="M {x(16.5):g} {mid - dy:g} A 9.15 9.15 0 0 {0 if side else 1} '
                   f'{x(16.5):g} {mid + dy:g}"/>')
    return "\n    ".join(out)


def svg_zones():
    """Zone rectangles plus a two-line label, shrunk to fit the narrow attacking cells."""
    cells, labels = [], []
    for z in ZONES:
        w, h = z["x1"] - z["x0"], z["y1"] - z["y0"]
        # y = 0 is the player's right touchline, which the viewer draws at the bottom
        top = PITCH_H - z["y1"]
        cells.append(
            f'<rect class="zone t-{z["tier"]}" x="{z["x0"]:g}" y="{top:g}" width="{w:g}" height="{h:g}">'
            f'<title>{z["index"]} · {z["name"]} · {w:g} × {h:g} m = {z["area"]:.0f} m²</title></rect>')

        area = f'{z["area"]:.0f} m²'
        # ~0.68 em per character for this font at weight 600
        size = min(2.2, h * 0.3, w * 0.9 / (len(z["name"]) * 0.68))
        cx, cy = z["x0"] + w / 2, top + h / 2
        labels.append(
            f'<text class="zlabel" x="{cx:g}" y="{cy - size * 0.55:.2f}" font-size="{size:.2f}">'
            f'{z["name"]}</text>'
            f'<text class="zlabel l-area" x="{cx:g}" y="{cy + size * 0.7:.2f}" '
            f'font-size="{size * 0.85:.2f}">{area}</text>')
    return "\n    ".join(cells), "\n    ".join(labels)


def summary_rows():
    rows = []
    for tier_name, _, _, band_codes in TIERS:
        zs = [z for z in ZONES if z["tier"] == tier_name]
        cols = sorted({(z["x0"], z["x1"]) for z in zs})
        depths = " / ".join(f"{b - a:g}" for a, b in cols)
        rows.append(
            f'<tr><td><span class="dot" style="background:{TIER_FILL[tier_name]}"></span>'
            f'{tier_name.title()}</td><td>{cols[0][0]:g}–{cols[-1][1]:g} m</td>'
            f'<td>{len(cols)} × {len(band_codes)} = {len(zs)}</td><td>{depths} m</td>'
            f'<td>{min(z["area"] for z in zs):.0f}–{max(z["area"] for z in zs):.0f} m²</td>'
            f'<td>{TIER_BLURB[tier_name]}</td></tr>')
    return "\n        ".join(rows)


def render():
    from string import Template
    cells, labels = svg_zones()
    html = Template(HTML).substitute(
        zones=cells, labels=labels, lines=svg_pitch_lines(), rows=summary_rows(),
        total=len(ZONES),
        smallest=f"{min(z['area'] for z in ZONES):.0f}",
        largest=f"{max(z['area'] for z in ZONES):.0f}",
        ratio=f"{max(z['area'] for z in ZONES) / min(z['area'] for z in ZONES):.1f}",
    )
    with open(OUT_FILE, "w") as f:
        f.write(html)
    return os.path.normpath(OUT_FILE)


HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pitch zones</title>
<style>
  :root { --bg:#111; --panel:#1c1c1c; --border:#2c2c2c; --text:#ececec; --muted:#8c8c8c; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text); padding:24px 16px;
         font:14px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  main { max-width:1100px; margin:0 auto; }
  h1 { font-size:20px; margin:0 0 4px; font-weight:600; }
  .sub { color:var(--muted); margin:0 0 20px; }
  .card { background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:16px; }
  .head { display:flex; flex-wrap:wrap; gap:12px; align-items:center; justify-content:space-between; margin-bottom:12px; }
  .toggles { display:flex; gap:16px; color:var(--muted); font-size:12px; }
  .toggles label { display:flex; gap:6px; align-items:center; cursor:pointer; }
  .pitch-wrap { overflow-x:auto; }
  svg.pitch { display:block; width:100%; min-width:640px; height:auto; }
  .zone { stroke:rgba(255,255,255,.35); stroke-width:.12; }
  .t-defensive { fill:#2f6fd0; fill-opacity:.18; }
  .t-middle    { fill:#f2b53a; fill-opacity:.18; }
  .t-attacking { fill:#e3342f; fill-opacity:.2; }
  .zone:hover  { fill-opacity:.45; }
  .lines { fill:none; stroke:rgba(255,255,255,.45); stroke-width:.3; }
  .zlabel { fill:#fff; text-anchor:middle; dominant-baseline:middle; font-family:inherit;
            pointer-events:none; font-weight:600; }
  .l-area { fill:rgba(255,255,255,.55); font-weight:400; }
  body.no-labels .zlabel, body.no-areas .l-area { display:none; }
  .direction { text-align:center; color:var(--muted); font-size:12px; margin-top:6px; }
  table { border-collapse:collapse; width:100%; margin-top:16px; font-size:13px; }
  th, td { text-align:left; padding:7px 10px; border-bottom:1px solid var(--border); }
  th { color:var(--muted); font-weight:500; font-size:12px; }
  .dot { display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:7px; vertical-align:-1px; }
  .notes { color:var(--muted); font-size:13px; margin-top:14px; }
  .notes li { margin-bottom:5px; }
  code { background:#242424; border-radius:4px; padding:1px 5px; }
</style>
</head>
<body>
<main>
  <h1>Pitch zones for heatmap comparison</h1>
  <p class="sub">$total zones. They shrink towards the goal being attacked, from
     $largest m² at the back to $smallest m² in the box — ${ratio}× more precision where it matters.</p>

  <div class="card">
    <div class="head">
      <div class="toggles">
        <label><input type="checkbox" id="labels" checked> Zone names</label>
        <label><input type="checkbox" id="areas" checked> Areas</label>
      </div>
      <div style="color:var(--muted);font-size:12px">Hover a zone for its size</div>
    </div>
    <div class="pitch-wrap">
      <svg class="pitch" viewBox="-2 -2 109 72" xmlns="http://www.w3.org/2000/svg">
    $zones
    <g class="lines">
    $lines
    </g>
    $labels
      </svg>
    </div>
    <div class="direction">Attacking direction → · left touchline at the top, matching the viewer</div>

    <table>
      <thead><tr><th>Tier</th><th>Along the pitch</th><th>Columns × bands</th>
                 <th>Column depths</th><th>Zone size</th><th>Why</th></tr></thead>
      <tbody>
        $rows
      </tbody>
    </table>

    <ul class="notes">
      <li>Column edges sit on real markings: <code>16.5</code> own box, <code>52.5</code> halfway,
          <code>88.5</code> opposition box, <code>99.5</code> six-yard line.</li>
      <li>Band edges are the box widths: <code>13.84 / 54.16</code> penalty box,
          <code>24.84 / 43.16</code> six-yard box, so bands read as wing, half-space and centre.</li>
      <li>Bands nest: every defensive edge is also a middle edge, and every middle edge is also an
          attacking edge, so a zone never straddles a coarser one.</li>
    </ul>
  </div>
</main>
<script>
  for (const [id, cls] of [["labels", "no-labels"], ["areas", "no-areas"]]) {
    const box = document.getElementById(id);
    box.addEventListener("change", () => document.body.classList.toggle(cls, !box.checked));
  }
</script>
</body>
</html>
"""


if __name__ == "__main__":
    path = render()
    print(f"{len(ZONES)} zones -> {path}")
