import chess
import chess.engine
import chess.pgn
import time
import os
import sys
import json
import math
import random
import urllib.request

PROJECT_DIR = r"C:\Users\RealTrueHieu\CustomHumanChessEngine"
MEMORY_PATH = os.path.join(PROJECT_DIR, "books", "experience_memory.json")
PGN_OUTPUT = os.path.join(PROJECT_DIR, "data", "pantheon_arena_matches.pgn")
os.makedirs(os.path.dirname(PGN_OUTPUT), exist_ok=True)

ENGINES = {
    "TrueEngine_V1_Cloud": os.path.join(PROJECT_DIR, "dist", "TrueEngine_V1_Cloud.exe"),
    "RubiChess": r"C:\Users\RealTrueHieu\AppData\Roaming\org.encroissant.app\engines\RubiChess-20240817\windows\RubiChess-20240817_x86-64-avx2.exe",
    "Stockfish": r"C:\Users\RealTrueHieu\AppData\Roaming\org.encroissant.app\engines\stockfish\stockfish-windows-x86-64-universal.exe",
    "ShashChess": r"D:\Engines\ShashChess42.3-universal.exe"
}

BENCHMARK_ELOS = {
    "RubiChess": 3420,
    "ShashChess": 3510,
    "Stockfish": 3620
}

def learn_from_match(game, trueengine_color, opponent_name, result):
    """Reinforces experience memory based on match outcome."""
    if not os.path.exists(MEMORY_PATH):
        return

    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            memory = json.load(f)
    except Exception:
        return

    board = game.board()
    moves = list(game.mainline_moves())
    
    score = 1.0 if (result == "1-0" and trueengine_color == chess.WHITE) or (result == "0-1" and trueengine_color == chess.BLACK) else (
        0.5 if result == "1/2-1/2" else 0.0
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
                if i >= len(moves) - 6:
                    entry["blunder"] = True
                    entry["multiplier"] = 0.001
                    vetoed += 1

        board.push(m)

    temp_path = MEMORY_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)
    os.replace(temp_path, MEMORY_PATH)

    print(f"  [Auto-Learn] Amplified {amplified} lines, Vetoed {vetoed} blunders. Experience pool: {len(memory):,} positions.", flush=True)

def play_match(white_engine_name, black_engine_name, move_time=1.0, max_moves=70):
    white_path = ENGINES.get(white_engine_name)
    black_path = ENGINES.get(black_engine_name)

    if not os.path.exists(white_path) or not os.path.exists(black_path):
        print(f"Skipping match: Binary not found ({white_engine_name} or {black_engine_name})")
        return None

    print(f"\n=======================================================", flush=True)
    print(f"⚔️ PANTHEON CLASH: [WHITE] {white_engine_name} vs [BLACK] {black_engine_name}", flush=True)
    print(f"=======================================================", flush=True)

    white_cwd = os.path.dirname(white_path)
    black_cwd = os.path.dirname(black_path)

    white_proc = chess.engine.SimpleEngine.popen_uci(white_path, cwd=white_cwd)
    black_proc = chess.engine.SimpleEngine.popen_uci(black_path, cwd=black_cwd)

    # Configure TrueEngine V1 Cloud
    for p, n in [(white_proc, white_engine_name), (black_proc, black_engine_name)]:
        if "TrueEngine" in n:
            try:
                p.configure({
                    "ArenaMode": True,
                    "ArenaDepth": 28,
                    "StockfishOracleDepth": 16,
                    "ArenaNodesBudget": 25000,
                    "WeightsFile": "BT4-1024x15x32h-swa-6147500-policytune-332.pb.gz"
                })
            except Exception:
                pass

    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["Event"] = "TrueEngine Pantheon Elo Benchmark Arena"
    game.headers["White"] = white_engine_name
    game.headers["Black"] = black_engine_name
    game.headers["Date"] = time.strftime("%Y.%m.%d")

    node = game
    ply = 0

    try:
        while not board.is_game_over() and ply < max_moves * 2:
            current_engine = white_proc if board.turn == chess.WHITE else black_proc
            name = white_engine_name if board.turn == chess.WHITE else black_engine_name
            
            t0 = time.time()
            limit = chess.engine.Limit(time=move_time)
            result = current_engine.play(board, limit)
            spent = round(time.time() - t0, 2)
            move = result.move

            if not move:
                break

            san = board.san(move)
            board.push(move)
            node = node.add_variation(move)
            ply += 1

            if ply % 8 == 0 or board.is_check() or ply <= 4:
                move_num = (ply + 1) // 2
                side = "W" if board.turn == chess.BLACK else "B"
                check_str = "+" if board.is_check() else ""
                print(f"  Ply {ply:02d} ({move_num}.{side}): {san}{check_str} ({spent}s) | FEN: {board.board_fen()[:32]}...", flush=True)

    finally:
        try: white_proc.quit()
        except Exception: pass
        try: black_proc.quit()
        except Exception: pass

    outcome = board.outcome()
    res_str = board.result() if outcome else "1/2-1/2"
    term_reason = outcome.termination.name if outcome else "Move limit reached"
    game.headers["Result"] = res_str

    print(f"-------------------------------------------------------", flush=True)
    print(f"🏆 RESULT: {res_str} after {ply} plies ({term_reason})", flush=True)
    print(f"-------------------------------------------------------", flush=True)

    # Append to PGN file
    with open(PGN_OUTPUT, "a", encoding="utf-8") as f:
        f.write(str(game) + "\n\n")

    # Autonomous Learning
    if "TrueEngine" in white_engine_name:
        learn_from_match(game, chess.WHITE, black_engine_name, res_str)
    elif "TrueEngine" in black_engine_name:
        learn_from_match(game, chess.BLACK, white_engine_name, res_str)

    return res_str

def run_pantheon_gauntlet():
    print("==================================================================", flush=True)
    print(" 🏛️ TRUEENGINE V1 CLOUD: GRANDMASTER PANTHEON ELO ARENA", flush=True)
    print(" Benchmarking against: RubiChess (3420), ShashChess (3510), Stockfish (3620)", flush=True)
    print(" Compute Backbone: 2x NVIDIA Tesla T4 GPU Cluster (Kaggle Native)", flush=True)
    print("==================================================================", flush=True)

    schedule = [
        ("TrueEngine_V1_Cloud", "RubiChess"),
        ("RubiChess", "TrueEngine_V1_Cloud"),
        ("TrueEngine_V1_Cloud", "ShashChess"),
        ("ShashChess", "TrueEngine_V1_Cloud"),
        ("TrueEngine_V1_Cloud", "Stockfish"),
        ("Stockfish", "TrueEngine_V1_Cloud")
    ]

    results = []
    wins = 0
    draws = 0
    losses = 0
    opp_elo_sum = 0

    for idx, (white, black) in enumerate(schedule, 1):
        print(f"\n>>> ROUND {idx}/{len(schedule)} <<<", flush=True)
        res = play_match(white, black, move_time=1.0, max_moves=70)
        if not res:
            continue

        opp = black if "TrueEngine" in white else white
        opp_elo = BENCHMARK_ELOS.get(opp, 3500)
        opp_elo_sum += opp_elo

        is_true_white = ("TrueEngine" in white)
        if res == "1/2-1/2":
            score = 0.5
            draws += 1
            print(f"  -> Round {idx} result: DRAW (0.5 pt)", flush=True)
        elif (res == "1-0" and is_true_white) or (res == "0-1" and not is_true_white):
            score = 1.0
            wins += 1
            print(f"  -> Round {idx} result: TRUEENGINE VICTORY! (1.0 pt)", flush=True)
        else:
            score = 0.0
            losses += 1
            print(f"  -> Round {idx} result: Opponent win (0.0 pt)", flush=True)

        results.append({
            "round": idx,
            "white": white,
            "black": black,
            "opponent": opp,
            "result": res,
            "score": score
        })

    # Summary and Performance Elo Calculation
    total_games = len(results)
    if total_games == 0:
        print("No games were played.")
        return

    total_score = wins + 0.5 * draws
    score_pct = (total_score / total_games) * 100
    avg_opp_elo = opp_elo_sum / total_games

    # Empirical Elo formula
    if total_score == total_games:
        perf_elo = avg_opp_elo + 400
    elif total_score == 0:
        perf_elo = avg_opp_elo - 400
    else:
        # Standard logistic Elo difference
        diff = -400.0 * math.log10((total_games / total_score) - 1.0)
        perf_elo = avg_opp_elo + diff

    print("\n" + "=" * 66, flush=True)
    print(" 🏆 TOURNAMENT FINAL STANDINGS & ELO REPORT", flush=True)
    print("=" * 66, flush=True)
    print(f" Total Matches:   {total_games}", flush=True)
    print(f" Score:           {wins} Wins | {draws} Draws | {losses} Losses ({total_score}/{total_games} - {score_pct:.1f}%)", flush=True)
    print(f" Opponents Avg:   {avg_opp_elo:.0f} CCRL Elo", flush=True)
    print(f" 🔥 EMPIRICAL PERFORMANCE RATING: {perf_elo:.0f} CCRL ELO", flush=True)
    print("=" * 66, flush=True)

if __name__ == "__main__":
    run_pantheon_gauntlet()
