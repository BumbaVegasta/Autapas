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
    """player_id -> {first_name, last_name, season_minutes} from the 2324
    roster -- the only season with hand-curated names. Missing for anyone who
    only appears in the newer seasons."""
    if not os.path.isfile(PLAYERS_FILE):
        return {}
    with open(PLAYERS_FILE, newline="") as f:
        return {row["player_id"]: row for row in csv.DictReader(f)}


def teams_lookup():
    if not os.path.isfile(TEAMS_FILE):
        return {}
    with open(TEAMS_FILE, newline="") as f:
        return {row["team"]: row["team_name"] for row in csv.DictReader(f)}
