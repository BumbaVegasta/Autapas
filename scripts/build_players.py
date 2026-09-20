"""Rebuild data/players.csv from the raw-data roster, carrying curated names
across club changes.

players.csv is keyed by player_id ("<league>_<team>_<slug>"), which embeds the
club, so a player who transfers gets a *new* player_id and the name curated
for them under their old club doesn't follow. That's why every player_id
introduced by the 24/25 and 25/26 exports started out with a blank name, even
for players we already had a name for.

The raw files carry no name of their own -- just the slug, lowercase and
accent-stripped with first and last name run together -- so the hand-curated
23/24 roster is the only name source in this repo. This script copies those
names onto a player's later player_ids, using seasons.person_ids() to decide
which player_ids belong to the same player (and, importantly, which merely
share a slug: "vitinha" is two different players).

Names already in players.csv are never overwritten, so editing a row by hand
is always the last word. Players who never appear in the 23/24 roster keep a
blank name and display by slug in the viewer -- their real names aren't
recoverable from the slug alone ("joakimmhle" for Joakim Mæhle), and would
need a name source we don't have here.

Re-running is safe and idempotent; run it after adding a season's raw data.

Run from the repo root:  python3 scripts/build_players.py
"""
import csv
import os

import seasons as S

FIELDS = ["player_id", "first_name", "last_name", "league", "team", "season_minutes"]


def read_existing():
    """Current rows in file order, so a re-run only rewrites what changed."""
    if not os.path.isfile(S.PLAYERS_FILE):
        return []
    with open(S.PLAYERS_FILE, newline="") as f:
        return list(csv.DictReader(f))


def main():
    roster = S.list_player_seasons()
    person_of = S.person_ids(roster)

    rows = read_existing()
    by_id = {r["player_id"]: r for r in rows}
    for player_id in sorted(person_of):
        if player_id not in by_id:
            league, team, _ = player_id.split("_", 2)
            by_id[player_id] = {"player_id": player_id, "first_name": "", "last_name": "",
                                "league": league, "team": team, "season_minutes": ""}
            rows.append(by_id[player_id])

    # the names already curated for each person, under any of their clubs
    names = {}
    for r in rows:
        if (r["first_name"] or r["last_name"]) and r["player_id"] in person_of:
            names.setdefault(person_of[r["player_id"]], set()).add(
                (r["first_name"], r["last_name"]))

    filled = clashes = 0
    for r in rows:
        if r["first_name"] or r["last_name"] or r["player_id"] not in person_of:
            continue
        known = names.get(person_of[r["player_id"]], set())
        if len(known) == 1:
            r["first_name"], r["last_name"] = next(iter(known))
            filled += 1
        elif known:
            clashes += 1

    with open(S.PLAYERS_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows({k: r[k] for k in FIELDS} for r in rows)

    unnamed = sum(1 for r in rows if not (r["first_name"] or r["last_name"]))
    print(f"players.csv: {len(rows)} rows for {len(set(person_of.values()))} players, "
          f"{len(rows) - unnamed} named ({filled} carried across a club change this run), "
          f"{unnamed} still unnamed")
    if clashes:
        print(f"  {clashes} left blank: their other clubs disagree on the name")


if __name__ == "__main__":
    main()
