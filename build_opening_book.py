import os
import json
import chess
import chess.pgn

PGN_DIR = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\data\pgn"
BOOK_PATH = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\books\grandmaster_book.json"

# Key aggressive and legendary champions to prioritize for opening choices
CHAMPION_WEIGHTS = {
    "Tal.pgn": 2.5,          # Maximum attacking fireworks
    "Kasparov.pgn": 2.2,     # High initiative & dynamic sharpness
    "Fischer.pgn": 2.0,      # Crystal-clear attacking classical
    "Carlsen.pgn": 1.5,      # High modern theoretical quality
    "Alekhine.pgn": 1.8,     # Tactical combinations
    "century_immortal_games.pgn": 5.0 # Immortal games highest priority
}

def build_book(max_depth=16, min_occurrences=2):
    print("=== BUILDING GRANDMASTER OPENING BOOK ===")
    opening_tree = {} # fen_epd -> {uci_move: {"weight": float, "wins": int, "total": int, "masters": list}}

    pgn_files = [f for f in os.listdir(PGN_DIR) if f.endswith(".pgn")]
    total_games_processed = 0

    for filename in pgn_files:
        filepath = os.path.join(PGN_DIR, filename)
        weight_mult = CHAMPION_WEIGHTS.get(filename, 1.0)
        master_name = filename.replace(".pgn", "")
        print(f"Processing openings from {filename} (Weight: {weight_mult}x)...")

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            while True:
                # Use read_headers or light game parsing for speed
                game = chess.pgn.read_game(f)
                if game is None:
                    break
                
                total_games_processed += 1
                result = game.headers.get("Result", "*")
                
                board = game.board()
                depth = 0
                for move in game.mainline_moves():
                    if depth >= max_depth:
                        break
                    
                    fen_key = board.epd(use_en_passant=False)
                    uci_str = move.uci()

                    if fen_key not in opening_tree:
                        opening_tree[fen_key] = {}
                    
                    if uci_str not in opening_tree[fen_key]:
                        opening_tree[fen_key][uci_str] = {
                            "weight": 0.0,
                            "count": 0,
                            "masters": []
                        }

                    entry = opening_tree[fen_key][uci_str]
                    entry["count"] += 1
                    entry["weight"] += weight_mult
                    if master_name not in entry["masters"]:
                        entry["masters"].append(master_name)

                    board.push(move)
                    depth += 1

                if total_games_processed % 3000 == 0:
                    print(f"  Processed {total_games_processed} games... (Tree positions: {len(opening_tree)})")

    # Filter out rare moves with count < min_occurrences (keep immortal games)
    filtered_tree = {}
    for fen, moves in opening_tree.items():
        valid_moves = {}
        for m, data in moves.items():
            if data["count"] >= min_occurrences or data["weight"] >= 4.0:
                valid_moves[m] = {
                    "count": data["count"],
                    "weight": round(data["weight"], 1),
                    "masters": data["masters"][:3]
                }
        if valid_moves:
            filtered_tree[fen] = valid_moves

    print(f"\nFinal Opening Book Positions: {len(filtered_tree)} positions from {total_games_processed} games.")
    with open(BOOK_PATH, "w", encoding="utf-8") as out_f:
        json.dump(filtered_tree, out_f, indent=2)

    print(f"Saved opening book to {BOOK_PATH}")

if __name__ == "__main__":
    build_book()
