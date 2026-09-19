"""Print one player-season's top 10 under both comparison methods, side by side.

  python3 scripts/compare_methods.py "Harry Kane"
  python3 scripts/compare_methods.py kane araujo rodri
  python3 scripts/compare_methods.py haaland --season 2425

Matching is loose: any part of the name or the raw player slug, accents and
case ignored. A query matching one player across several seasons prints one
block per season (that's the point -- comparing a player's own seasons is
exactly what the multi-season data is for); a query matching several
different players is ambiguous and asks you to be more specific. A * marks a
player the zone method found that the blur method missed.

Run from the repo root.
"""
import argparse
import csv
import os
import sys
import unicodedata

import seasons as S

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data")
METHODS = [("cells", "similar.csv", "build_similar.py"),
           ("zones", "similar_zones.csv", "build_similar_zones.py")]
LEAGUES = {"premierleague": "Premier League", "laliga": "La Liga", "seriea": "Serie A",
           "bundesliga": "Bundesliga", "ligue1": "Ligue 1", "superlig": "Süper Lig"}


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").replace("'", "").lower()


def name_of(players, r):
    p = players.get(r["player_id"])
    if p and (p["first_name"] or p["last_name"]):
        return f'{p["first_name"]} {p["last_name"]}'.strip()
    return r["slug"]


def load_ranking(filename, script):
    path = os.path.join(DATA, filename)
    if not os.path.isfile(path):
        sys.exit(f"Missing {os.path.relpath(path, ROOT)} — run:  python3 scripts/{script}")
    out = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["player_season_id"], []).append(
                (r["similar_player_season_id"], float(r["similarity"])))
    return out


def find(roster, players, query, seasons):
    """The player-season row(s) matching `query`: every season of one player if
    the name is unambiguous, or None (after explaining why) if it matches
    several different players."""
    q = fold(query)
    candidates = [r for r in roster if r["season"] in seasons
                  and (q in fold(name_of(players, r)) or q in fold(r["slug"]))]
    if not candidates:
        print(f'\nNo player matching "{query}".')
        return None
    people = sorted({r["player_id"] for r in candidates})
    if len(people) > 1:
        shown = ", ".join(f"{name_of(players, next(r for r in candidates if r['player_id'] == p))} "
                           f"({next(r for r in candidates if r['player_id'] == p)['team']})"
                           for p in people[:8])
        print(f'\n"{query}" matches {len(people)} players — be more specific: '
              + shown + ("…" if len(people) > 8 else ""))
        return None
    return sorted(candidates, key=lambda r: r["season"])


def report(players, players_by_id, rankings, r):
    pid = r["player_season_id"]
    minutes = S.season_minutes(r["path"])
    if minutes is None:
        p = players.get(r["player_id"])
        minutes = p["season_minutes"] if p else "?"
    print(f'\n{name_of(players, r)} — {r["team"]} · {LEAGUES.get(r["league"], r["league"])} '
          f'· {S.SEASON_LABEL[r["season"]]} · {minutes} min')

    cells, zones = (rankings[m].get(pid, []) for m in ("cells", "zones"))
    if not cells or not zones:
        print("  no similarity rows for this player-season — run both build_similar*.py scripts")
        return
    cell_ids = {p for p, _ in cells}

    def label(psid):
        p_id, season = psid.rsplit("__", 1)
        row = players_by_id.get(p_id, [None])[0]
        name = name_of(players, row) if row else p_id.split("_", 2)[2]
        return f"{name} '{S.SEASON_LABEL[season][-2:]}"

    print(f'  {"":<3}{"CELLS (every m² equal)":<42}{"ZONES (mirrored, defence merged)"}')
    print("  " + "-" * 84)
    for i in range(min(len(cells), len(zones))):
        bp, bs = cells[i]
        zp, zs = zones[i]
        mark = " " if zp in cell_ids else "*"
        print(f"  {i + 1:>2}. {label(bp)[:32]:<32}{bs * 100:5.1f}%   "
              f"{mark} {label(zp)[:32]:<32}{zs * 100:5.1f}%")

    kept = len(cell_ids & {p for p, _ in zones})
    print(f"  {kept}/{len(zones)} of the top 10 are the same player-seasons. "
          f"* = found only by the zone method.")
    print("  Scores aren't comparable between the two columns — sparse raw cells rarely "
          "coincide,\n  so cell scores sit far lower. Compare the ranking, not the number.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("player", nargs="+", help="part of a player's name (or raw slug)")
    ap.add_argument("--season", default=",".join(S.SEASONS),
                    help=f"comma-separated seasons to include, from {S.SEASONS} (default: all)")
    args = ap.parse_args()
    seasons = set(args.season.split(","))

    roster = S.list_player_seasons()
    players = S.players_lookup()
    players_by_id = {}
    for r in roster:
        players_by_id.setdefault(r["player_id"], []).append(r)

    rankings = {m: load_ranking(f, s) for m, f, s in METHODS}
    for query in args.player:
        rows = find(roster, players, query, seasons)
        if rows:
            for r in rows:
                report(players, players_by_id, rankings, r)


if __name__ == "__main__":
    main()
