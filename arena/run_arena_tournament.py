import os
import sys
import chess
import chess.engine
import chess.pgn
import datetime

TRUE_ENGINE_EXE = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\dist\TrueEngine_V1.exe"
STOCKFISH_EXE = r"C:\Users\RealTrueHieu\AppData\Roaming\org.encroissant.app\engines\stockfish\stockfish-windows-x86-64-universal.exe"
ARENA_DIR = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\arena"
PGN_OUT = os.path.join(ARENA_DIR, "arena_matches_vs_stockfish.pgn")

OPENINGS = [
    ("Sicilian Najdorf", "1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6"),
    ("King's Indian Defense", "1. d4 Nf6 2. c4 g6 3. Nc3 Bg7 4. e4 d6"),
    ("Ruy Lopez", "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7"),
    ("French Defense", "1. e4 e6 2. d4 d5 3. Nc3 Nf6 4. e5 Nfd7"),
    ("Queen's Gambit Declined", "1. d4 d5 2. c4 e6 3. Nc3 Nf6 4. Bg5 Be7")
]

def play_match(game_num, opening_name, opening_moves_str, true_as_white=True, max_moves=60):
    print(f"\n=======================================================")
    print(f"ARENA MATCH #{game_num}: {opening_name}")
    print(f"White: {'TrueEngine V1' if true_as_white else 'Stockfish 19'}")
    print(f"Black: {'Stockfish 19' if true_as_white else 'TrueEngine V1'}")
    print(f"=======================================================")

    board = chess.Board()
    # Apply opening moves
    for san in opening_moves_str.split():
        if san[0].isdigit() or san.endswith("."):
            continue
        try:
            board.push_san(san)
        except Exception:
            pass

    engine_true = chess.engine.SimpleEngine.popen_uci(TRUE_ENGINE_EXE)
    engine_sf = chess.engine.SimpleEngine.popen_uci(STOCKFISH_EXE)

    # Set TrueEngine options
    engine_true.configure({"Style": "Tal_Dynamic", "HumanNodesBudget": 600})

    game = chess.pgn.Game()
    game.headers["Event"] = "En Croissant Arena Test"
    game.headers["Site"] = "Local PC (GTX 1660 Ti)"
    game.headers["Date"] = datetime.datetime.now().strftime("%Y.%m.%d")
    game.headers["Round"] = str(game_num)
    game.headers["White"] = "TrueEngine V1 (Human GM)" if true_as_white else "Stockfish 19"
    game.headers["Black"] = "Stockfish 19" if true_as_white else "TrueEngine V1 (Human GM)"
    game.headers["Opening"] = opening_name

    node = game
    # Replay opening in PGN
    temp_board = chess.Board()
    for m in board.move_stack:
        node = node.add_variation(m)
        temp_board.push(m)

    move_count = len(board.move_stack)
    result = "*"

    while not board.is_game_over() and move_count < max_moves * 2:
        is_true_turn = (board.turn == chess.WHITE and true_as_white) or (board.turn == chess.BLACK and not true_as_white)
        
        current_engine = engine_true if is_true_turn else engine_sf
        # TrueEngine uses 600 nodes (human speed, ~10ms), Stockfish uses limited time/depth for fair rapid arena
        limit = chess.engine.Limit(nodes=800) if is_true_turn else chess.engine.Limit(time=0.15)

        try:
            res = current_engine.play(board, limit)
            move = res.move
            board.push(move)
            node = node.add_variation(move)
            move_count += 1
            mover_name = "TrueEngine" if is_true_turn else "Stockfish"
            print(f"Move {move_count // 2 + 1}: {mover_name} played {move.uci()}", flush=True)
        except Exception as e:
            print(f"Engine play error: {e}")
            break

    engine_true.quit()
    engine_sf.quit()

    if board.is_checkmate():
        result = "1-0" if board.turn == chess.BLACK else "0-1"
    elif board.is_stalemate() or board.is_insufficient_material() or board.is_fivefold_repetition() or board.is_seventyfive_moves():
        result = "1/2-1/2"
    else:
        result = "1/2-1/2" # Draw by move cap

    game.headers["Result"] = result
    print(f"\nGame #{game_num} Finished. Result: {result}")

    # Append to PGN file
    with open(PGN_OUT, "a", encoding="utf-8") as f:
        print(game, file=f, end="\n\n")

    return result

def run_tournament(num_games=2):
    print("=== STARTING TRUEENGINE V1 VS STOCKFISH 19 ARENA TOURNAMENT ===")
    results = []
    for i in range(num_games):
        op_name, op_moves = OPENINGS[i % len(OPENINGS)]
        true_white = (i % 2 == 0)
        res = play_match(i + 1, op_name, op_moves, true_as_white=true_white, max_moves=35)
        results.append(res)
    
    print("\n=== TOURNAMENT SUMMARY ===")
    print(f"Total Games: {len(results)}")
    print(f"Results: {results}")

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    run_tournament(n)
