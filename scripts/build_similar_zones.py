"""Find each player-season's 10 most similar heatmaps using the pitch zones.

The cell version (build_similar.py) compares every one of the 101x101 cells
equally, so a metre by the corner flag counts as much as a metre on the
penalty spot. This one sums the heatmap into the zones from zones.py: one
zone for the whole defensive third, and mirrored wing/half-space/centre
zones everywhere else.

Nothing is blurred here either. The viewer's Blur view blurs for display
only; the zones do the smoothing this comparison needs, by collecting nearby
touches into the same bucket.

How it works:
  1. Put each player-season's points on the 101x101 grid (value = count).
  2. Sum the grid into the zones and turn it into shares of the total, so we
     compare *where* a player played that season, not how much.
  3. Divide each share by the zone's area. Without this the huge defensive
     zone would dominate simply for being huge. Per m² the attacking zones
     carry the comparison for attacking players, and the defensive zone still
     carries it for defenders, because that's where their density sits.
  4. Cosine similarity between every pair; keep the top 10 per player-season.

Like build_similar.py, a player-season is only excluded from matching a
DIFFERENT file of themselves in the SAME season (a mid-season transfer split
across two clubs) -- their own other seasons are fair matches.

Run from the repo root:  python3 scripts/build_similar_zones.py
"""
import csv
import os

import numpy as np

import seasons as S
import zones as Z

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT_FILE = os.path.join(ROOT, "data", "similar_zones.csv")
TOP_N = 10

# Multiply a tier's zones by this before comparing.  1.0 leaves the balance to
# the areas alone; raise "attacking" to push attacking differences harder.
TIER_WEIGHTS = {"defensive": 1.0, "middle": 1.0, "attacking": 1.0}


def zone_vectors(roster):
    """One unit vector of per-m² zone density per player-season, in GROUPS order."""
    zone_map = Z.grid_zone_map().ravel()
    n_zones = len(Z.GROUPS)
    scale = np.array([TIER_WEIGHTS[g["tier"]] / g["area"] for g in Z.GROUPS])

    vectors = np.empty((len(roster), n_zones), dtype=np.float64)
    for i, r in enumerate(roster):
        totals = np.bincount(zone_map, weights=S.load_grid(r["path"]).ravel(), minlength=n_zones)
        density = (totals / totals.sum()) * scale
        vectors[i] = density / np.linalg.norm(density)
    return vectors


def main():
    roster = S.list_player_seasons()
    ids = [r["player_season_id"] for r in roster]
    person = np.array([r["player_id"] for r in roster])
    season = np.array([r["season"] for r in roster])

    vectors = zone_vectors(roster)
    similarity = vectors @ vectors.T
    same_person_season = (person[:, None] == person[None, :]) & (season[:, None] == season[None, :])
    similarity[same_person_season] = -np.inf

    with open(OUT_FILE, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["player_season_id", "rank", "similar_player_season_id", "similarity"])
        for i, pid in enumerate(ids):
            for rank, j in enumerate(np.argsort(-similarity[i])[:TOP_N], 1):
                w.writerow([pid, rank, ids[j], f"{similarity[i, j]:.4f}"])

    print(f"Wrote top {TOP_N} zone matches for {len(ids)} player-seasons "
          f"to {os.path.relpath(OUT_FILE, ROOT)}")


if __name__ == "__main__":
    main()
