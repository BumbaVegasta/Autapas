"""Local server for the player heatmap viewer.

Run from the repo root:  python3 heatmap_viewer/server.py  →  http://localhost:8000
"""
import csv
import errno
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import zones as Z  # noqa: E402  the single source of truth for the zone grid

DATA_ROOT = os.path.join(HERE, "..", "data")
DATA_DIR = os.path.join(DATA_ROOT, "heatmaps_1000plus_minutes_2324_raw_data")
PLAYERS_FILE = os.path.join(DATA_ROOT, "players.csv")
TEAMS_FILE = os.path.join(DATA_ROOT, "teams.csv")
# one file per comparison method, each built by the matching script in scripts/
SIMILAR_FILES = {
    "cells": (os.path.join(DATA_ROOT, "similar.csv"), "scripts/build_similar.py"),
    "zones": (os.path.join(DATA_ROOT, "similar_zones.csv"), "scripts/build_similar_zones.py"),
}
SUFFIX = "_heatmap_2324_raw_data.csv"
# kickoffs at the centre spot, not open play — keep in step with
# KICKOFF_CELLS in scripts/build_similar.py
KICKOFF_CELLS = {(49, 49), (49, 50), (50, 49), (50, 50)}
PORT = int(os.environ.get("PORT", 8000))


def list_players():
    with open(PLAYERS_FILE, newline="") as f:
        rows = list(csv.DictReader(f))
    with open(TEAMS_FILE, newline="") as f:
        team_names = {t["team"]: t["team_name"] for t in csv.DictReader(f)}
    return [{
        **row,
        "team_name": team_names.get(row["team"], row["team"]),
        "player": row["player_id"].split("_", 2)[2],
        "season_minutes": int(row["season_minutes"]),
        "file": row["player_id"] + SUFFIX,
    } for row in rows]


def read_points(file_path):
    """The player's cells as CSV text, with the centre-spot kickoffs dropped."""
    with open(file_path, newline="") as f:
        rows = [r for r in csv.DictReader(f)
                if (int(r["x"]), int(r["y"])) not in KICKOFF_CELLS]
    return "x,y,count\n" + "".join(f'{r["x"]},{r["y"]},{r["count"]}\n' for r in rows)


def similar_players(player_id, path):
    with open(path, newline="") as f:
        return [{
            "player_id": row["similar_player_id"],
            "rank": int(row["rank"]),
            "similarity": float(row["similarity"]),
        } for row in csv.DictReader(f) if row["player_id"] == player_id]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/api/zones":
            return self.send_bytes(json.dumps([
                {"name": z["name"], "tier": z["tier"], "x0": z["x0"], "x1": z["x1"],
                 "y0": z["y0"], "y1": z["y1"], "area": round(z["area"], 2)}
                for z in Z.ZONES]).encode(), "application/json")
        if path == "/api/players":
            return self.send_bytes(json.dumps(list_players()).encode(), "application/json")
        if path.startswith("/api/similar/"):
            method = parse_qs(query).get("method", ["cells"])[0]
            if method not in SIMILAR_FILES:
                return self.send_error(400, f"Unknown method: {method}")
            file_path, script = SIMILAR_FILES[method]
            if not os.path.isfile(file_path):
                return self.send_error(404, f"Run: python3 {script}")
            player_id = path[len("/api/similar/"):]
            return self.send_bytes(
                json.dumps(similar_players(player_id, file_path)).encode(), "application/json")
        if path.startswith("/data/"):
            name = os.path.basename(path[len("/data/"):])
            file_path = os.path.join(DATA_DIR, name)
            if not name.endswith(SUFFIX) or not os.path.isfile(file_path):
                return self.send_error(404)
            return self.send_bytes(read_points(file_path).encode(), "text/csv")
        return super().do_GET()

    def send_bytes(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError as e:
        if e.errno != errno.EADDRINUSE:
            raise
        sys.exit(f"Port {PORT} is already in use. It may already be running at http://localhost:{PORT}\n"
                 f"Stop it with:  kill $(lsof -t -iTCP:{PORT} -sTCP:LISTEN)\n"
                 f"Or use another port:  PORT=8001 python3 heatmap_viewer/server.py")
    print(f"Heatmap viewer running at http://localhost:{PORT}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
