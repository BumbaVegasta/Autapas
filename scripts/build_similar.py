"""Find each player-season's 10 most similar heatmaps and save them to
data/similar.csv.

This is the fine-grained method: it compares all 101x101 grid cells directly.
Nothing is blurred -- the viewer's Blur view blurs for display only, so that
a season reads as a shape instead of a scatter of dots, and that blur is
deliberately kept out of the maths.

The unit of comparison is a player-season (see scripts/seasons.py), not a
player: Erling Haaland's 23/24 and 24/25 are two different rows, across all
three seasons of raw data we have. A player is only excluded from matching
against a DIFFERENT file of themselves in the SAME season (a mid-season
transfer split across two clubs, which is the same minutes twice, not a
comparison) -- matches against their OWN other seasons are allowed and
expected, since "how has this player's game changed" is exactly the kind of
question this is for.

How it works:
  1. Put each player-season's points on the 101x101 grid (value = count),
     minus the kickoff cells at the centre spot.
  2. Turn the grid into shares of the total, so we compare *where* a player
     played that season, not how much.
  3. Cosine similarity between every pair; keep the top 10 per player-season.

Because raw cells are sparse, two players rarely land on the exact same cell
and the scores sit low -- a strong match is around 20%, not 90%. The ranking is
what carries meaning; see build_similar_zones.py for the coarser zone method.

Run from the repo root:  python3 scripts/build_similar.py
"""
import csv
import os

import numpy as np

import seasons as S

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT_FILE = os.path.join(ROOT, "data", "similar.csv")
TOP_N = 10


def main():
    roster = S.list_player_seasons()
    ids = [r["player_season_id"] for r in roster]
    person = np.array([r["player_id"] for r in roster])
    season = np.array([r["season"] for r in roster])

    vectors = np.empty((len(roster), S.GRID * S.GRID), dtype=np.float32)
    for i, r in enumerate(roster):
        grid = S.load_grid(r["path"])
        shares = grid / grid.sum()
        vectors[i] = (shares / np.linalg.norm(shares)).ravel()

    similarity = vectors @ vectors.T
    # only exclude the same person in the SAME season (a mid-season transfer
    # split across two clubs) -- their other seasons are fair matches
    same_person_season = (person[:, None] == person[None, :]) & (season[:, None] == season[None, :])
    similarity[same_person_season] = -np.inf

    with open(OUT_FILE, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["player_season_id", "rank", "similar_player_season_id", "similarity"])
        for i, pid in enumerate(ids):
            top = np.argsort(-similarity[i])[:TOP_N]
            for rank, j in enumerate(top, 1):
                w.writerow([pid, rank, ids[j], f"{similarity[i, j]:.4f}"])

    print(f"Wrote top {TOP_N} similar player-seasons for {len(ids)} rows to "
          f"{os.path.relpath(OUT_FILE, ROOT)}")


if __name__ == "__main__":
    main()
