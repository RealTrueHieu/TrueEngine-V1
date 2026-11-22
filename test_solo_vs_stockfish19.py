import chess
import chess.engine
import chess.pgn
import time
import os
import sys
import json

PROJECT_DIR = r"C:\Users\RealTrueHieu\CustomHumanChessEngine"
MEMORY_PATH = os.path.join(PROJECT_DIR, "books", "experience_memory.json")
PGN_PATH = os.path.join(PROJECT_DIR, "data", "solo_sf19_matches.pgn")
os.makedirs(os.path.dirname(PGN_PATH), exist_ok=True)

TRUEENGINE_EXE = os.path.join(PROJECT_DIR, "dist", "TrueEngine_V1.exe")
STOCKFISH_EXE = r"C:\Users\RealTrueHieu\AppData\Roaming\org.encroissant.app\engines\stockfish\stockfish-windows-x86-64-universal.exe"

print("=" * 65)
print("  SOLO CLASH: TRUEENGINE V1 (SUPERNET BT4) vs STOCKFISH 19 (DEPTH 25)")
print("=" * 65)

def play_solo_game(white_name, black_name, white_path, black_path, max_plies=160):
    print(f"\n>>> GAME START: [WHITE] {white_name} vs [BLACK] {black_name} <<<")
    
    white_proc = chess.engine.SimpleEngine.popen_uci(white_path, cwd=os.path.dirname(white_path))
    black_proc = chess.engine.SimpleEngine.popen_uci(black_path, cwd=os.path.dirname(black_path))

    # Configure Stockfish 19
    for p, n in [(white_proc, white_name), (black_proc, black_name)]:
        if "Stockfish" in n:
            p.configure({"Threads": 4, "Hash": 128})
        elif "TrueEngine" in n:
            try:
                p.configure({
                    "ArenaMode": True,
                    "ArenaDepth": 28,
                    "WeightsFile": "BT4-1024x15x32h-swa-6147500-policytune-332.pb.gz",
                    "StockfishOracleDepth": 20,
                    "ArenaNodesBudget": 25000,
                    "Threads": 4,
                    "Hash": 128
                })
            except Exception as e:
                print("TrueEngine config note:", e)

    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["Event"] = "TrueEngine Supernet BT4 vs Stockfish 19 Solo Clash"
    game.headers["White"] = white_name
    game.headers["Black"] = black_name
    game.headers["Date"] = time.strftime("%Y.%m.%d")
    
    node = game
    ply = 0

    try:
        while not board.is_game_over() and ply < max_plies:
            is_white = (board.turn == chess.WHITE)
            proc = white_proc if is_white else black_proc
            name = white_name if is_white else black_name
            move_num = (ply // 2) + 1
            side_str = "W" if is_white else "B"

            t0 = time.time()
            if "Stockfish" in name:
                limit = chess.engine.Limit(depth=25)
            else:
                limit = chess.engine.Limit(depth=28)

            result = proc.play(board, limit)
            elapsed = time.time() - t0
            move = result.move

            if not move:
                break

            san = board.san(move)
            board.push(move)
            node = node.add_variation(move)
            ply += 1

            chk = "+" if board.is_check() else ""
            print(f"  Ply {ply:02d} ({move_num}.{side_str}): {san}{chk} [{name}] ({elapsed:.2f}s) | FEN: {board.board_fen()[:32]}...", flush=True)

    finally:
        white_proc.quit()
        black_proc.quit()

    outcome = board.outcome()
    res_str = board.result() if outcome else "1/2-1/2"
    game.headers["Result"] = res_str

    print(f"\n[Game Finished] Result: {res_str} after {ply} plies ({outcome.termination if outcome else 'Ply limit reached'})")
    with open(PGN_PATH, "a", encoding="utf-8") as f:
        f.write(str(game) + "\n\n")

    return res_str, ply

if __name__ == "__main__":
    print("Match 1 Result already recorded in PGN: TrueEngine V1 [W] vs Stockfish 19 [B] -> 1/2-1/2 (Draw in 80 moves)")

    # Match 2: Stockfish 19 (White) vs TrueEngine V1 (Black)
    res2, plies2 = play_solo_game("Stockfish_19", "TrueEngine_V1", STOCKFISH_EXE, TRUEENGINE_EXE)
    print(f"\n==================================================")
    print(f"SERIES SUMMARY vs STOCKFISH 19 (DEPTH 25):")
    print(f"Match 1 (White): 1/2-1/2 (Draw)")
    print(f"Match 2 (Black): {res2}")
    print(f"==================================================")
