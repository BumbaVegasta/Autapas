"""Find each player's 10 most similar heatmaps and save them to data/similar.csv.

This is the fine-grained method: it compares all 101x101 grid cells directly.
Nothing is blurred -- the viewer's Blur view blurs for display only, so that
a season reads as a shape instead of a scatter of dots, and that blur is
deliberately kept out of the maths.

How it works:
  1. Put each player's points on the 101x101 grid (value = count), minus the
     kickoff cells at the centre spot -- see KICKOFF_CELLS below.
  2. Turn the grid into shares of the player's total, so we compare *where*
     players play, not how much.
  3. Cosine similarity between every pair; keep the top 10 per player.
     A player's own file at another club (e.g. mid-season transfer) is skipped.

Because raw cells are sparse, two players rarely land on the exact same cell
and the scores sit low -- a strong match is around 20%, not 90%. The ranking is
what carries meaning; see build_similar_zones.py for the coarser zone method.

Run from the repo root:  python3 scripts/build_similar.py
"""
import csv
import os

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA_ROOT = os.path.join(ROOT, "data")
POINTS_DIR = os.path.join(DATA_ROOT, "heatmaps_1000plus_minutes_2324_raw_data")
PLAYERS_FILE = os.path.join(DATA_ROOT, "players.csv")
OUT_FILE = os.path.join(DATA_ROOT, "similar.csv")
SUFFIX = "_heatmap_2324_raw_data.csv"

GRID = 101
PITCH_W, PITCH_H = 105, 68  # metres
TOP_N = 10

# The centre spot lands on four cells, and they hold a spike nothing else on the
# pitch comes close to: 8,795 touches against ~200 in each neighbouring cell.
# They are kickoffs -- starting a half, restarting after a goal -- not open play,
# and they land almost entirely on centre-forwards (up to 6.3% of a striker's
# touches). Dropped everywhere, including from what the viewer draws; the copy
# of this set in heatmap_viewer/server.py must stay in step.
KICKOFF_CELLS = {(49, 49), (49, 50), (50, 49), (50, 50)}


def load_grid(player_id):
    grid = np.zeros((GRID, GRID), dtype=np.float64)  # [x, y]
    with open(os.path.join(POINTS_DIR, player_id + SUFFIX), newline="") as f:
        for row in csv.DictReader(f):
            x, y = int(row["x"]), int(row["y"])
            if (x, y) in KICKOFF_CELLS:
                continue
            grid[x, y] += int(row["count"])
    return grid


def main():
    with open(PLAYERS_FILE, newline="") as f:
        players = list(csv.DictReader(f))
    ids = [p["player_id"] for p in players]
    person = np.array([pid.split("_", 2)[2] for pid in ids])

    vectors = np.empty((len(ids), GRID * GRID), dtype=np.float32)
    for i, pid in enumerate(ids):
        grid = load_grid(pid)
        shares = grid / grid.sum()
        vectors[i] = (shares / np.linalg.norm(shares)).ravel()

    similarity = vectors @ vectors.T
    # never match a player with themselves (same file or same person at another club)
    similarity[person[:, None] == person[None, :]] = -np.inf

    with open(OUT_FILE, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["player_id", "rank", "similar_player_id", "similarity"])
        for i, pid in enumerate(ids):
            top = np.argsort(-similarity[i])[:TOP_N]
            for rank, j in enumerate(top, 1):
                w.writerow([pid, rank, ids[j], f"{similarity[i, j]:.4f}"])

    print(f"Wrote top {TOP_N} similar players for {len(ids)} players to {os.path.relpath(OUT_FILE, ROOT)}")


if __name__ == "__main__":
    main()
