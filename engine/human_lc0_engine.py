import sys
import os
import subprocess
import time
import random
import json
import chess

LC0_DIR = r"C:\Users\RealTrueHieu\Downloads\lc0-v0.33.0-rc0-windows-gpu-nvidia-cuda12"
LC0_EXE = os.path.join(LC0_DIR, "lc0.exe")
DEFAULT_WEIGHTS = "maia-1900.pb.gz"
BOOK_PATH = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\books\grandmaster_book.json"

class HumanLc0Engine:
    def __init__(self):
        self.lc0_proc = None
        self.board = chess.Board()
        self.book = {}
        self.book_enabled = True
        self.style = "Tal_Dynamic" # Options: Tal_Dynamic, Fischer_Aggressive, Kasparov_Initiative, Pure_Maia
        self.weights_file = DEFAULT_WEIGHTS
        self.human_nodes_budget = 600
        self.load_book()
        self.start_lc0()

    def load_book(self):
        if os.path.exists(BOOK_PATH):
            try:
                with open(BOOK_PATH, "r", encoding="utf-8") as f:
                    self.book = json.load(f)
            except Exception as e:
                self.book = {}

    def start_lc0(self):
        if self.lc0_proc:
            try:
                self.lc0_proc.terminate()
            except Exception:
                pass

        weights_path = os.path.join(LC0_DIR, self.weights_file)
        if not os.path.exists(weights_path):
            weights_path = self.weights_file

        cmd = [
            LC0_EXE,
            f"--weights={weights_path}",
            "--backend=cuda-fp16",
            "--minibatch-size=256",
            "--threads=4",
            "--max-prefetch=64",
            "--nncache=2000000",
            "--policy-softmax-temp=1.35",
            "--cpuct=1.85",
            "--fpu-strategy=reduction",
            "--fpu-value=0.4"
        ]

        self.lc0_proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=LC0_DIR
        )

        # Send uci and isready to lc0
        self.send_to_lc0("uci")
        while True:
            line = self.lc0_proc.stdout.readline()
            if not line or "uciok" in line:
                break
        
        self.send_to_lc0("isready")
        while True:
            line = self.lc0_proc.stdout.readline()
            if not line or "readyok" in line:
                break

    def send_to_lc0(self, cmd):
        if self.lc0_proc and self.lc0_proc.stdin:
            self.lc0_proc.stdin.write(cmd + "\n")
            self.lc0_proc.stdin.flush()

    def query_book(self):
        if not self.book_enabled or not self.book:
            return None

        fen_key = self.board.epd(use_en_passant=False)
        if fen_key in self.book:
            candidates = self.book[fen_key]
            if not candidates:
                return None

            moves = []
            weights = []
            for move_uci, data in candidates.items():
                try:
                    move_obj = chess.Move.from_uci(move_uci)
                    if move_obj in self.board.legal_moves:
                        w = data.get("weight", 1.0)
                        masters = data.get("masters", [])
                        
                        # Style prioritization
                        if self.style == "Tal_Dynamic" and "Tal" in masters:
                            w *= 3.0
                        elif self.style == "Fischer_Aggressive" and "Fischer" in masters:
                            w *= 3.0
                        elif self.style == "Kasparov_Initiative" and "Kasparov" in masters:
                            w *= 3.0

                        moves.append((move_uci, masters))
                        weights.append(w)
                except Exception:
                    continue

            if moves:
                chosen_move, masters = random.choices(moves, weights=weights, k=1)[0]
                master_str = ", ".join(masters) if masters else "Grandmaster Book"
                return chosen_move, master_str

        return None

    def search_bestmove(self, go_cmd):
        # 1. Check opening book first
        book_res = self.query_book()
        if book_res:
            chosen_uci, master_str = book_res
            print(f"info string [Book] Played in history by {master_str}", flush=True)
            # Add human delay (0.05 - 0.2s)
            time.sleep(random.uniform(0.05, 0.15))
            return chosen_uci

        # 2. Parse time controls and determine search nodes
        tokens = go_cmd.split()
        allocated_nodes = self.human_nodes_budget

        # If user explicitly passed 'nodes', honor it
        if "nodes" in tokens:
            idx = tokens.index("nodes")
            if idx + 1 < len(tokens):
                try:
                    allocated_nodes = int(tokens[idx + 1])
                except ValueError:
                    pass
        elif "movetime" in tokens:
            idx = tokens.index("movetime")
            if idx + 1 < len(tokens):
                try:
                    mt = int(tokens[idx + 1])
                    # 90k NPS on 1660Ti, allocate realistic nodes
                    allocated_nodes = min(self.human_nodes_budget, max(50, int(mt * 90)))
                except ValueError:
                    pass
        elif "wtime" in tokens and "btime" in tokens:
            # Dynamic time management
            is_white = (self.board.turn == chess.WHITE)
            time_key = "wtime" if is_white else "btime"
            inc_key = "winc" if is_white else "binc"
            
            my_time = 60000
            my_inc = 0
            if time_key in tokens:
                my_time = int(tokens[tokens.index(time_key) + 1])
            if inc_key in tokens:
                my_inc = int(tokens[tokens.index(inc_key) + 1])
            
            # Target ~2% - 3% of remaining time
            target_ms = (my_time / 35.0) + (my_inc * 0.75)
            # Bound nodes for human feel and rapid speed on 1660Ti
            allocated_nodes = int(min(2500, max(150, target_ms * 90)))

        # Send search command to Lc0
        search_cmd = f"go nodes {allocated_nodes}"
        self.send_to_lc0(search_cmd)

        bestmove = None
        while True:
            line = self.lc0_proc.stdout.readline()
            if not line:
                break
            line_str = line.strip()
            if line_str.startswith("info"):
                print(line_str, flush=True)
            elif line_str.startswith("bestmove"):
                parts = line_str.split()
                if len(parts) >= 2:
                    bestmove = parts[1]
                break

        return bestmove

    def run(self):
        while True:
            try:
                line = sys.stdin.readline()
            except Exception:
                break
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            if line == "uci":
                print("id name Human-Lc0 GM Turbo (GTX 1660Ti)", flush=True)
                print("id author Antigravity & Leela Chess Zero", flush=True)
                print("option name Style type combo default Tal_Dynamic var Tal_Dynamic var Fischer_Aggressive var Kasparov_Initiative var Pure_Maia", flush=True)
                print("option name HumanNodesBudget type spin default 600 min 1 max 50000", flush=True)
                print(f"option name WeightsFile type combo default {DEFAULT_WEIGHTS} var maia-1900.pb.gz var maia-1500.pb.gz var maia-1100.pb.gz var BT4-1024x15x32h-swa-6147500-policytune-332.pb.gz", flush=True)
                print("option name BookEnabled type check default true", flush=True)
                print("uciok", flush=True)

            elif line == "isready":
                self.send_to_lc0("isready")
                while True:
                    l = self.lc0_proc.stdout.readline()
                    if not l or "readyok" in l:
                        break
                print("readyok", flush=True)

            elif line == "ucinewgame":
                self.board.reset()
                self.send_to_lc0("ucinewgame")

            elif line.startswith("setoption"):
                parts = line.split()
                if "name" in parts and "value" in parts:
                    name_idx = parts.index("name") + 1
                    val_idx = parts.index("value") + 1
                    name = " ".join(parts[name_idx:parts.index("value")])
                    val = " ".join(parts[val_idx:])

                    if name == "Style":
                        self.style = val
                    elif name == "HumanNodesBudget":
                        self.human_nodes_budget = int(val)
                    elif name == "BookEnabled":
                        self.book_enabled = (val.lower() == "true")
                    elif name == "WeightsFile":
                        self.weights_file = val
                        self.start_lc0()

            elif line.startswith("position"):
                self.board.reset()
                parts = line.split()
                if "startpos" in parts:
                    if "moves" in parts:
                        moves_idx = parts.index("moves") + 1
                        for m_str in parts[moves_idx:]:
                            self.board.push_uci(m_str)
                elif "fen" in parts:
                    moves_idx = parts.index("moves") if "moves" in parts else len(parts)
                    fen_str = " ".join(parts[2:moves_idx])
                    self.board.set_fen(fen_str)
                    if "moves" in parts:
                        for m_str in parts[moves_idx + 1:]:
                            self.board.push_uci(m_str)

                # Forward position to Lc0
                self.send_to_lc0(line)

            elif line.startswith("go"):
                bestmove = self.search_bestmove(line)
                if bestmove:
                    print(f"bestmove {bestmove}", flush=True)
                else:
                    legal = list(self.board.legal_moves)
                    if legal:
                        print(f"bestmove {legal[0].uci()}", flush=True)
                    else:
                        print("bestmove 0000", flush=True)

            elif line == "quit":
                if self.lc0_proc:
                    try:
                        self.send_to_lc0("quit")
                        self.lc0_proc.terminate()
                    except Exception:
                        pass
                break

if __name__ == "__main__":
    engine = HumanLc0Engine()
    engine.run()
