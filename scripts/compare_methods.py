"""Print one player's top 10 under both comparison methods, side by side.

  python3 scripts/compare_methods.py "Harry Kane"
  python3 scripts/compare_methods.py kane araujo rodri

Matching is loose: any part of the name, accents and case ignored.  A * marks a
player the zone method found that the blur method missed.
"""
import argparse
import csv
import os
import sys
import unicodedata

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data")
METHODS = [("cells", "similar.csv", "build_similar.py"),
           ("zones", "similar_zones.csv", "build_similar_zones.py")]
LEAGUES = {"premierleague": "Premier League", "laliga": "La Liga", "seriea": "Serie A",
           "bundesliga": "Bundesliga", "ligue1": "Ligue 1", "superlig": "Süper Lig"}


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").replace("'", "").lower()


def load_players():
    with open(os.path.join(DATA, "players.csv"), newline="") as f:
        return {r["player_id"]: r for r in csv.DictReader(f)}


def load_ranking(filename, script):
    path = os.path.join(DATA, filename)
    if not os.path.isfile(path):
        sys.exit(f"Missing {os.path.relpath(path, ROOT)} — run:  python3 scripts/{script}")
    out = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["player_id"], []).append((r["similar_player_id"], float(r["similarity"])))
    return out


def find(players, query):
    """The one player matching `query`, or None after saying why it was skipped."""
    q = fold(query)
    hits = [pid for pid, r in players.items() if q in fold(name_of(players, pid))]
    if not hits:
        print(f'\nNo player matching "{query}".')
        return None
    if len(hits) > 1:
        shown = ", ".join(f"{name_of(players, h)} ({players[h]['team']})" for h in hits[:8])
        print(f'\n"{query}" matches {len(hits)} players — be more specific: '
              + shown + ("…" if len(hits) > 8 else ""))
        return None
    return hits[0]


def name_of(players, pid):
    r = players[pid]
    return f'{r["first_name"]} {r["last_name"]}'.strip() or pid


def report(players, rankings, pid):
    r = players[pid]
    print(f'\n{name_of(players, pid)} — {r["team"]} · {LEAGUES.get(r["league"], r["league"])} '
          f'· {r["season_minutes"]} min')

    cells, zones = (rankings[m].get(pid, []) for m in ("cells", "zones"))
    if not cells or not zones:
        print("  no similarity rows for this player in one of the files")
        return
    cell_ids = {p for p, _ in cells}

    print(f'  {"":<3}{"CELLS (every m² equal)":<38}{"ZONES (finer towards goal)"}')
    print("  " + "-" * 78)
    for i in range(min(len(cells), len(zones))):
        bp, bs = cells[i]
        zp, zs = zones[i]
        mark = " " if zp in cell_ids else "*"
        print(f"  {i + 1:>2}. {name_of(players, bp)[:28]:<28}{bs * 100:5.1f}%   "
              f"{mark} {name_of(players, zp)[:28]:<28}{zs * 100:5.1f}%")

    kept = len(cell_ids & {p for p, _ in zones})
    print(f"  {kept}/{len(zones)} of the top 10 are the same players. "
          f"* = found only by the zone method.")
    print("  Scores aren't comparable between the two columns — sparse raw cells rarely "
          "coincide,\n  so cell scores sit far lower. Compare the ranking, not the number.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("player", nargs="+", help="part of a player's name")
    args = ap.parse_args()

    players = load_players()
    rankings = {m: load_ranking(f, s) for m, f, s in METHODS}
    for query in args.player:
        pid = find(players, query)
        if pid:
            report(players, rankings, pid)


if __name__ == "__main__":
    main()
