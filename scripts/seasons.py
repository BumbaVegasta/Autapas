"""Multi-season roster: every player-season we have raw heatmap data for.

Each raw file is named "<league>_<team>_<slug>_heatmap_<season>_raw_data.csv"
inside "data/heatmaps_1000plus_minutes_<season>_raw_data/". The unit of
comparison is a *player-season*, not a player -- Erling Haaland's 23/24 and
24/25 are two different rows, so a similarity search can surface "closest to
this player's OTHER season" as well as "closest to another player".

player_season_id = "<player_id>__<season>", e.g.
"premierleague_manchestercity_erlinghaaland__2425". player_id on its own
(league_team_slug) never changes across seasons, so it's what identifies "the
same person" for the self-match exclusion in build_similar*.py.
"""
import csv
import glob
import os

import numpy as np

DATA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
PLAYERS_FILE = os.path.join(DATA_ROOT, "players.csv")
TEAMS_FILE = os.path.join(DATA_ROOT, "teams.csv")

SEASONS = ["2324", "2425", "2526"]
SEASON_LABEL = {"2324": "23/24", "2425": "24/25", "2526": "25/26"}

# The 24/25 and 25/26 raw data uses a different team-slug spelling than the
# original 23/24 export for clubs that didn't change identity, only export
# convention (e.g. "afcbournemouth" -> "bournemouth", "internazionale" ->
# "inter"). Left un-aliased, a continuing player's player_id would silently
# change team component across seasons, breaking name lookups and the
# same-person exclusion. Maps the NEW slug to the original (23/24) one, found
# by cross-checking club name similarity against shared-player overlap
# between the two spellings -- not by a promoted/relegated club coincidentally
# sharing a transferred player or two.
TEAM_ALIASES = {
    "1fcheidenheim1846": "fcheidenheim",
    "1fcunionberlin": "unionberlin",
    "1fsvmainz05": "mainz05",
    "bayer04leverkusen": "bayerleverkusen",
    "fcaugsburg": "augsburg",
    "sportclubfreiburg": "freiburg",
    "svwerderbremen": "werderbremen",
    "tsg1899hoffenheim": "hoffenheim",
    "vflbochum1848": "bochum",
    "vflwolfsburg": "wolfsburg",
    "alaves": "deportivoalaves",
    "atleticodemadrid": "atleticomadrid",
    "celtadevigo": "celtavigo",
    "valenciacf": "valencia",
    "bournemouth": "afcbournemouth",
    "brightonandhovealbion": "brightonhovealbion",
    "internazionale": "inter",
    "verona": "hellasverona",
}

GRID = 101
# The centre spot lands on four cells with a spike nothing else on the pitch
# comes close to (kickoffs, not open play). Dropped everywhere -- both
# build_similar*.py and heatmap_viewer/server.py import this constant.
KICKOFF_CELLS = {(49, 49), (49, 50), (50, 49), (50, 50)}


def raw_data_dir(season):
    return os.path.join(DATA_ROOT, f"heatmaps_1000plus_minutes_{season}_raw_data")


def list_player_seasons():
    """Every (player_id, season) we have a raw file for, sorted for stable output."""
    rows = []
    for season in SEASONS:
        suffix = f"_heatmap_{season}_raw_data.csv"
        for path in glob.glob(os.path.join(raw_data_dir(season), f"*{suffix}")):
            fname = os.path.basename(path)
            raw_id = fname[: -len(suffix)]
            league, team, slug = raw_id.split("_", 2)
            team = TEAM_ALIASES.get(team, team)
            player_id = f"{league}_{team}_{slug}"
            rows.append({
                "player_id": player_id,
                "player_season_id": f"{player_id}__{season}",
                "league": league, "team": team, "slug": slug,
                "season": season, "path": path,
            })
    rows.sort(key=lambda r: r["player_season_id"])
    return rows


def load_grid(path):
    """A player-season's touches on the 101x101 grid, kickoffs dropped."""
    grid = np.zeros((GRID, GRID), dtype=np.float64)
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            x, y = int(row["x"]), int(row["y"])
            if (x, y) in KICKOFF_CELLS:
                continue
            grid[x, y] += int(row["count"])
    return grid


def season_minutes(path):
    """Season minutes from the raw file when it carries one (2425/2526's
    sezon_dakikasi column); None for the 2324 files, which don't."""
    with open(path, newline="") as f:
        row = next(csv.DictReader(f), None)
    if row and "sezon_dakikasi" in row:
        return int(row["sezon_dakikasi"])
    return None


def players_lookup():
    """player_id -> {first_name, last_name, league, team, season_minutes}.

    Names are hand-curated for 23/24 and carried onto a player's later
    player_ids by scripts/build_players.py when they change club. Still blank
    for anyone who never appears in the 23/24 roster -- the raw files carry no
    name, so those display by slug. season_minutes is only filled for 23/24;
    later seasons carry it in the raw file itself (see season_minutes())."""
    if not os.path.isfile(PLAYERS_FILE):
        return {}
    with open(PLAYERS_FILE, newline="") as f:
        return {row["player_id"]: row for row in csv.DictReader(f)}


def teams_lookup():
    if not os.path.isfile(TEAMS_FILE):
        return {}
    with open(TEAMS_FILE, newline="") as f:
        return {row["team"]: row["team_name"] for row in csv.DictReader(f)}


# 38 matches x 90 minutes -- the longest league season in the dataset. Two
# player_ids sharing a slug whose minutes in one season add up to more than a
# season's worth of football cannot belong to the same player.
MAX_SEASON_MINUTES = 38 * 90


def person_ids(roster=None):
    """player_id -> person_id, grouping the player_ids one player collects as
    they change club.

    player_id embeds the club, so a transfer starts a new one and nothing
    downstream can tell "Calafiori at Bologna, then at Arsenal" from two
    different people. The raw files give us only the slug to go on, so two
    player_ids sharing a slug are treated as one person unless their seasons
    say otherwise:

      * no season in common      -> one player, who moved between seasons
      * one season in common,
        minutes fitting inside
        a single season          -> one player, transferred mid-season
      * anything else            -> namesakes, kept apart

    The last case is real: "vitinha" is Vitinha at Paris Saint-Germain and a
    different Vitinha at Genoa, both playing full 24/25 and 25/26 seasons.

    person_id is the alphabetically first player_id in the group, so it's
    stable as long as the same files are present.
    """
    roster = roster if roster is not None else list_player_seasons()
    seasons_of, minutes_of, by_slug = {}, {}, {}
    for r in roster:
        seasons_of.setdefault(r["player_id"], set()).add(r["season"])
        minutes_of[(r["player_id"], r["season"])] = season_minutes(r["path"])
        by_slug.setdefault(r["slug"], set()).add(r["player_id"])

    def same_person(a, b):
        shared = seasons_of[a] & seasons_of[b]
        if not shared:
            return True
        if len(shared) > 1:
            return False
        season = next(iter(shared))
        ma, mb = minutes_of[(a, season)], minutes_of[(b, season)]
        # 23/24 raw files carry no minutes, so a namesake can't be ruled out
        return ma is not None and mb is not None and ma + mb <= MAX_SEASON_MINUTES

    out = {}
    for ids in by_slug.values():
        groups = []  # lists of player_ids already judged to be one person
        for pid in sorted(ids):
            for g in groups:
                if all(same_person(pid, other) for other in g):
                    g.append(pid)
                    break
            else:
                groups.append([pid])
        for g in groups:
            for pid in g:
                out[pid] = g[0]
    return out
