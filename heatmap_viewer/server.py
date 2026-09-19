"""Local server for the player heatmap viewer.

Run from the repo root:  python3 heatmap_viewer/server.py  →  http://localhost:8000
"""
import csv
import errno
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(HERE, "..", "data")
DATA_DIR = os.path.join(DATA_ROOT, "heatmaps_1000plus_minutes_2324_raw_data")
PLAYERS_FILE = os.path.join(DATA_ROOT, "players.csv")
TEAMS_FILE = os.path.join(DATA_ROOT, "teams.csv")
SIMILAR_FILE = os.path.join(DATA_ROOT, "similar.csv")  # built by scripts/build_similar.py
SUFFIX = "_heatmap_2324_raw_data.csv"
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


def similar_players(player_id):
    with open(SIMILAR_FILE, newline="") as f:
        return [{
            "player_id": row["similar_player_id"],
            "rank": int(row["rank"]),
            "similarity": float(row["similarity"]),
        } for row in csv.DictReader(f) if row["player_id"] == player_id]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/players":
            return self.send_bytes(json.dumps(list_players()).encode(), "application/json")
        if path.startswith("/api/similar/"):
            if not os.path.isfile(SIMILAR_FILE):
                return self.send_error(404, "Run: python3 scripts/build_similar.py")
            player_id = path[len("/api/similar/"):]
            return self.send_bytes(json.dumps(similar_players(player_id)).encode(), "application/json")
        if path.startswith("/data/"):
            name = os.path.basename(path[len("/data/"):])
            file_path = os.path.join(DATA_DIR, name)
            if not name.endswith(SUFFIX) or not os.path.isfile(file_path):
                return self.send_error(404)
            with open(file_path, "rb") as f:
                return self.send_bytes(f.read(), "text/csv")
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
