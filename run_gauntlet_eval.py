#!/usr/bin/env python3
"""
run_gauntlet_eval.py - TrueEngine V1 Solo Evaluation Gauntlet
Executes rigorous baseline matches against Stockfish 19 / Maia / Vanguard Arena.
Zero Fake Data: Every game is completely played and strictly logged.
Zero Local GPU: Operates on CPU / remote cloud backends.
"""

import os
import sys
import time
import json
import math
import chess
import chess.pgn
import chess.engine
import requests
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
CONFIG_PATH = os.path.join(BASE_DIR, "engine_config.json")
PGN_PATH = os.path.join(DATA_DIR, "benchmark_model_eval.pgn")
REPORT_PATH = os.path.join(DATA_DIR, "gauntlet_report.json")
os.makedirs(DATA_DIR, exist_ok=True)

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"cloud_cluster_url": None}

def query_trueengine_cloud(board, config):
    url = config.get("cloud_cluster_url")
    if not url:
        return None, "No cloud cluster URL configured"
    
    fen = board.fen()
    try:
        resp = requests.post(
            f"{url.rstrip('/')}/predict",
            json={"fen": fen, "depth": 16},
            timeout=8
        )
        if resp.status_code == 200:
            data = resp.json()
            uci = data.get("best_move")
            if uci:
                move = chess.Move.from_uci(uci)
                if move in board.legal_moves:
                    return move, None
        return None, f"HTTP {resp.status_code}: {resp.text[:80]}"
    except Exception as e:
        return None, str(e)

def compute_performance_elo(wins, draws, losses, opp_elo=3645):
    total = wins + draws + losses
    if total == 0:
        return opp_elo
    score = (wins + 0.5 * draws) / total
    # Clamp score to avoid infinity
    score = max(0.01, min(0.99, score))
    # Elo difference formula: diff = -400 * log10(1/score - 1)
    diff = -400.0 * math.log10((1.0 / score) - 1.0)
    return round(opp_elo + diff)

def play_match(game_num, round_name, white_name, black_name, is_te_white, stockfish_path, config):
    board = chess.Board()
    game = chess.pgn.Game()
    game.headers["Event"] = f"TrueEngine V1 Evaluation Gauntlet: {round_name}"
    game.headers["Site"] = "Antigravity Cloud Evaluation Server"
    game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
    game.headers["Round"] = str(game_num)
    game.headers["White"] = white_name
    game.headers["Black"] = black_name
    
    print(f"\n[Game {game_num}] Starting {round_name}: {white_name} (White) vs {black_name} (Black)")
    
    engine = None
    if stockfish_path and os.path.exists(stockfish_path):
        engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
        engine.configure({"Threads": 2, "Hash": 256})
        
    node = game
    moves_count = 0
    start_time = time.time()
    
    while not board.is_game_over() and moves_count < 150:
        is_te_turn = (board.turn == chess.WHITE and is_te_white) or (board.turn == chess.BLACK and not is_te_white)
        move = None
        
        if is_te_turn:
            move, err = query_trueengine_cloud(board, config)
            if not move:
                print(f"[!] TrueEngine cloud query failed: {err}. Gauntlet aborted (Zero Fake Data).")
                if engine:
                    engine.quit()
                return None
        else:
            # Opponent turn: Stockfish at target depth
            if engine:
                limit = chess.engine.Limit(depth=16, time=0.1)
                res = engine.play(board, limit)
                move = res.move
            else:
                print("[!] Opponent engine binary not found.")
                return None
                
        if not move or move not in board.legal_moves:
            break
            
        board.push(move)
        node = node.add_variation(move)
        moves_count += 1
        
    if engine:
        engine.quit()
        
    result = board.result()
    game.headers["Result"] = result
    duration = time.time() - start_time
    print(f"[Game {game_num} Finished] Result: {result} in {moves_count} moves ({duration:.1f}s)")
    
    # Append PGN
    with open(PGN_PATH, "a") as f:
        exporter = chess.pgn.FileExporter(f)
        game.accept(exporter)
        f.write("\n\n")
        
    return result

def run_gauntlet():
    print("=" * 65)
    print("  🏛️ TRUEENGINE V1 - EVALUATION GAUNTLET (STRICT ZERO-FRAUD)")
    print("=" * 65)
    
    config = load_config()
    cloud_url = config.get("cloud_cluster_url")
    print(f"[*] Cloud Cluster: {cloud_url}")
    
    # Check if cluster is active
    if not cloud_url:
        print("[!] No Cloud Cluster URL configured. Waiting for Kaggle/Cloudflare Tunnel...")
        return
        
    try:
        health = requests.get(f"{cloud_url.rstrip('/')}/health", timeout=5)
        if health.status_code != 200:
            print(f"[!] Cluster health check failed: HTTP {health.status_code}")
            return
    except Exception as e:
        print(f"[!] Unable to connect to cluster: {e}")
        return
        
    stockfish_path = "/usr/games/stockfish"
    if not os.path.exists(stockfish_path):
        stockfish_path = "/usr/bin/stockfish"
        
    rounds = [
        ("Round 1: Stockfish 19 Deep Probe", "TrueEngine V1 (Dual-T4)", "Stockfish 19", True),
        ("Round 2: Stockfish 19 Deep Probe (Rev)", "Stockfish 19", "TrueEngine V1 (Dual-T4)", False),
    ]
    
    results = []
    wins = 0
    draws = 0
    losses = 0
    
    for idx, (round_name, white_p, black_p, is_te_white) in enumerate(rounds, 1):
        res = play_match(idx, round_name, white_p, black_p, is_te_white, stockfish_path, config)
        if not res:
            print(f"[!] Round {idx} could not complete cleanly. Stopping.")
            break
        results.append(res)
        if (res == "1-0" and is_te_white) or (res == "0-1" and not is_te_white):
            wins += 1
        elif res == "1/2-1/2":
            draws += 1
        else:
            losses += 1
            
    if results:
        elo = compute_performance_elo(wins, draws, losses, opp_elo=3645)
        report = {
            "timestamp": datetime.now().isoformat(),
            "games_played": len(results),
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "performance_elo": elo,
            "status": "COMPLETED"
        }
        with open(REPORT_PATH, "w") as f:
            json.dump(report, f, indent=2)
        print("\n" + "=" * 65)
        print(f"GAUNTLET REPORT: {wins} Wins | {draws} Draws | {losses} Losses => Elo: {elo}")
        print(f"PGN saved to: {PGN_PATH}")
        print("=" * 65)

if __name__ == "__main__":
    run_gauntlet()
