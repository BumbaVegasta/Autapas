"""Local server for the player heatmap viewer.

Run from the repo root:  python3 heatmap_viewer/server.py  →  http://localhost:8000
"""
import errno
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import seasons as S  # noqa: E402
import zones as Z  # noqa: E402  the single source of truth for the zone grid

DATA_ROOT = os.path.join(HERE, "..", "data")
# one file per comparison method, each built by the matching script in scripts/
SIMILAR_FILES = {
    "cells": (os.path.join(DATA_ROOT, "similar.csv"), "scripts/build_similar.py"),
    "zones": (os.path.join(DATA_ROOT, "similar_zones.csv"), "scripts/build_similar_zones.py"),
}
PORT = int(os.environ.get("PORT", 8000))


def list_players():
    players = S.players_lookup()
    team_names = S.teams_lookup()
    out = []
    for r in S.list_player_seasons():
        p = players.get(r["player_id"])
        minutes = S.season_minutes(r["path"])
        if minutes is None:
            minutes = int(p["season_minutes"]) if p else 0
        out.append({
            "player_id": r["player_id"],
            "player_season_id": r["player_season_id"],
            "season": r["season"],
            "season_label": S.SEASON_LABEL[r["season"]],
            "league": r["league"],
            "team": r["team"],
            "team_name": team_names.get(r["team"], r["team"]),
            "player": r["slug"],
            "first_name": p["first_name"] if p else "",
            "last_name": p["last_name"] if p else "",
            "season_minutes": minutes,
            "file": os.path.basename(r["path"]),
        })
    return out


def read_points(file_path):
    """The player's cells as CSV text, with the centre-spot kickoffs dropped."""
    import csv
    with open(file_path, newline="") as f:
        rows = [r for r in csv.DictReader(f)
                if (int(r["x"]), int(r["y"])) not in S.KICKOFF_CELLS]
    return "x,y,count\n" + "".join(f'{r["x"]},{r["y"]},{r["count"]}\n' for r in rows)


def similar_players(player_season_id, path):
    import csv
    with open(path, newline="") as f:
        return [{
            "player_season_id": row["similar_player_season_id"],
            "rank": int(row["rank"]),
            "similarity": float(row["similarity"]),
        } for row in csv.DictReader(f) if row["player_season_id"] == player_season_id]


def find_raw_file(name):
    """The season a raw filename belongs to (from its own suffix), so /data/
    can locate it without trusting a client-supplied path."""
    name = os.path.basename(name)
    for season in S.SEASONS:
        suffix = f"_heatmap_{season}_raw_data.csv"
        if name.endswith(suffix):
            path = os.path.join(S.raw_data_dir(season), name)
            return path if os.path.isfile(path) else None
    return None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/api/zones":
            return self.send_bytes(json.dumps([
                {"name": z["name"], "group": z["group"], "group_index": z["index"],
                 "tier": z["tier"], "x0": z["x0"], "x1": z["x1"], "y0": z["y0"], "y1": z["y1"],
                 "group_area": round(Z.GROUPS[z["index"]]["area"], 2)}
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
            player_season_id = path[len("/api/similar/"):]
            return self.send_bytes(
                json.dumps(similar_players(player_season_id, file_path)).encode(),
                "application/json")
        if path.startswith("/data/"):
            file_path = find_raw_file(path[len("/data/"):])
            if not file_path:
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
