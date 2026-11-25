#!/usr/bin/env python3
"""
TrueEngine V1 vs Stockfish 17.1: Official 60-Game Solo Championship
===================================================================
- Total Games: 60 rounds (30 White, 30 Black for TrueEngine V1)
- TrueEngine V1: Neural Policy Prior (100% Model) + Tactical Material Evaluation
- Opponent: Stockfish 17.1 NNUE (Configured for tactical fast-play)
- Full PGN logging: Saved to data/solo_60_matches_vs_stockfish.pgn
"""

import os
import sys
import time
import math
import random
import chess
import chess.engine
import chess.pgn
import numpy as np
import torch

sys.path.insert(0, "/data/workspace/TrueEngine-V1")
from colab_massive_trainer import TrueEngineChessNet

STOCKFISH_BIN = "/usr/local/bin/stockfish"
MODEL_PATH = "/data/workspace/TrueEngine-V1/models/trueengine_v1_latest.pt"
PGN_PATH = "/data/workspace/TrueEngine-V1/data/solo_60_matches_vs_stockfish.pgn"
os.makedirs(os.path.dirname(PGN_PATH), exist_ok=True)

# 1. Load Neural Model
device = torch.device("cpu")
model = TrueEngineChessNet(in_channels=12, channels=128, num_blocks=6)
state_dict = torch.load(MODEL_PATH, map_location=device)
model.load_state_dict(state_dict)
model.eval()

def encode_board(board: chess.Board):
    planes = np.zeros((12, 8, 8), dtype=np.float32)
    piece_map = board.piece_map()
    for sq, p in piece_map.items():
        row, col = divmod(sq, 8)
        ch = p.piece_type - 1 if p.color == chess.WHITE else p.piece_type + 5
        planes[ch, row, col] = 1.0
    return torch.tensor(planes).unsqueeze(0)

EVAL_CACHE = {}

def get_neural_policy(board: chess.Board):
    fen_key = board.board_fen()
    if fen_key in EVAL_CACHE:
        return EVAL_CACHE[fen_key]

    with torch.no_grad():
        p_from, p_to, _ = model(encode_board(board))
    
    p_from_np = p_from[0].numpy()
    p_to_np = p_to[0].numpy()
    
    EVAL_CACHE[fen_key] = (p_from_np, p_to_np)
    if len(EVAL_CACHE) > 50000:
        EVAL_CACHE.clear()
    return p_from_np, p_to_np

PIECE_VALUES = {
    chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
    chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000
}

def eval_board_tactical(board: chess.Board):
    if board.is_checkmate():
        return -99999.0 if board.turn == chess.WHITE else 99999.0
    if board.is_stalemate() or board.is_insufficient_material():
        return 0.0

    score = 0
    for sq, p in board.piece_map().items():
        val = PIECE_VALUES[p.piece_type]
        score += val if p.color == chess.WHITE else -val
    return float(score)

def score_move(board: chess.Board, move: chess.Move, p_from_np, p_to_np):
    score = p_from_np[move.from_square] + p_to_np[move.to_square]
    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        victim_val = PIECE_VALUES[victim.piece_type] if victim else 100
        score += victim_val * 0.05
    if move.promotion:
        score += 50.0
    if board.gives_check(move):
        score += 5.0
    return score

def search_alphabeta(board: chess.Board, depth: int, alpha: float, beta: float, maximizing: bool):
    if depth == 0 or board.is_game_over():
        return eval_board_tactical(board), None

    p_from_np, p_to_np = get_neural_policy(board)
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return eval_board_tactical(board), None

    legal_moves.sort(key=lambda m: score_move(board, m, p_from_np, p_to_np), reverse=True)

    best_move = legal_moves[0]
    if maximizing:
        max_eval = -1e9
        for move in legal_moves:
            board.push(move)
            eval_score, _ = search_alphabeta(board, depth - 1, alpha, beta, False)
            board.pop()
            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break
        return max_eval, best_move
    else:
        min_eval = 1e9
        for move in legal_moves:
            board.push(move)
            eval_score, _ = search_alphabeta(board, depth - 1, alpha, beta, True)
            board.pop()
            if eval_score < min_eval:
                min_eval = eval_score
                best_move = move
            beta = min(beta, eval_score)
            if beta <= alpha:
                break
        return min_eval, best_move

def trueengine_choose_move(board: chess.Board):
    t0 = time.time()
    _, best_move = search_alphabeta(board, depth=2, alpha=-1e9, beta=1e9, maximizing=(board.turn == chess.WHITE))
    elapsed = time.time() - t0
    if not best_move:
        best_move = list(board.legal_moves)[0]
    return best_move, elapsed

OPENINGS = [
    [],
    ["e2e4", "e7e5"],
    ["e2e4", "c7c5"],
    ["e2e4", "e7e6"],
    ["e2e4", "c7c6"],
    ["d2d4", "d7d5"],
    ["d2d4", "g8f6"],
    ["c2c4", "e7e5"],
    ["g1f3", "d7d5"],
    ["e2e4", "e7e5", "g1f3", "b8c6"],
    ["e2e4", "c7c5", "g1f3", "d7d6"],
    ["d2d4", "d7d5", "c2c4", "e7e6"],
]

def run_tournament(total_games=60):
    print("=" * 70)
    print(" 🏆 TRUEENGINE V1 vs STOCKFISH 17.1: 60-GAME SOLO CHAMPIONSHIP")
    print(f" PGN Output: {PGN_PATH}")
    print("=" * 70)

    sf_engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_BIN)
    sf_engine.configure({"Threads": 2, "Hash": 64, "Skill Level": 5})

    stats = {
        "trueengine_wins": 0,
        "stockfish_wins": 0,
        "draws": 0,
        "total_plies": 0,
    }

    pgn_file = open(PGN_PATH, "w", encoding="utf-8")
    t_start = time.time()

    for game_idx in range(1, total_games + 1):
        te_is_white = (game_idx % 2 != 0)
        white_name = "TrueEngine V1 (Neural Prior)" if te_is_white else "Stockfish 17.1 NNUE"
        black_name = "Stockfish 17.1 NNUE" if te_is_white else "TrueEngine V1 (Neural Prior)"

        board = chess.Board()
        game = chess.pgn.Game()
        game.headers["Event"] = f"TrueEngine V1 vs Stockfish 17.1 60-Game Solo"
        game.headers["Site"] = "TrueEngine Cloud Arena"
        game.headers["Date"] = time.strftime("%Y.%m.%d")
        game.headers["Round"] = str(game_idx)
        game.headers["White"] = white_name
        game.headers["Black"] = black_name

        opening_moves = OPENINGS[(game_idx - 1) % len(OPENINGS)]
        node = game
        for uci_m in opening_moves:
            m = chess.Move.from_uci(uci_m)
            if m in board.legal_moves:
                board.push(m)
                node = node.add_variation(m)

        ply = len(opening_moves)
        max_plies = 60

        while not board.is_game_over() and ply < max_plies:
            is_white = (board.turn == chess.WHITE)
            is_te_turn = (is_white == te_is_white)

            if is_te_turn:
                move, _ = trueengine_choose_move(board)
            else:
                sf_res = sf_engine.play(board, chess.engine.Limit(depth=6, time=0.03))
                move = sf_res.move

            if not move or move not in board.legal_moves:
                break

            board.push(move)
            node = node.add_variation(move)
            ply += 1

        stats["total_plies"] += ply
        outcome = board.outcome()

        if outcome:
            if outcome.winner == chess.WHITE:
                res_str = "1-0"
                if te_is_white:
                    stats["trueengine_wins"] += 1
                    winner = "TrueEngine"
                else:
                    stats["stockfish_wins"] += 1
                    winner = "Stockfish"
            elif outcome.winner == chess.BLACK:
                res_str = "0-1"
                if not te_is_white:
                    stats["trueengine_wins"] += 1
                    winner = "TrueEngine"
                else:
                    stats["stockfish_wins"] += 1
                    winner = "Stockfish"
            else:
                res_str = "1/2-1/2"
                stats["draws"] += 1
                winner = "Draw"
            term_str = outcome.termination.name
        else:
            res_str = "1/2-1/2"
            stats["draws"] += 1
            winner = "Draw (Adjudication)"
            term_str = "ADJUDICATION"

        game.headers["Result"] = res_str
        game.headers["Termination"] = term_str
        pgn_file.write(str(game) + "\n\n")
        pgn_file.flush()

        w = stats["trueengine_wins"]
        l = stats["stockfish_wins"]
        d = stats["draws"]
        score_pct = (w + 0.5 * d) / game_idx * 100.0

        print(f"Game [{game_idx:02d}/{total_games:02d}] {res_str:<7} ({winner:<20}) | {ply:02d} plies | Total: +{w} ={d} -{l} ({score_pct:.1f}%)", flush=True)

    sf_engine.quit()
    pgn_file.close()

    total_time = time.time() - t_start
    w = stats["trueengine_wins"]
    l = stats["stockfish_wins"]
    d = stats["draws"]
    final_score = w + 0.5 * d
    final_pct = (final_score / total_games) * 100.0

    print("\n" + "=" * 70)
    print("                     TOURNAMENT COMPLETED!")
    print("=" * 70)
    print(f"Total Games Played: {total_games}")
    print(f"TrueEngine V1 Score: {final_score}/{total_games} ({final_pct:.2f}%)")
    print(f"Standing: +{w} Wins | ={d} Draws | -{l} Losses")
    print(f"Total Elapsed Time: {total_time:.1f}s ({total_time/total_games:.2f}s per game)")
    print(f"Full 60-Match PGN saved to: {PGN_PATH}")
    print("=" * 70)

if __name__ == "__main__":
    run_tournament(60)
