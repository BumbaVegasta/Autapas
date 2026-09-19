"""Find each player's 10 most similar heatmaps and save them to data/similar.csv.

How it works:
  1. Put each player's points on the 101x101 grid (value = count).
  2. Blur with the same Gaussian as the viewer's Smooth mode (2.5 m), so touches
     a metre or two apart still overlap.
  3. Turn the grid into shares of the player's total, so we compare *where*
     players play, not how much.
  4. Cosine similarity between every pair; keep the top 10 per player.
     A player's own file at another club (e.g. mid-season transfer) is skipped.

Run from the repo root:  python3 scripts/build_similar.py
"""
import csv
import os

import numpy as np
from scipy.ndimage import gaussian_filter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA_ROOT = os.path.join(ROOT, "data")
POINTS_DIR = os.path.join(DATA_ROOT, "heatmaps_1000plus_minutes_2324_raw_data")
PLAYERS_FILE = os.path.join(DATA_ROOT, "players.csv")
OUT_FILE = os.path.join(DATA_ROOT, "similar.csv")
SUFFIX = "_heatmap_2324_raw_data.csv"

GRID = 101
PITCH_W, PITCH_H = 105, 68  # metres
SIGMA_M = 2.5               # keep in sync with SIGMA_M in heatmap_viewer/index.html
TOP_N = 10


def load_grid(player_id):
    grid = np.zeros((GRID, GRID), dtype=np.float64)  # [x, y]
    with open(os.path.join(POINTS_DIR, player_id + SUFFIX), newline="") as f:
        for row in csv.DictReader(f):
            grid[int(row["x"]), int(row["y"])] += int(row["count"])
    return grid


def main():
    with open(PLAYERS_FILE, newline="") as f:
        players = list(csv.DictReader(f))
    ids = [p["player_id"] for p in players]
    person = np.array([pid.split("_", 2)[2] for pid in ids])

    # grid steps are 1.04 m along x and 0.67 m along y, so sigma differs per axis
    sigma = (SIGMA_M / (PITCH_W / GRID), SIGMA_M / (PITCH_H / GRID))
    vectors = np.empty((len(ids), GRID * GRID), dtype=np.float32)
    for i, pid in enumerate(ids):
        blurred = gaussian_filter(load_grid(pid), sigma=sigma, mode="constant")
        shares = blurred / blurred.sum()
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
