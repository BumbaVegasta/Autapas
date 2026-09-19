"""Pitch zones for heatmap comparison, mirrored left/right and coarsened at the back.

Columns run the length of the pitch (x): the defensive half is 3 equal 17.5 m
columns, a 4th 17.5 m column sits right at the start of the attacking half, and
the rest of the pitch is 6 equal columns -- the closer to goal, the more of
them a heatmap needs to place a player accurately.

Every column has the same 3 lateral bands (y), not 5: a player's left and
right sides are folded together before comparing, because which flank a
winger favours isn't the question -- how central or wide he plays is. So a
column contributes a wing share (both touchlines), a half-space share (both
half-spaces) and a centre share, not five separate numbers.

The defensive tier is coarsened all the way: its 3 columns x 3 bands collapse
into a single zone. Defenders' heatmaps are dominated by which third and side
of their own half they cover, not by centimetre-level shape back there, and
folding it into one zone stops it from crowding out the attacking detail the
comparison actually cares about.

Attacking direction is left -> right (+x).  y = 0 is the player's RIGHT
touchline, matching the raw data and the viewer.

Run from the repo root:  python3 scripts/zones.py   ->  heatmap_viewer/zones.html
"""
import os

PITCH_W, PITCH_H = 105.0, 68.0  # metres
GRID = 101                      # data coords are 0-100 inclusive

# Columns along the pitch. The defensive half (0-52.5) is 3 equal columns; a
# 4th, the same width, starts right at the halfway line; the rest of the
# pitch (52.5 more columns worth of narrowing) shrinks fastest going forward.
N_ATTACK = 6
_D_W = 52.5 / 3        # 17.5 m
_A_W = 35.0 / N_ATTACK  # 5.833 m

COLUMNS = [
    ("D1", 0 * _D_W, 1 * _D_W, "defensive"),
    ("D2", 1 * _D_W, 2 * _D_W, "defensive"),
    ("D3", 2 * _D_W, 3 * _D_W, "defensive"),
    ("M1", 3 * _D_W, 3 * _D_W + _D_W, "middle"),
] + [
    (f"A{i + 1}", 70.0 + i * _A_W, 70.0 + (i + 1) * _A_W, "attacking")
    for i in range(N_ATTACK)
]

# Lateral bands, the same for every column -- edges on the real box markings
# (13.84/54.16 penalty box, matching the project's long-standing numbers) --
# but pulled in 1 m each side from the original 24.84/43.16 six-yard-box
# edges, so the centre band reads a bit wider and the half-spaces a bit
# narrower than the pure box geometry.
BAND_EDGES = [0, 13.84, 23.84, 44.16, 54.16, 68]
# (band name, the bucket it mirrors into) -- R and L both feed "RL", RH and
# LH both feed "H"; a column ends up with 3 features, not 5.
BANDS = [("R", "RL"), ("RH", "H"), ("C", "C"), ("LH", "H"), ("L", "RL")]

TIER_CODE = {"defensive": "D", "middle": "M", "attacking": "A"}
TIER_FILL = {"defensive": "#2f6fd0", "middle": "#f2b53a", "attacking": "#e3342f"}
TIER_BLURB = {
    "defensive": "one zone for the whole defensive third, both sides folded in",
    "middle": "the transition column right after halfway, mirrored L/R",
    "attacking": "6 columns, each mirrored L/R -- finest where shots come from",
}


def build_zones():
    """Every physical rectangle the grid can land in (`ZONES`), and the
    coarser buckets the similarity maths actually compares (`GROUPS`).

    A defensive rectangle's group is "D-ALL", shared by all 3 defensive
    columns and all 3 bands. Everywhere else the group is "<column>-<bucket>",
    e.g. "A1-H" for A1's two half-space bands -- mirrored, not merged further.
    """
    zones = []
    for col, x0, x1, tier in COLUMNS:
        for (y0, y1), (band, bucket) in zip(zip(BAND_EDGES, BAND_EDGES[1:]), BANDS):
            group = "D-ALL" if tier == "defensive" else f"{col}-{bucket}"
            zones.append({
                "name": f"{col}-{band}", "group": group, "tier": tier,
                "col": col, "band": band, "bucket": bucket,
                "x0": x0, "x1": x1, "y0": y0, "y1": y1,
                "area": (x1 - x0) * (y1 - y0),
            })

    group_order, group_area, group_tier = [], {}, {}
    for z in zones:
        g = z["group"]
        if g not in group_area:
            group_order.append(g)
            group_area[g] = 0.0
            group_tier[g] = z["tier"]
        group_area[g] += z["area"]
    group_index = {g: i for i, g in enumerate(group_order)}
    for z in zones:
        z["index"] = group_index[z["group"]]

    groups = [{"name": g, "index": group_index[g], "tier": group_tier[g], "area": group_area[g]}
              for g in group_order]
    return zones, groups


ZONES, GROUPS = build_zones()


def zone_of(x_m, y_m):
    """Model-group index (0..len(GROUPS)-1) for a point in metres."""
    for z in ZONES:
        if z["x0"] <= x_m < z["x1"] and z["y0"] <= y_m < z["y1"]:
            return z["index"]
    return ZONES[-1]["index"] if x_m >= PITCH_W or y_m >= PITCH_H else None


def grid_zone_map():
    """101x101 array [x, y] -> model-group index, so a raw grid can be summed
    straight into GROUPS."""
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
    """Zone rectangles plus a two-line label per group, one label even when a
    group covers several rectangles (the defensive block, the mirrored pairs)."""
    cells = []
    for z in ZONES:
        w, h = z["x1"] - z["x0"], z["y1"] - z["y0"]
        top = PITCH_H - z["y1"]
        group = GROUPS[z["index"]]
        cells.append(
            f'<rect class="zone t-{z["tier"]}" x="{z["x0"]:g}" y="{top:g}" width="{w:g}" height="{h:g}">'
            f'<title>{group["name"]} · {group["area"]:.0f} m²</title></rect>')

    labels = []
    for g in GROUPS:
        members = [z for z in ZONES if z["index"] == g["index"]]
        # A mirrored L/R pair shares one column (same x0/x1), so its bounding
        # box centres on the mirror axis -- exactly where its sibling bucket's
        # box also centres. Anchor those on the first member's own rectangle
        # instead. A group that isn't mirrored within a column (a lone centre
        # band, or the defensive block spanning several columns) keeps the
        # full bounding box -- nothing else occupies that space.
        if len({(z["x0"], z["x1"]) for z in members}) == 1 and len(members) > 1:
            members = members[:1]
        x0 = min(z["x0"] for z in members); x1 = max(z["x1"] for z in members)
        y0 = min(z["y0"] for z in members); y1 = max(z["y1"] for z in members)
        w, h = x1 - x0, y1 - y0
        top = PITCH_H - y1
        area = f'{g["area"]:.0f} m²'
        size = min(2.6, h * 0.28, w * 0.9 / (len(g["name"]) * 0.62))
        cx, cy = x0 + w / 2, top + h / 2
        labels.append(
            f'<text class="zlabel" x="{cx:g}" y="{cy - size * 0.55:.2f}" font-size="{size:.2f}">'
            f'{g["name"]}</text>'
            f'<text class="zlabel l-area" x="{cx:g}" y="{cy + size * 0.7:.2f}" '
            f'font-size="{size * 0.85:.2f}">{area}</text>')
    return "\n    ".join(cells), "\n    ".join(labels)


def summary_rows():
    rows = []
    for tier_name in ("defensive", "middle", "attacking"):
        gs = [g for g in GROUPS if g["tier"] == tier_name]
        areas = sorted(g["area"] for g in gs)
        rows.append(
            f'<tr><td><span class="dot" style="background:{TIER_FILL[tier_name]}"></span>'
            f'{tier_name.title()}</td><td>{len(gs)}</td>'
            f'<td>{areas[0]:.0f}–{areas[-1]:.0f} m²</td>'
            f'<td>{TIER_BLURB[tier_name]}</td></tr>')
    return "\n        ".join(rows)


def render():
    from string import Template
    cells, labels = svg_zones()
    areas = sorted(g["area"] for g in GROUPS)
    html = Template(HTML).substitute(
        zones=cells, labels=labels, lines=svg_pitch_lines(), rows=summary_rows(),
        total=len(GROUPS),
        smallest=f"{areas[0]:.0f}",
        largest=f"{areas[-1]:.0f}",
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
  <p class="sub">$total zones. The whole defensive third is one zone; everywhere else is mirrored
     left/right, so a wing or half-space value is shared by both flanks. Sizes run
     $smallest–$largest m².</p>

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
      <thead><tr><th>Tier</th><th>Zones</th><th>Zone size</th><th>What it is</th></tr></thead>
      <tbody>
        $rows
      </tbody>
    </table>

    <ul class="notes">
      <li><b>Defensive collapse:</b> D1, D2, D3 (3 columns x 3 bands = 9 rectangles) all feed one
          feature, <code>D-ALL</code> -- the whole defensive third, 3570 m².</li>
      <li><b>Mirroring:</b> every other column's wing bands (R+L) and half-space bands (RH+LH) are
          summed together before comparing, so e.g. <code>A1-H</code> is A1's right AND left
          half-space combined -- one number, not two.</li>
      <li>Column edges: 3 equal 17.5 m columns cover the defensive half; a 4th 17.5 m column (M1)
          starts right at halfway; the remaining 35 m split into 6 equal 5.83 m columns (A1-A6).</li>
      <li>Band edges: wings stay at the penalty-box line (<code>13.84</code> m each side); the
          half-space/centre edge sits 1 m inside the six-yard line (<code>23.84</code> m each
          side), so the centre band (<code>20.32</code> m) reads a touch wider than the box
          (<code>18.32</code> m) and the half-spaces (<code>10</code> m) a touch narrower.</li>
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
    print(f"{len(GROUPS)} groups (from {len(ZONES)} rectangles) -> {path}")
