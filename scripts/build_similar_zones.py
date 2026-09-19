"""Find each player's 10 most similar heatmaps using the graduated pitch zones.

The cell version (build_similar.py) compares every one of the 101x101 cells
equally, so a metre by the corner flag counts as much as a metre on the penalty
spot.  This one sums the heatmap into the zones from zones.py, which are big at
the back and small in the box.

Nothing is blurred here either.  The viewer's Blur view blurs for display
only; the zones do the smoothing this comparison needs, by collecting nearby
touches into the same bucket.

How it works:
  1. Put each player's points on the 101x101 grid (value = count).
  2. Sum the grid into the 51 zones and turn it into shares of the player's
     total, so we compare *where* players play, not how much.
  3. Divide each share by the zone's area.  Without this the big defensive
     blocks would dominate simply for being big -- a striker's top zone came
     out as his own middle third.  Per m² the 30 small attacking zones carry
     the comparison for attacking players, and the defensive blocks still
     carry it for defenders, because that's where their density sits.
  4. Cosine similarity between every pair; keep the top 10 per player.
     A player's own file at another club (e.g. mid-season transfer) is skipped.

Run from the repo root:  python3 scripts/build_similar_zones.py
"""
import csv
import os

import numpy as np

import zones as Z
from build_similar import load_grid

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PLAYERS_FILE = os.path.join(ROOT, "data", "players.csv")
OUT_FILE = os.path.join(ROOT, "data", "similar_zones.csv")
TOP_N = 10

# Multiply a tier's zones by this before comparing.  1.0 leaves the balance to
# the areas alone; raise "attacking" to push attacking differences harder.
TIER_WEIGHTS = {"defensive": 1.0, "middle": 1.0, "attacking": 1.0}


def zone_vectors(ids):
    """One unit vector of per-m² zone density per player, in ZONES order."""
    zone_map = Z.grid_zone_map().ravel()
    n_zones = len(Z.ZONES)
    scale = np.array([TIER_WEIGHTS[z["tier"]] / z["area"] for z in Z.ZONES])

    vectors = np.empty((len(ids), n_zones), dtype=np.float64)
    for i, pid in enumerate(ids):
        totals = np.bincount(zone_map, weights=load_grid(pid).ravel(), minlength=n_zones)
        density = (totals / totals.sum()) * scale
        vectors[i] = density / np.linalg.norm(density)
    return vectors


def main():
    with open(PLAYERS_FILE, newline="") as f:
        ids = [p["player_id"] for p in csv.DictReader(f)]
    person = np.array([pid.split("_", 2)[2] for pid in ids])

    vectors = zone_vectors(ids)
    similarity = vectors @ vectors.T
    # never match a player with themselves (same file or same person at another club)
    similarity[person[:, None] == person[None, :]] = -np.inf

    with open(OUT_FILE, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["player_id", "rank", "similar_player_id", "similarity"])
        for i, pid in enumerate(ids):
            for rank, j in enumerate(np.argsort(-similarity[i])[:TOP_N], 1):
                w.writerow([pid, rank, ids[j], f"{similarity[i, j]:.4f}"])

    print(f"Wrote top {TOP_N} zone matches for {len(ids)} players "
          f"to {os.path.relpath(OUT_FILE, ROOT)}")


if __name__ == "__main__":
    main()
