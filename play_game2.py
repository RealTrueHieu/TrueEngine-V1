import requests
import json
import subprocess
import time
import os
import chess
import chess.pgn

PROJECT_DIR = r"C:\Users\RealTrueHieu\CustomHumanChessEngine"
TRUEENGINE_EXE = os.path.join(PROJECT_DIR, "dist", "TrueEngine_V1_Cloud.exe")
PGN_PATH = os.path.join(PROJECT_DIR, "data", "vanguard_gen6_clash.pgn")
os.makedirs(os.path.dirname(PGN_PATH), exist_ok=True)

class TrueEngineClient:
    def __init__(self):
        self.proc = subprocess.Popen(
            [TRUEENGINE_EXE],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        self.proc.stdin.write("uci\nisready\n")
        self.proc.stdin.flush()
        while True:
            line = self.proc.stdout.readline()
            if "readyok" in line:
                break

    def get_move(self, fen: str, nodes: int = 3500) -> str:
        self.proc.stdin.write(f"position fen {fen}\ngo nodes {nodes}\n")
        self.proc.stdin.flush()
        bestmove = None
        info_lines = []
        while True:
            line = self.proc.stdout.readline()
            if not line:
                break
            line_str = line.strip()
            if line_str.startswith("info ") and ("score" in line_str or "Hardware" in line_str):
                info_lines.append(line_str)
            if line_str.startswith("bestmove"):
                parts = line_str.split()
                bestmove = parts[1] if len(parts) > 1 else None
                break
        return bestmove, info_lines

    def close(self):
        try:
            self.proc.stdin.write("quit\n")
            self.proc.stdin.flush()
            self.proc.terminate()
        except Exception:
            pass

def safe_post(s, url, payload, max_retries=4):
    for attempt in range(max_retries):
        time.sleep(0.7)
        try:
            r = s.post(url, json=payload, timeout=15)
            if r.status_code == 429:
                print(f"    [Rate-Limit 429] Waiting 1.2s before retry...", flush=True)
                time.sleep(1.2)
                continue
            return r
        except Exception as e:
            time.sleep(1.0)
    return None

def play_game2():
    print("==================================================================", flush=True)
    print(" ♚ GAME 2: Vanguard Gen-6 [WHITE] vs TrueEngine V1 [BLACK]", flush=True)
    print(" Arena: https://lethoso.tech/ | Model: Clean-Room V6_Gen6 Big (💀 Full Power)", flush=True)
    print("==================================================================", flush=True)

    s = requests.Session()
    v_user = os.environ.get("VANGUARD_USER", "truehieu")
    v_pass = os.environ.get("VANGUARD_PASS", "")
    s.post("https://lethoso.tech/api/auth/login", json={"username": v_user, "password": v_pass}, timeout=10)

    trueengine = TrueEngineClient()

    MODEL = "v6_gen6_big"
    LEVEL = "gen6_full"

    r_reset = safe_post(s, "https://lethoso.tech/api/reset", {
        "fen": "startpos",
        "engine_first": True,
        "model": MODEL,
        "level": LEVEL,
        "movetime_ms": 450
    })
    state = r_reset.json()

    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["Event"] = "Super-Model Titan Clash"
    game.headers["Site"] = "https://lethoso.tech/"
    game.headers["White"] = "Vanguard Gen-6 Clean-Room (Big)"
    game.headers["Black"] = "TrueEngine V1 (Dual Tesla T4)"
    game.headers["Date"] = time.strftime("%Y.%m.%d")
    node = game

    ply = 0
    if state.get("moves"):
        vg_m1 = state["moves"][0]
        obj1 = chess.Move.from_uci(vg_m1)
        board.push(obj1)
        node = node.add_variation(obj1)
        ply = 1
        print(f"  ♔ Vanguard Gen-6 (Move 1): {vg_m1}", flush=True)

    while not state.get("game_status", {}).get("over", False) and ply < 120:
        fen = state.get("fen")
        print(f"\n--- Move {(ply//2) + 1} ---", flush=True)
        t0 = time.time()
        bestmove, info_lines = trueengine.get_move(fen, nodes=3500)
        t_te = round(time.time() - t0, 2)
        if not bestmove:
            print("No move from TrueEngine!")
            break

        move_obj = chess.Move.from_uci(bestmove)
        san_b = board.san(move_obj)
        board.push(move_obj)
        node = node.add_variation(move_obj)
        ply += 1

        print(f"  ♚ TrueEngine V1: {san_b} ({bestmove}) [{t_te}s]", flush=True)
        for inf in info_lines:
            if "Tesla T4" in inf or "Guardian" in inf:
                print(f"    -> {inf}", flush=True)

        # Check if TrueEngine move ended the game
        if board.is_game_over():
            break

        t1 = time.time()
        r_move = safe_post(s, "https://lethoso.tech/api/move", {
            "move": bestmove,
            "reply": True,
            "model": MODEL,
            "level": LEVEL,
            "movetime_ms": 450,
            "expected_hash": state.get("position_hash")
        })
        t_vg = round(time.time() - t1, 2)

        if not r_move or r_move.status_code != 200:
            print(f"Error from arena: {r_move.status_code if r_move else 'No resp'}")
            break

        state = r_move.json()
        gs = state.get("game_status", {})
        moves_list = state.get("moves", [])

        # Check if game over right away
        if gs.get("over", False):
            # Check if Vanguard made a move before game over
            if len(moves_list) == ply + 1:
                vg_move_uci = moves_list[-1]
                vg_obj = chess.Move.from_uci(vg_move_uci)
                san_w = board.san(vg_obj)
                board.push(vg_obj)
                node = node.add_variation(vg_obj)
                ply += 1
                print(f"  ♔ Vanguard Gen-6: {san_w} ({vg_move_uci}) [{t_vg}s]", flush=True)
            break

        if len(moves_list) > ply - 1:
            vg_move_uci = moves_list[-1]
            vg_obj = chess.Move.from_uci(vg_move_uci)
            san_w = board.san(vg_obj)
            board.push(vg_obj)
            node = node.add_variation(vg_obj)
            ply += 1

            vg_info = state.get("last_info", {})
            vg_cp = vg_info.get("score_white", "N/A")
            vg_d = vg_info.get("depth", "N/A")
            vg_nps = vg_info.get("nps", "N/A")
            print(f"  ♔ Vanguard Gen-6: {san_w} ({vg_move_uci}) [{t_vg}s] (Depth {vg_d} | NPS {vg_nps} | Eval {vg_cp} cp)", flush=True)

    gs = state.get("game_status", {})
    res = gs.get("result", board.result())
    game.headers["Result"] = res
    print("\n" + "=" * 50, flush=True)
    print(f"🏁 GAME 2 FINISHED! Result: {res} ({gs.get('title', '')} - {gs.get('subtitle', '')})", flush=True)
    print("=" * 50, flush=True)

    with open(PGN_PATH, "a", encoding="utf-8") as f:
        f.write(str(game) + "\n\n")

    trueengine.close()

if __name__ == "__main__":
    play_game2()
