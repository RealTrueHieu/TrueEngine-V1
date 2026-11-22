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
    """Posts JSON to Vanguard Arena with automatic 429 rate-limit backoff."""
    for attempt in range(max_retries):
        time.sleep(0.7)  # Safe spacing between moves
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

def run_vanguard_match():
    print("==================================================================", flush=True)
    print(" ⚔️ TITAN CLASH: TrueEngine V1 [Dual-T4 Supercomputing] vs Vanguard Gen-6", flush=True)
    print(" Model: Clean-Room V6_Gen6 Big (💀 Full Power - SF15 Killer)", flush=True)
    print(" Arena: https://lethoso.tech/", flush=True)
    print("==================================================================", flush=True)

    # 1. Login to Vanguard Arena
    s = requests.Session()
    v_user = os.environ.get("VANGUARD_USER", "truehieu")
    v_pass = os.environ.get("VANGUARD_PASS", "")
    login_res = s.post(
        "https://lethoso.tech/api/auth/login",
        json={"username": v_user, "password": v_pass},
        timeout=10
    )
    if login_res.status_code != 200:
        print("❌ Login failed:", login_res.text)
        return
    print("✅ Authenticated into Vanguard Gen-6 Arena!", flush=True)

    trueengine = TrueEngineClient()

    MODEL = "v6_gen6_big"   # Clean-Room V6_Gen6 Big
    LEVEL = "gen6_full"     # Full V6_Gen6

    # =================================================================
    # GAME 1: TrueEngine V1 (White) vs Vanguard Gen-6 (Black)
    # =================================================================
    print("\n" + "=" * 60, flush=True)
    print(" ♔ GAME 1: TrueEngine V1 [WHITE] vs Vanguard Gen-6 [BLACK]", flush=True)
    print("=" * 60, flush=True)

    r_reset = safe_post(s, "https://lethoso.tech/api/reset", {
        "fen": "startpos",
        "engine_first": False,
        "model": MODEL,
        "level": LEVEL,
        "movetime_ms": 450
    })
    state = r_reset.json()

    board = chess.Board()
    game1 = chess.pgn.Game()
    game1.headers["Event"] = "Super-Model Titan Clash"
    game1.headers["Site"] = "https://lethoso.tech/"
    game1.headers["White"] = "TrueEngine V1 (Dual Tesla T4)"
    game1.headers["Black"] = "Vanguard Gen-6 Clean-Room (Big)"
    game1.headers["Date"] = time.strftime("%Y.%m.%d")
    node = game1

    ply = 0
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
        san_w = board.san(move_obj)
        board.push(move_obj)
        node = node.add_variation(move_obj)
        ply += 1

        print(f"  ♔ TrueEngine V1: {san_w} ({bestmove}) [{t_te}s]", flush=True)
        for inf in info_lines:
            if "Tesla T4" in inf or "Guardian" in inf or "Book" in inf:
                print(f"    -> {inf}", flush=True)

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
        moves_list = state.get("moves", [])

        if len(moves_list) > ply - 1:
            vg_move_uci = moves_list[-1]
            vg_obj = chess.Move.from_uci(vg_move_uci)
            san_b = board.san(vg_obj)
            board.push(vg_obj)
            node = node.add_variation(vg_obj)
            ply += 1

            vg_info = state.get("last_info", {})
            vg_cp = vg_info.get("score_white", "N/A")
            vg_d = vg_info.get("depth", "N/A")
            vg_nps = vg_info.get("nps", "N/A")
            print(f"  ♚ Vanguard Gen-6: {san_b} ({vg_move_uci}) [{t_vg}s] (Depth {vg_d} | NPS {vg_nps} | Eval {vg_cp} cp)", flush=True)

        if state.get("game_status", {}).get("over", False):
            break

    gs = state.get("game_status", {})
    res1 = gs.get("result", board.result())
    game1.headers["Result"] = res1
    print("\n" + "=" * 50, flush=True)
    print(f"🏁 GAME 1 FINISHED! Result: {res1} ({gs.get('title', '')} - {gs.get('subtitle', '')})", flush=True)
    print("=" * 50, flush=True)

    with open(PGN_PATH, "a", encoding="utf-8") as f:
        f.write(str(game1) + "\n\n")

    # =================================================================
    # GAME 2: Vanguard Gen-6 (White) vs TrueEngine V1 (Black)
    # =================================================================
    print("\n" + "=" * 60, flush=True)
    print(" ♚ GAME 2: Vanguard Gen-6 [WHITE] vs TrueEngine V1 [BLACK]", flush=True)
    print("=" * 60, flush=True)

    r_reset2 = safe_post(s, "https://lethoso.tech/api/reset", {
        "fen": "startpos",
        "engine_first": True,
        "model": MODEL,
        "level": LEVEL,
        "movetime_ms": 450
    })
    state2 = r_reset2.json()

    board2 = chess.Board()
    game2 = chess.pgn.Game()
    game2.headers["Event"] = "Super-Model Titan Clash"
    game2.headers["Site"] = "https://lethoso.tech/"
    game2.headers["White"] = "Vanguard Gen-6 Clean-Room (Big)"
    game2.headers["Black"] = "TrueEngine V1 (Dual Tesla T4)"
    game2.headers["Date"] = time.strftime("%Y.%m.%d")
    node2 = game2

    ply2 = 0
    if state2.get("moves"):
        vg_m1 = state2["moves"][0]
        obj1 = chess.Move.from_uci(vg_m1)
        board2.push(obj1)
        node2 = node2.add_variation(obj1)
        ply2 = 1
        print(f"  ♔ Vanguard Gen-6 (Move 1): {vg_m1}", flush=True)

    while not state2.get("game_status", {}).get("over", False) and ply2 < 120:
        fen = state2.get("fen")
        print(f"\n--- Move {(ply2//2) + 1} ---", flush=True)
        t0 = time.time()
        bestmove, info_lines = trueengine.get_move(fen, nodes=3500)
        t_te = round(time.time() - t0, 2)
        if not bestmove:
            print("No move from TrueEngine!")
            break

        move_obj = chess.Move.from_uci(bestmove)
        san_b = board2.san(move_obj)
        board2.push(move_obj)
        node2 = node2.add_variation(move_obj)
        ply2 += 1

        print(f"  ♚ TrueEngine V1: {san_b} ({bestmove}) [{t_te}s]", flush=True)
        for inf in info_lines:
            if "Tesla T4" in inf or "Guardian" in inf or "Book" in inf:
                print(f"    -> {inf}", flush=True)

        t1 = time.time()
        r_move = safe_post(s, "https://lethoso.tech/api/move", {
            "move": bestmove,
            "reply": True,
            "model": MODEL,
            "level": LEVEL,
            "movetime_ms": 450,
            "expected_hash": state2.get("position_hash")
        })
        t_vg = round(time.time() - t1, 2)

        if not r_move or r_move.status_code != 200:
            print(f"Error from arena: {r_move.status_code if r_move else 'No resp'}")
            break

        state2 = r_move.json()
        moves_list = state2.get("moves", [])

        if len(moves_list) > ply2 - 1:
            vg_move_uci = moves_list[-1]
            vg_obj = chess.Move.from_uci(vg_move_uci)
            san_w = board2.san(vg_obj)
            board2.push(vg_obj)
            node2 = node2.add_variation(vg_obj)
            ply2 += 1

            vg_info = state2.get("last_info", {})
            vg_cp = vg_info.get("score_white", "N/A")
            vg_d = vg_info.get("depth", "N/A")
            vg_nps = vg_info.get("nps", "N/A")
            print(f"  ♔ Vanguard Gen-6: {san_w} ({vg_move_uci}) [{t_vg}s] (Depth {vg_d} | NPS {vg_nps} | Eval {vg_cp} cp)", flush=True)

        if state2.get("game_status", {}).get("over", False):
            break

    gs2 = state2.get("game_status", {})
    res2 = gs2.get("result", board2.result())
    game2.headers["Result"] = res2
    print("\n" + "=" * 50, flush=True)
    print(f"🏁 GAME 2 FINISHED! Result: {res2} ({gs2.get('title', '')} - {gs2.get('subtitle', '')})", flush=True)
    print("=" * 50, flush=True)

    with open(PGN_PATH, "a", encoding="utf-8") as f:
        f.write(str(game2) + "\n\n")

    trueengine.close()
    print(f"\n🎉 TITAN CLASH COMPLETED! Games saved to {PGN_PATH}", flush=True)

if __name__ == "__main__":
    run_vanguard_match()
