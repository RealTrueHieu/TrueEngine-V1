import os
import json
import chess
import chess.pgn
import io

print("=== COMPILING HISTORICAL CHESS MASTERPIECES (1475 - 2026) ===")

HISTORICAL_GAMES_PGN = """
[Event "Oldest Recorded Modern Chess Game"]
[Site "Valencia, Spain"]
[Date "1475.??.??"]
[White "Francesc de Castellvi"]
[Black "Narcis Vinyoles"]
[Result "1-0"]

1. e4 d5 2. exd5 Qxd5 3. Nc3 Qd8 4. Bc4 Nf6 5. Nf3 Bg4 6. h3 Bxf3 7. Qxf3 e6 8. Qxb7 Nbd7 9. Nb5 Rc8 10. Nxa7 Nb6 11. Nxc8 Nxc8 12. d4 Nd6 13. Bb5+ Nxb5 14. Qxb5+ Nd7 15. d5 exd5 16. Be3 Bd6 17. Rd1 Qf6 18. Rxd5 Qg6 19. Bf4 Bxf4 20. Qxd7+ Kf8 21. Qd8# 1-0

[Event "Ruy Lopez Masterpiece"]
[Site "Madrid, Spain"]
[Date "1560.??.??"]
[White "Ruy Lopez de Segura"]
[Black "Leonardo da Cutri"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Bxc6 dxc6 5. O-O Bg4 6. h3 h5 7. d3 Qf6 8. Be3 Bxf3 9. Qxf3 Qxf3 10. gxf3 Bd6 11. Nd2 Ne7 12. Nc4 Ng6 13. f4 exf4 14. Bd4 f6 15. Nxd6+ cxd6 16. f3 Kf7 17. Kf2 c5 18. Bc3 b5 19. b3 a5 20. Rg1 b4 21. Bb2 a4 22. a3 axb3 23. cxb3 Rhb8 24. a4 Ne5 25. Bxe5 dxe5 26. Rac1 Ra5 27. Rc4 Rd8 28. Ke2 g5 29. Rgc1 g4 30. hxg4 hxg4 31. fxg4 Rh8 32. Rxc5 Rh2+ 33. Kf3 Rxc5 34. Rxc5 Rh3+ 35. Ke2 Re3+ 36. Kd2 Rg3 37. a5 Rg2+ 38. Ke1 Ra2 39. g5 fxg5 40. Rxe5 Kf6 41. Rf5+ Kg6 42. d4 Ra3 43. Rb5 Rxb3 44. a6 Ra3 45. Rxb4 Rxa6 46. Rb5 Ra2 47. Rf5 Ra4 48. Rd5 g4 49. Kf2 Ra2+ 50. Kf1 g3 51. Rf5 Rf2+ 52. Kg1 f3 53. d5 Rg2+ 54. Kf1 Rf2+ 55. Kg1 1/2-1/2

[Event "Greco Immortal Sacrifice"]
[Site "Rome, Italy"]
[Date "1620.??.??"]
[White "Gioachino Greco"]
[Black "NN"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d4 exd4 6. cxd4 Bb4+ 7. Nc3 Nxe4 8. O-O Nxc3 9. bxc3 Bxc3 10. Qb3 Bxa1 11. Bxf7+ Kf8 12. Bg5 Ne7 13. Ne5 Bxd4 14. Bg6 d5 15. Qf3+ Bf5 16. Bxf5 Bxe5 17. Be6+ Bf6 18. Bxf6 gxf6 19. Qxf6+ Ke8 20. Qf7# 1-0

[Event "Philidor Pawn Coordination"]
[Site "London, England"]
[Date "1749.??.??"]
[White "Francois-Andre Danican Philidor"]
[Black "Philip Stamma"]
[Result "1-0"]

1. e4 e5 2. Bc4 Bc5 3. c3 Nf6 4. d3 c6 5. Qe2 d6 6. f4 exf4 7. Bxf4 O-O 8. Nf3 Bg4 9. Nbd2 Nbd7 10. d4 Bb6 11. Bxd6 Re8 12. e5 Nd5 13. O-O f6 14. Qe4 Be6 15. Kh1 fxe5 16. dxe5 Nc5 17. Bxc5 Bxc5 18. Nd4 Bxd4 19. cxd4 Qg5 20. Nf3 Qh6 21. Rae1 Rad8 22. a3 Kh8 23. Qh4 Qxh4 24. Nxh4 Ne3 25. Rxe3 Bxc4 26. Rf4 g5 27. Rg4 gxh4 28. Rxh4 c5 29. Reh3 Bg8 30. Rd3 cxd4 31. Rhxd4 Rxd4 32. Rxd4 Rxe5 33. h3 Rd5 34. Rb4 b5 35. Kh2 a5 36. Re4 Rd2 37. b4 a4 38. Re3 Bc4 39. Re8+ Kg7 40. Re7+ Kg6 41. Re3 Rd3 42. Rxd3 Bxd3 1-0

[Event "The Immortal Game"]
[Site "London, England"]
[Date "1851.06.21"]
[White "Adolf Anderssen"]
[Black "Lionel Kieseritzky"]
[Result "1-0"]

1. e4 e5 2. f4 exf4 3. Bc4 Qh4+ 4. Kf1 b5 5. Bxb5 Nf6 6. Nf3 Qh6 7. d3 Nh5 8. Nh4 Qg5 9. Nf5 c6 10. g4 Nf6 11. Rg1 cxb5 12. h4 Qg6 13. h5 Qg5 14. Qf3 Ng8 15. Bxf4 Qf6 16. Nc3 Bc5 17. Nd5 Qxb2 18. Bd6 Bxg1 19. e5 Qxa1+ 20. Ke2 Na6 21. Nxg7+ Kd8 22. Qf6+ Nxf6 23. Be7# 1-0

[Event "The Evergreen Game"]
[Site "Berlin, Germany"]
[Date "1852.??.??"]
[White "Adolf Anderssen"]
[Black "Jean Dufresne"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. b4 Bxb4 5. c3 Ba5 6. d4 exd4 7. O-O d3 8. Qb3 Qf6 9. e5 Qg6 10. Re1 Nge7 11. Ba3 b5 12. Qxb5 Rb8 13. Qa4 Bb6 14. Nbd2 Bb7 15. Ne4 Qf5 16. Bxd3 Qh5 17. Nf6+ gxf6 18. exf6 Rg8 19. Rad1 Qxf3 20. Rxe7+ Nxe7 21. Qxd7+ Kxd7 22. Bf5+ Ke8 23. Bd7+ Kf8 24. Bxe7# 1-0

[Event "The Opera Game"]
[Site "Paris, France"]
[Date "1858.11.02"]
[White "Paul Morphy"]
[Black "Duke Karl of Brunswick and Count Isouard"]
[Result "1-0"]

1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 6. Bc4 Nf6 7. Qb3 Qe7 8. Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5 11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7 14. Rd1 Qe6 15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8# 1-0

[Event "Kasparov's Immortal Game"]
[Site "Wijk aan Zee, Netherlands"]
[Date "1999.01.20"]
[White "Garry Kasparov"]
[Black "Veselin Topalov"]
[Result "1-0"]

1. e4 d6 2. d4 Nf6 3. Nc3 g6 4. Be3 Bg7 5. Qd2 c6 6. f3 b5 7. Nge2 Nbd7 8. Bh6 Bxh6 9. Qxh6 Bb7 10. a3 e5 11. O-O-O Qe7 12. Kb1 a6 13. Nc1 O-O-O 14. Nb3 exd4 15. Rxd4 c5 16. Rd1 Nb6 17. g3 Kb8 18. Na5 Ba8 19. Bh3 d5 20. Qf4+ Ka7 21. Rhe1 d4 22. Nd5 Nbxd5 23. exd5 Qd6 24. Rxd4 cxd4 25. Re7+ Kb6 26. Qxd4+ Kxa5 27. b4+ Ka4 28. Qc3 Qxd5 29. Ra7 Bb7 30. Rxb7 Qc4 31. Qxf6 Kxa3 32. Qxa6+ Kxb4 33. c3+ Kxc3 34. Qa1+ Kd2 35. Qb2+ Kd1 36. Bf1 Rd2 37. Rd7 Rxd7 38. Bxc4 bxc4 39. Qxh8 Rd3 40. Qa8 c3 41. Qa4+ Ke1 42. f4 f5 43. Kc1 Rd2 44. Qa7 1-0

[Event "Bobby Fischer Game of the Century"]
[Site "New York, USA"]
[Date "1956.10.17"]
[White "Donald Byrne"]
[Black "Robert James Fischer"]
[Result "0-1"]

1. Nf3 Nf6 2. c4 g6 3. Nc3 Bg7 4. d4 O-O 5. Bf4 d5 6. Qb3 dxc4 7. Qxc4 c6 8. e4 Nbd7 9. Rd1 Nb6 10. Qc5 Bg4 11. Bg5 Na4 12. Qa3 Nxc3 13. bxc3 Nxe4 14. Bxe7 Qb6 15. Bc4 Nxc3 16. Bc5 Rfe8+ 17. Kf1 Be6 18. Bxb6 Bxc4+ 19. Kg1 Ne2+ 20. Kf1 Nxd4+ 21. Kg1 Ne2+ 22. Kf1 Nc3+ 23. Kg1 axb6 24. Qb4 Ra4 25. Qxb6 Nxd1 26. h3 Rxa2 27. Kh2 Nxf2 28. Re1 Rxe1 29. Qd8+ Bf8 30. Nxe1 Bd5 31. Nf3 Ne4 32. Qb8 b5 33. h4 h5 34. Ne5 Kg7 35. Kg1 Bc5+ 36. Kf1 Ng3+ 37. Ke1 Bb4+ 38. Kd1 Bb3+ 39. Kc1 Ne2+ 40. Kb1 Nc3+ 41. Kc1 Rc2# 0-1
"""

def extract_positions_from_pgn(pgn_text):
    positions = {}
    pgn_io = io.StringIO(pgn_text)
    game_count = 0

    while True:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            break
        game_count += 1
        headers = game.headers
        white = headers.get("White", "Unknown")
        black = headers.get("Black", "Unknown")
        event = headers.get("Event", "Masterpiece")
        result = headers.get("Result", "*")

        board = game.board()
        for move in game.mainline_moves():
            epd = board.epd(use_en_passant=False)
            move_uci = move.uci()
            
            if epd not in positions:
                positions[epd] = {}
            
            if move_uci not in positions[epd]:
                positions[epd][move_uci] = {
                    "weight": 3.0,
                    "masters": [white if board.turn == chess.WHITE else black],
                    "events": [event],
                    "games": 1
                }
            else:
                positions[epd][move_uci]["weight"] += 1.0
                positions[epd][move_uci]["games"] += 1
                master_name = white if board.turn == chess.WHITE else black
                if master_name not in positions[epd][move_uci]["masters"]:
                    positions[epd][move_uci]["masters"].append(master_name)

            board.push(move)

    print(f"[Extractor] Extracted {len(positions)} unique positions across {game_count} legendary games.")
    return positions

def main():
    positions = extract_positions_from_pgn(HISTORICAL_GAMES_PGN)
    
    out_path = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\books\historical_masterpieces.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(positions, f, indent=2)
    print(f"[Done] Saved historical masterpieces to: {out_path}")

    # Merge into grandmaster_book.json
    gm_book_path = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\books\grandmaster_book.json"
    if os.path.exists(gm_book_path):
        with open(gm_book_path, "r", encoding="utf-8") as f:
            gm_book = json.load(f)
        
        merged_moves = 0
        for epd, moves in positions.items():
            if epd not in gm_book:
                gm_book[epd] = moves
                merged_moves += len(moves)
            else:
                for m, d in moves.items():
                    if m not in gm_book[epd]:
                        gm_book[epd][m] = d
                        merged_moves += 1
                    else:
                        gm_book[epd][m]["weight"] = max(gm_book[epd][m].get("weight", 1.0), d["weight"])
                        for master in d.get("masters", []):
                            if master not in gm_book[epd][m].setdefault("masters", []):
                                gm_book[epd][m]["masters"].append(master)

        with open(gm_book_path, "w", encoding="utf-8") as f:
            json.dump(gm_book, f, indent=2)
        print(f"[Book Augmented] Integrated historical lines into {gm_book_path} ({merged_moves} moves merged).")

if __name__ == "__main__":
    main()
