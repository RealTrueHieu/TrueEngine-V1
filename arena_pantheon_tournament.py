import chess
import chess.engine
import chess.pgn
import time
import os
import sys
import json
import random
import urllib.request

PROJECT_DIR = r"C:\Users\RealTrueHieu\CustomHumanChessEngine"
MEMORY_PATH = os.path.join(PROJECT_DIR, "books", "experience_memory.json")
PGN_OUTPUT = os.path.join(PROJECT_DIR, "data", "pantheon_arena_matches.pgn")
os.makedirs(os.path.dirname(PGN_OUTPUT), exist_ok=True)

BRIDGE_URL = "https://start-throwing-blacks-accommodate.trycloudflare.com"

ENGINES = {
    "TrueEngine_V1": r"C:\Users\RealTrueHieu\CustomHumanChessEngine\dist\TrueEngine_V1.exe",
    "RubiChess": r"C:\Users\RealTrueHieu\AppData\Roaming\org.encroissant.app\engines\RubiChess-20240817\windows\RubiChess-20240817_x86-64-avx2.exe",
    "Lc0": r"C:\Users\RealTrueHieu\Downloads\lc0-v0.33.0-rc0-windows-gpu-nvidia-cuda12\lc0.exe",
    "Komodo_Persona_ShashChess": r"D:\Engines\ShashChess42.3-universal.exe",
    "Stockfish_19": r"C:\Users\RealTrueHieu\AppData\Roaming\org.encroissant.app\engines\stockfish\stockfish-windows-x86-64-universal.exe"
}

def push_to_cloud(fen, move, refutation=""):
    try:
        url = f"{BRIDGE_URL}/push_blunder"
        payload = json.dumps({"fen": fen, "blunder_move": move, "refutation": refutation}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass

def learn_from_match(game, trueengine_color, opponent_name, result):
    """Reinforces experience memory based on match outcome."""
    if not os.path.exists(MEMORY_PATH):
        return

    with open(MEMORY_PATH, "r", encoding="utf-8") as f:
        memory = json.load(f)

    board = game.board()
    moves = list(game.mainline_moves())
    
    score = 1.0 if result == "1-0" and trueengine_color == chess.WHITE else (
        1.0 if result == "0-1" and trueengine_color == chess.BLACK else (
            0.5 if result == "1/2-1/2" else 0.0
        )
    )

    amplified = 0
    vetoed = 0

    for i, m in enumerate(moves):
        fen_key = board.epd(use_en_passant=False)
        m_uci = m.uci()
        turn = board.turn

        if turn == trueengine_color:
            if fen_key not in memory:
                memory[fen_key] = {}
            if m_uci not in memory[fen_key]:
                memory[fen_key][m_uci] = {
                    "visits": 1,
                    "wins": 1 if score == 1.0 else 0,
                    "draws": 1 if score == 0.5 else 0,
                    "losses": 1 if score == 0.0 else 0,
                    "multiplier": 1.0,
                    "blunder": False,
                    "last_updated": int(time.time())
                }

            entry = memory[fen_key][m_uci]
            entry["visits"] += 1

            if score == 1.0:
                entry["wins"] += 1
                entry["multiplier"] = min(3.5, round(entry.get("multiplier", 1.0) * 1.3, 3))
                amplified += 1
            elif score == 0.5:
                entry["draws"] += 1
                entry["multiplier"] = min(2.5, round(entry.get("multiplier", 1.0) * 1.1, 3))
            else:
                entry["losses"] += 1
                # If near the end of lost game, mark blunder
                if i >= len(moves) - 6:
                    entry["blunder"] = True
                    entry["multiplier"] = 0.001
                    vetoed += 1
                    push_to_cloud(fen_key, m_uci, "Match Loss Blunder")

        board.push(m)

    temp_path = MEMORY_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)
    os.replace(temp_path, MEMORY_PATH)

    print(f"[TrueEngine Auto-Learn] Match vs {opponent_name} ({result}): Amplified {amplified} lines, Vetoed {vetoed} blunders. Total Memory: {len(memory):,} positions.", flush=True)

def play_match(white_engine_name, black_engine_name, move_time=0.25, max_moves=100):
    white_path = ENGINES.get(white_engine_name)
    black_path = ENGINES.get(black_engine_name)

    if not os.path.exists(white_path) or not os.path.exists(black_path):
        print(f"Skipping match: Binary not found ({white_engine_name} or {black_engine_name})")
        return None

    print(f"\n=======================================================")
    print(f" PANTHEON CLASH: [WHITE] {white_engine_name} vs [BLACK] {black_engine_name}")
    print(f"=======================================================")

    white_cwd = os.path.dirname(white_path)
    black_cwd = os.path.dirname(black_path)

    white_proc = chess.engine.SimpleEngine.popen_uci(white_path, cwd=white_cwd)
    black_proc = chess.engine.SimpleEngine.popen_uci(black_path, cwd=black_cwd)

    # Configure Arena Full Power mode for TrueEngine V1
    for p, n in [(white_proc, white_engine_name), (black_proc, black_engine_name)]:
        if n == "TrueEngine_V1":
            try:
                p.configure({
                    "ArenaMode": True,
                    "ArenaDepth": 28,
                    "StockfishOracleDepth": 16,
                    "ArenaNodesBudget": 25000
                })
            except Exception:
                pass

    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["Event"] = "TrueEngine Pantheon Grandmaster Clash (Depth 28 Arena Full Power)"
    game.headers["White"] = white_engine_name
    game.headers["Black"] = black_engine_name
    game.headers["Date"] = time.strftime("%Y.%m.%d")

    node = game
    ply = 0

    try:
        while not board.is_game_over() and ply < max_moves * 2:
            current_engine = white_proc if board.turn == chess.WHITE else black_proc
            name = white_engine_name if board.turn == chess.WHITE else black_engine_name
            
            # Arena Full Power: Depth 28
            limit = chess.engine.Limit(depth=28, time=move_time)
            result = current_engine.play(board, limit)
            move = result.move

            if not move:
                break

            san = board.san(move)
            board.push(move)
            node = node.add_variation(move)
            ply += 1

            if ply % 10 == 0 or board.is_check():
                move_num = (ply + 1) // 2
                side = "W" if board.turn == chess.BLACK else "B"
                check_str = "+" if board.is_check() else ""
                print(f"  Ply {ply:02d} ({move_num}.{side}): {san}{check_str} | Board FEN: {board.board_fen()[:30]}...", flush=True)

    finally:
        white_proc.quit()
        black_proc.quit()

    outcome = board.outcome()
    res_str = board.result() if outcome else "1/2-1/2"
    game.headers["Result"] = res_str

    print(f"-------------------------------------------------------")
    print(f" RESULT: {res_str} after {ply} plies ({outcome.termination if outcome else 'Move limit reached'})")
    print(f"-------------------------------------------------------")

    # Append to PGN file
    with open(PGN_OUTPUT, "a", encoding="utf-8") as f:
        f.write(str(game) + "\n\n")

    # Autonomous Learning
    if white_engine_name == "TrueEngine_V1":
        learn_from_match(game, chess.WHITE, black_engine_name, res_str)
    elif black_engine_name == "TrueEngine_V1":
        learn_from_match(game, chess.BLACK, white_engine_name, res_str)

    return res_str

def run_pantheon_gauntlet():
    print("==================================================================")
    print(" TRUEENGINE V1 GRANDMASTER PANTHEON GAUNTLET")
    print(" Opponents: RubiChess 20240817, Leela Chess Zero (Lc0), Komodo/ShashChess")
    print("==================================================================")

    # 1. Match vs RubiChess (White & Black)
    play_match("TrueEngine_V1", "RubiChess", move_time=0.20)
    play_match("RubiChess", "TrueEngine_V1", move_time=0.20)

    # 2. Match vs Leela Chess Zero (White & Black)
    play_match("TrueEngine_V1", "Lc0", move_time=0.20)
    play_match("Lc0", "TrueEngine_V1", move_time=0.20)

    # 3. Match vs Komodo Persona / ShashChess 42.3 (White & Black)
    play_match("TrueEngine_V1", "Komodo_Persona_ShashChess", move_time=0.20)
    play_match("Komodo_Persona_ShashChess", "TrueEngine_V1", move_time=0.20)

    print("\n[Pantheon Gauntlet Completed] All games recorded to data/pantheon_arena_matches.pgn.")

if __name__ == "__main__":
    run_pantheon_gauntlet()
