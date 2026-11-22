import requests
import json
import time
import re
import chess
import chess.pgn
import subprocess
import os

CLOUD_URL = "https://holiday-straight-television-academic.trycloudflare.com"
ENGINE_EXE = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\dist\TrueEngine_V1_Cloud.exe"
PGN_PATH = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\data\vanguard_gen6_clash.pgn"

def recover_game1_pgn():
    log_path = r"C:\Users\RealTrueHieu\.gemini\antigravity-cli\brain\807a9b6f-9861-48a6-9b02-1fc3c6220065\.system_generated\tasks\task-5069.log"
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    # Extract all moves
    # Pattern: ♔ TrueEngine V1: <san> (<uci>) or ♚ Vanguard Gen-6: <san> (<uci>)
    moves_raw = re.findall(r"\(([a-h1-8]{4,5})\)", text)
    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["Event"] = "Super-Model Titan Clash"
    game.headers["Site"] = "https://lethoso.tech/"
    game.headers["Date"] = "2026.11.22"
    game.headers["Round"] = "1"
    game.headers["White"] = "TrueEngine V1 (Dual Tesla T4)"
    game.headers["Black"] = "Vanguard Gen-6 Clean-Room (Big)"
    game.headers["Result"] = "1-0"
    game.headers["Termination"] = "Checkmate"

    node = game
    for uci_move in moves_raw:
        try:
            m = chess.Move.from_uci(uci_move)
            if m in board.legal_moves:
                board.push(m)
                node = node.add_variation(m)
        except Exception:
            pass
    return str(game)

class TrueEngineUCI:
    def __init__(self, exe_path, config_override=None):
        if config_override:
            cfg_path = os.path.join(os.path.dirname(exe_path), "engine_config.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data.update(config_override)
                with open(cfg_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

        self.proc = subprocess.Popen(
            [exe_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        self._send("uci")
        self._read_until("uciok")
        self._send("isready")
        self._read_until("readyok")

    def _send(self, cmd):
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()

    def _read_until(self, target):
        lines = []
        while True:
            line = self.proc.stdout.readline().strip()
            if not line:
                break
            lines.append(line)
            if target in line:
                break
        return lines

    def get_move(self, fen, nodes=3000):
        self._send(f"position fen {fen}")
        self._send(f"go nodes {nodes}")
        lines = []
        bestmove = None
        while True:
            line = self.proc.stdout.readline().strip()
            if not line:
                continue
            lines.append(line)
            if line.startswith("bestmove"):
                parts = line.split()
                if len(parts) > 1:
                    bestmove = parts[1]
                break
        return bestmove, lines

    def close(self):
        try:
            self._send("quit")
            self.proc.terminate()
        except:
            pass

def safe_post(s, url, json_data, retries=5):
    for i in range(retries):
        try:
            time.sleep(0.7)
            r = s.post(url, json=json_data, timeout=20)
            if r.status_code == 429:
                time.sleep(1.2 * (i + 1))
                continue
            return r
        except Exception as e:
            time.sleep(1.0)
    return None

def finish_game2():
    print("Logging into Vanguard Arena...")
    s = requests.Session()
    v_user = os.environ.get("VANGUARD_USER", "truehieu")
    v_pass = os.environ.get("VANGUARD_PASS", "")
    s.post("https://lethoso.tech/api/auth/login", json={"username": v_user, "password": v_pass})
    
    st = s.get("https://lethoso.tech/api/state").json()
    moves_history = st.get("moves", [])
    print(f"Current arena state: {len(moves_history)} moves, Over: {st.get('game_status', {}).get('over')}")
    
    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["Event"] = "Super-Model Titan Clash"
    game.headers["Site"] = "https://lethoso.tech/"
    game.headers["Date"] = "2026.11.22"
    game.headers["Round"] = "2"
    game.headers["White"] = "Vanguard Gen-6 Clean-Room (Big)"
    game.headers["Black"] = "TrueEngine V1 (Dual Tesla T4)"
    
    node = game
    for m_uci in moves_history:
        m = chess.Move.from_uci(m_uci)
        board.push(m)
        node = node.add_variation(m)

    trueengine = TrueEngineUCI(ENGINE_EXE, config_override={"cloud_backend_url": CLOUD_URL})
    
    ply = len(moves_history)
    while not st.get("game_status", {}).get("over", False) and ply < 200:
        fen = board.fen()
        print(f"\n--- Move {(ply//2) + 1} (Black TrueEngine to move) ---", flush=True)
        t0 = time.time()
        bestmove, info_lines = trueengine.get_move(fen, nodes=3000)
        t_te = round(time.time() - t0, 2)
        if not bestmove:
            print("No move returned!")
            break
            
        move_obj = chess.Move.from_uci(bestmove)
        san_b = board.san(move_obj)
        board.push(move_obj)
        node = node.add_variation(move_obj)
        ply += 1
        print(f"  ♚ TrueEngine V1: {san_b} ({bestmove}) [{t_te}s]", flush=True)
        
        if board.is_game_over():
            print("Local board says game over!")
            break
            
        t1 = time.time()
        r_move = safe_post(s, "https://lethoso.tech/api/move", {
            "move": bestmove,
            "reply": True,
            "model": "v6_gen6_big",
            "level": "gen6_full",
            "movetime_ms": 450,
            "expected_hash": st.get("position_hash")
        })
        t_vg = round(time.time() - t1, 2)
        
        if not r_move or r_move.status_code != 200:
            print(f"Arena error: {r_move.status_code if r_move else 'None'}")
            break
            
        st = r_move.json()
        gs = st.get("game_status", {})
        server_moves = st.get("moves", [])
        
        if gs.get("over", False):
            print(f"Server signaled game over: {gs}")
            if len(server_moves) == ply + 1:
                vg_uci = server_moves[-1]
                vg_obj = chess.Move.from_uci(vg_uci)
                san_w = board.san(vg_obj)
                board.push(vg_obj)
                node = node.add_variation(vg_obj)
                ply += 1
                print(f"  ♔ Vanguard Gen-6: {san_w} ({vg_uci}) [{t_vg}s]", flush=True)
            break
            
        if len(server_moves) > ply - 1:
            vg_uci = server_moves[-1]
            vg_obj = chess.Move.from_uci(vg_uci)
            san_w = board.san(vg_obj)
            board.push(vg_obj)
            node = node.add_variation(vg_obj)
            ply += 1
            print(f"  ♔ Vanguard Gen-6: {san_w} ({vg_uci}) [{t_vg}s]", flush=True)

    gs = st.get("game_status", {})
    res = gs.get("result", board.result())
    if board.is_checkmate():
        res = "0-1" if board.turn == chess.WHITE else "1-0"
    game.headers["Result"] = res
    game.headers["Termination"] = gs.get("title", "Game completed")
    print(f"\nGame 2 result: {res}")
    
    trueengine.close()
    return str(game)

if __name__ == "__main__":
    g1_str = recover_game1_pgn()
    print("Game 1 recovered successfully!")
    g2_str = finish_game2()
    
    with open(PGN_PATH, "w", encoding="utf-8") as f:
        f.write(g1_str + "\n\n" + g2_str + "\n")
    print(f"\nAll match PGNs saved to {PGN_PATH}!")
