import os
import urllib.request
import zipfile
import io
import chess.pgn

DATA_DIR = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\data"
PGN_DIR = os.path.join(DATA_DIR, "pgn")
os.makedirs(PGN_DIR, exist_ok=True)

CHAMPIONS = [
    "Kasparov",
    "Fischer",
    "Tal",
    "Carlsen",
    "Karpov",
    "Alekhine",
    "Capablanca",
    "Morphy",
    "Spassky",
    "Botvinnik",
    "Anand",
    "Kramnik",
    "Lasker",
    "Petrosian",
    "Smyslov"
]

CENTURY_GAMES_PGN = """[Event "Third Rosenwald Trophy"]
[Site "New York, NY USA"]
[Date "1956.10.17"]
[EventDate "1956.10.07"]
[Round "8"]
[Result "0-1"]
[White "Donald Byrne"]
[Black "Robert James Fischer"]
[ECO "D92"]
[WhiteElo "?"]
[BlackElo "?"]
[PlyCount "82"]

1. Nf3 Nf6 2. c4 g6 3. Nc3 Bg7 4. d4 O-O 5. Bf4 d5 6. Qb3 dxc4
7. Qxc4 c6 8. e4 Nbd7 9. Rd1 Nb6 10. Qc5 Bg4 11. Bg5 Na4 12. Qa3
Nxc3 13. bxc3 Nxe4 14. Bxe7 Qb6 15. Bc4 Nxc3 16. Bc5 Rfe8+ 17. Kf1
Be6 18. Bxb6 Bxc4+ 19. Kg1 Ne2+ 20. Kf1 Nxd4+ 21. Kg1 Ne2+
22. Kf1 Nc3+ 23. Kg1 axb6 24. Qb4 Ra4 25. Qxb6 Nxd1 26. h3 Rxa2
27. Kh2 Nxf2 28. Re1 Rxe1 29. Qd8+ Bf8 30. Nxe1 Bd5 31. Nf3 Ne4
32. Qb8 b5 33. h4 h5 34. Ne5 Kg7 35. Kg1 Bc5+ 36. Kf1 Ng3+
37. Ke1 Bb4+ 38. Kd1 Bb3+ 39. Kc1 Ne2+ 40. Kb1 Nc3+ 41. Kc1 Rc2# 0-1

[Event "Hoogovens Group A"]
[Site "Wijk aan Zee NED"]
[Date "1999.01.20"]
[Round "4"]
[White "Garry Kasparov"]
[Black "Veselin Topalov"]
[Result "1-0"]
[ECO "B07"]
[PlyCount "87"]

1. e4 d6 2. d4 Nf6 3. Nc3 g6 4. Be3 Bg7 5. Qd2 c6 6. f3 b5 7. Nge2 Nbd7
8. Bh6 Bxh6 9. Qxh6 Bb7 10. a3 e5 11. O-O-O Qe7 12. Kb1 a6 13. Nc1 O-O-O
14. Nb3 exd4 15. Rxd4 c5 16. Rd1 Nb6 17. g3 Kb8 18. Na5 Ba8 19. Bh3 d5
20. Qf4+ Ka7 21. Rhe1 d4 22. Nd5 Nbxd5 23. exd5 Qd6 24. Rxd4 cxd4 25. Re7+ Kb6
26. Qxd4+ Kxa5 27. b4+ Ka4 28. Qc3 Qxd5 29. Ra7 Bb7 30. Rxb7 Qc4 31. Qxf6 Kxa3
32. Qxa6+ Kxb4 33. c3+ Kxc3 34. Qa1+ Kd2 35. Qb2+ Kd1 36. Bf1 Rd2 37. Rd7 Rxd7
38. Bxc4 bxc4 39. Qxh8 Rd3 40. Qa8 c3 41. Qa4+ Ke1 42. f4 f5 43. Kc1 Rd2 44. Qa7 1-0

[Event "The Immortal Game"]
[Site "London ENG"]
[Date "1851.06.21"]
[Round "?"]
[White "Adolf Anderssen"]
[Black "Lionel Kieseritzky"]
[Result "1-0"]
[ECO "C33"]
[PlyCount "45"]

1. e4 e5 2. f4 exf4 3. Bc4 Qh4+ 4. Kf1 b5 5. Bxb5 Nf6 6. Nf3 Qh6 7. d3 Nh5
8. Nh4 Qg5 9. Nf5 c6 10. g4 Nf6 11. Rg1 cxb5 12. h4 Qg6 13. h5 Qg5 14. Qf3 Ng8
15. Bxf4 Qf6 16. Nc3 Bc5 17. Nd5 Qxb2 18. Bd6 Bxg1 19. e5 Qxa1+ 20. Ke2 Na6
21. Nxg7+ Kd8 22. Qf6+ Nxf6 23. Be7# 1-0

[Event "The Evergreen Game"]
[Site "Berlin GER"]
[Date "1852.??.??"]
[Round "?"]
[White "Adolf Anderssen"]
[Black "Jean Dufresne"]
[Result "1-0"]
[ECO "C52"]
[PlyCount "47"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. b4 Bxb4 5. c3 Ba5 6. d4 exd4 7. O-O d3
8. Qb3 Qf6 9. e5 Qg6 10. Re1 Nge7 11. Ba3 b5 12. Qxb5 Rb8 13. Qa4 Bb6
14. Nbd2 Bb7 15. Ne4 Qf5 16. Bxd3 Qh5 17. Nf6+ gxf6 18. exf6 Rg8 19. Rad1 Qxf3
20. Rxe7+ Nxe7 21. Qxd7+ Kxd7 22. Bf5+ Ke8 23. Bd7+ Kf8 24. Bxe7# 1-0

[Event "A Night at the Opera"]
[Site "Paris FRA"]
[Date "1858.10.21"]
[Round "?"]
[White "Paul Morphy"]
[Black "Duke Karl / Count Isouard"]
[Result "1-0"]
[ECO "C41"]
[PlyCount "33"]

1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 6. Bc4 Nf6 7. Qb3 Qe7
8. Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5 11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7
14. Rd1 Qe6 15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8# 1-0
"""

def main():
    print("=== SCRAPING WORLD CHAMPIONS & HISTORICAL MASTER GAMES ===")
    
    # 1. Save Century games
    century_path = os.path.join(PGN_DIR, "century_immortal_games.pgn")
    with open(century_path, "w", encoding="utf-8") as f:
        f.write(CENTURY_GAMES_PGN.strip())
    print(f"Saved legendary immortal games to {century_path}")

    # 2. Download Champion PGNs from PGN Mentor
    total_downloaded = 0
    total_games = 0

    for champ in CHAMPIONS:
        zip_url = f"https://www.pgnmentor.com/players/{champ}.zip"
        target_pgn = os.path.join(PGN_DIR, f"{champ}.pgn")
        
        if os.path.exists(target_pgn) and os.path.getsize(target_pgn) > 1000:
            print(f"[{champ}] Already exists ({os.path.getsize(target_pgn)} bytes)")
            total_downloaded += 1
            continue

        print(f"[{champ}] Downloading from {zip_url}...")
        try:
            req = urllib.request.Request(zip_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
            
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                # Find the pgn file inside
                for name in zf.namelist():
                    if name.lower().endswith(".pgn"):
                        with open(target_pgn, "wb") as out_f:
                            out_f.write(zf.read(name))
                        print(f"[{champ}] Extracted {target_pgn} ({os.path.getsize(target_pgn)} bytes)")
                        total_downloaded += 1
                        break
        except Exception as e:
            print(f"[{champ}] Failed: {e}")

    # 3. Analyze dataset
    print("\n=== ANALYZING COLLECTED MASTER DATASET ===")
    summary = {}
    for filename in os.listdir(PGN_DIR):
        if filename.endswith(".pgn"):
            filepath = os.path.join(PGN_DIR, filename)
            count = 0
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                while True:
                    game = chess.pgn.read_game(f)
                    if game is None:
                        break
                    count += 1
            summary[filename] = count
            total_games += count
            print(f"  - {filename}: {count:,} games")

    print(f"\nTOTAL MASTER GAMES COLLECTED: {total_games:,} across {len(summary)} files!")
    
    # Save metadata summary
    with open(os.path.join(DATA_DIR, "dataset_summary.txt"), "w", encoding="utf-8") as f:
        f.write(f"Total Grandmaster & Century Games: {total_games}\n\n")
        for k, v in summary.items():
            f.write(f"{k}: {v} games\n")

if __name__ == "__main__":
    main()
