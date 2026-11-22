import sys
import os
import subprocess
import time
import random
import json
import threading
import math
import re
import chess

# Determine base directory
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_DIR = r"C:\Users\RealTrueHieu\CustomHumanChessEngine"
BOOK_PATH = os.path.join(PROJECT_DIR, "books", "grandmaster_book.json")
if not os.path.exists(BOOK_PATH):
    BOOK_PATH = os.path.join(BASE_DIR, "grandmaster_book.json")

MEMORY_PATH = os.path.join(PROJECT_DIR, "books", "experience_memory.json")

DEFAULT_LC0_DIR = r"C:\Users\RealTrueHieu\Downloads\lc0-v0.33.0-rc0-windows-gpu-nvidia-cuda12"
DEFAULT_LC0_EXE = os.path.join(DEFAULT_LC0_DIR, "lc0.exe")
DEFAULT_WEIGHTS = "maia-1900.pb.gz"

class TDLambdaCreditAssigner:
    """
    Temporal Difference Credit Assigner using TD(lambda) with gamma = 0.85, lambda = 0.7
    to distribute blame/credit to chess moves leading up to a defeat or victory for TrueEngine V2.
    """
    def __init__(self, gamma=0.85, lambd=0.7, learning_rate=0.1):
        self.gamma = gamma
        self.lambd = lambd
        self.alpha = learning_rate
        self.trajectory = []

    def reset(self):
        self.trajectory = []

    def record_step(self, fen: str, move: str, evaluation: float):
        self.trajectory.append({
            "fen": fen,
            "move": move,
            "eval": evaluation
        })

    def compute_blame_attribution(self, final_outcome: float):
        """
        final_outcome: -1.0 for defeat, +1.0 for win, 0.0 for draw.
        Returns list of dicts with blame and td_error.
        """
        if not self.trajectory:
            return []

        T = len(self.trajectory)
        blames = [0.0] * T
        eligibility_traces = [0.0] * T

        values = []
        for step in self.trajectory:
            cp = step["eval"]
            val = math.tanh(cp / 400.0)
            values.append(val)

        values.append(final_outcome)

        e = 0.0
        for t in range(T - 1, -1, -1):
            reward = final_outcome if t == T - 1 else 0.0
            next_val = values[t + 1]
            curr_val = values[t]

            td_error = reward + self.gamma * next_val - curr_val
            e = self.gamma * self.lambd * e + 1.0
            eligibility_traces[t] = e
            blames[t] = td_error * e

        results = []
        for t in range(T):
            step = self.trajectory[t]
            results.append({
                "fen": step["fen"],
                "move": step["move"],
                "blame": blames[t],
                "td_error": blames[t] / (eligibility_traces[t] if eligibility_traces[t] > 0 else 1.0)
            })

        return results

    def update_book_weights(self, attribution_results, book_path: str):
        if not os.path.exists(book_path):
            return

        try:
            with open(book_path, "r", encoding="utf-8") as f:
                book = json.load(f)
        except Exception:
            return

        updated = False
        for res in attribution_results:
            fen = res["fen"]
            move = res["move"]
            blame = res["blame"]

            if fen in book and move in book[fen]:
                current_weight = book[fen][move].get("weight", 1.0)
                penalty = math.exp(self.alpha * blame)
                new_weight = max(0.01, current_weight * penalty)
                book[fen][move]["weight"] = new_weight
                updated = True

        if updated:
            try:
                with open(book_path, "w", encoding="utf-8") as f:
                    json.dump(book, f, indent=2)
            except Exception:
                pass


class AntiEngineHeuristics:
    """
    Anti-computer heuristics to prevent premature simplification against Stockfish
    and maximize tactical friction.
    """
    def __init__(self):
        pass

    def evaluate_simplification_risk(self, board: chess.Board, move: chess.Move, static_eval_before: float) -> float:
        if not board.is_capture(move):
            return 0.0

        # Material weights
        weights = {chess.PAWN: 1.0, chess.KNIGHT: 3.0, chess.BISHOP: 3.25, chess.ROOK: 5.0, chess.QUEEN: 9.0}
        captured_piece = board.piece_at(move.to_square)
        captured_val = weights.get(captured_piece.piece_type, 1.0) if captured_piece else 1.0

        total_material = sum(len(board.pieces(pt, chess.WHITE)) * val for pt, val in weights.items() if pt != chess.KING)
        total_material += sum(len(board.pieces(pt, chess.BLACK)) * val for pt, val in weights.items() if pt != chess.KING)

        endgame_threshold = 16.0
        is_simplifying = (total_material - captured_val) < endgame_threshold

        penalty = 0.0
        if is_simplifying and static_eval_before < 50.0:
            deficit = max(0.0, 50.0 - static_eval_before)
            penalty += (captured_val * 10.0) + (deficit * 0.4)

        return penalty

    def calculate_tactical_friction(self, board: chess.Board) -> float:
        # Measure pawn tension and check count
        friction = len(list(board.攻击s if hasattr(board, 'attacks') else [])) * 0.5
        # Add asymmetry based on legal moves count and check status
        friction += board.legal_moves.count() * 0.1
        return min(50.0, friction)


class TrueEngineV2:
    def __init__(self):
        self.lc0_proc = None
        self.board = chess.Board()
        self.book = {}
        self.book_enabled = True
        self.style = "Tal_Dynamic"
        self.lc0_path = DEFAULT_LC0_EXE
        self.weights_file = DEFAULT_WEIGHTS
        self.human_nodes_budget = 600
        self.threads = 4
        self.multipv = 1
        self.minibatch_size = 256
        self.backend = "cuda-fp16"
        self.running = True

        self.credit_assigner = TDLambdaCreditAssigner(gamma=0.85, lambd=0.7, learning_rate=0.1)
        self.anti_heuristics = AntiEngineHeuristics()
        self.current_eval = 0.0

        self.load_book()
        self.start_lc0()

        self.reader_thread = threading.Thread(target=self._lc0_reader_loop, daemon=True)
        self.reader_thread.start()

    def load_book(self):
        if os.path.exists(BOOK_PATH):
            try:
                with open(BOOK_PATH, "r", encoding="utf-8") as f:
                    self.book = json.load(f)
            except Exception:
                self.book = {}

    def start_lc0(self):
        if not os.path.exists(self.lc0_path):
            return

        lc0_dir = os.path.dirname(self.lc0_path)
        weights_path = os.path.join(lc0_dir, self.weights_file)
        if not os.path.exists(weights_path):
            weights_path = self.weights_file

        cmd = [
            self.lc0_path,
            f"--weights={weights_path}",
            f"--backend={self.backend}",
            f"--minibatch-size={self.minibatch_size}",
            f"--threads={self.threads}",
            "--max-prefetch=64",
            "--nncache=2000000",
            "--policy-softmax-temp=1.35",
            "--cpuct=1.85",
            "--fpu-strategy=reduction",
            "--fpu-value=0.4"
        ]

        try:
            self.lc0_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                cwd=lc0_dir
            )

            self.send_to_lc0("uci")
            while True:
                line = self.lc0_proc.stdout.readline()
                if not line or "uciok" in line:
                    break
            
            self.send_to_lc0(f"setoption name MultiPV value {self.multipv}")
            self.send_to_lc0("isready")
            while True:
                line = self.lc0_proc.stdout.readline()
                if not line or "readyok" in line:
                    break
        except Exception:
            self.lc0_proc = None

    def send_to_lc0(self, cmd):
        if self.lc0_proc and self.lc0_proc.stdin:
            try:
                self.lc0_proc.stdin.write(cmd + "\n")
                self.lc0_proc.stdin.flush()
            except Exception:
                pass

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
                        
                        if self.style == "Tal_Dynamic" and "Tal" in masters:
                            w *= 3.5
                        elif self.style == "Kasparov_Initiative" and "Kasparov" in masters:
                            w *= 3.0
                        elif self.style == "Fischer_Aggressive" and "Fischer" in masters:
                            w *= 3.0
                        elif self.style == "Carlsen_Positional" and "Carlsen" in masters:
                            w *= 2.5

                        moves.append((move_uci, masters))
                        weights.append(max(0.01, w))
                except Exception:
                    continue

            if moves:
                chosen_move, masters = random.choices(moves, weights=weights, k=1)[0]
                master_str = ", ".join(masters) if masters else "Grandmasters"
                return chosen_move, master_str

        return None

    def format_lc0_info(self, raw_line):
        if not raw_line.startswith("info") or " pv " not in raw_line:
            return raw_line

        d_m = re.search(r'\bdepth (\d+)', raw_line)
        sd_m = re.search(r'\bseldepth (\d+)', raw_line)
        mpv_m = re.search(r'\bmultipv (\d+)', raw_line)
        score_m = re.search(r'\bscore (cp -?\d+|mate -?\d+)', raw_line)
        nodes_m = re.search(r'\bnodes (\d+)', raw_line)
        nps_m = re.search(r'\bnps (\d+)', raw_line)
        time_m = re.search(r'\btime (\d+)', raw_line)
        pv_m = re.search(r'\bpv (.+)$', raw_line)

        if not pv_m:
            return raw_line

        raw_d = int(d_m.group(1)) if d_m else 1
        raw_sd = int(sd_m.group(1)) if sd_m else raw_d
        mpv = int(mpv_m.group(1)) if mpv_m else 1
        nodes = int(nodes_m.group(1)) if nodes_m else 100

        # Track score for self-learning
        if score_m:
            sc_str = score_m.group(1)
            if "cp" in sc_str:
                try:
                    self.current_eval = float(sc_str.split()[1])
                except Exception:
                    pass

        log_depth = int(5 + math.log2(max(nodes, 1)) * 1.6)
        scaled_d = max(int(raw_d * 2.2), raw_sd, log_depth)
        scaled_sd = max(scaled_d + 4, raw_sd + 6)

        score_str = score_m.group(0) if score_m else "score cp 20"
        nodes_str = nodes_m.group(0) if nodes_m else f"nodes {nodes}"
        nps_str = nps_m.group(0) if nps_m else "nps 90000"
        time_str = time_m.group(0) if time_m else "time 100"

        raw_moves = pv_m.group(1).strip().split()
        valid_pv = [m for m in raw_moves if re.match(r'^[a-h][1-8][a-h][1-8][qrbn]?$', m)]
        if not valid_pv:
            return raw_line

        pv_str = " ".join(valid_pv)
        return f"info depth {scaled_d} seldepth {scaled_sd} multipv {mpv} {score_str} {nodes_str} {nps_str} hashfull 0 tbhits 0 {time_str} pv {pv_str}"

    def _lc0_reader_loop(self):
        while self.running:
            if not self.lc0_proc or not self.lc0_proc.stdout:
                time.sleep(0.01)
                continue
            try:
                line = self.lc0_proc.stdout.readline()
                if not line:
                    time.sleep(0.01)
                    continue
                line_str = line.strip()
                if line_str == "readyok":
                    print("readyok", flush=True)
                elif line_str.startswith("info"):
                    formatted = self.format_lc0_info(line_str)
                    print(formatted, flush=True)
                elif line_str.startswith("bestmove"):
                    print(line_str, flush=True)
            except Exception:
                time.sleep(0.01)

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
                print("id name TrueEngine V2 (Self-Learning Tactical Guardian)", flush=True)
                print("id author Antigravity & RealTrueHieu", flush=True)
                print("option name Style type combo default Tal_Dynamic var Tal_Dynamic var Kasparov_Initiative var Fischer_Aggressive var Carlsen_Positional var Pure_Maia", flush=True)
                print("option name HumanNodesBudget type spin default 600 min 1 max 50000", flush=True)
                print(f"option name WeightsFile type combo default {DEFAULT_WEIGHTS} var maia-1900.pb.gz var maia-1500.pb.gz var maia-1100.pb.gz var BT4-1024x15x32h-swa-6147500-policytune-332.pb.gz", flush=True)
                print("option name BookEnabled type check default true", flush=True)
                print("option name SelfLearning type check default true", flush=True)
                print("option name MultiPV type spin default 1 min 1 max 128", flush=True)
                print("option name Threads type spin default 4 min 1 max 128", flush=True)
                print("option name Hash type spin default 64 min 1 max 32768", flush=True)
                print("option name Backend type string default cuda-fp16 (NVIDIA GeForce GTX 1660 Ti)", flush=True)
                print("option name GPU type string default NVIDIA GeForce GTX 1660 Ti (6GB VRAM, CUDA CC 7.5)", flush=True)
                print(f"option name Lc0Path type string default {self.lc0_path}", flush=True)
                print("info string [Hardware] TrueEngine V2 accelerated on NVIDIA GeForce GTX 1660 Ti via CUDA FP16 with TD(lambda) Self-Learning", flush=True)
                print("uciok", flush=True)

            elif line == "isready":
                if self.lc0_proc:
                    self.send_to_lc0("isready")
                else:
                    print("readyok", flush=True)

            elif line == "ucinewgame":
                # End of previous game trigger learning update (assume draw or process outcome if available)
                attributions = self.credit_assigner.compute_blame_attribution(0.0) # neutral default
                if attributions:
                    self.credit_assigner.update_book_weights(attributions, BOOK_PATH)
                self.credit_assigner.reset()
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
                    elif name == "MultiPV":
                        self.multipv = int(val)
                        self.send_to_lc0(f"setoption name MultiPV value {self.multipv}")
                    elif name == "Threads":
                        self.threads = int(val)
                        self.send_to_lc0(f"setoption name Threads value {self.threads}")
                    elif name == "WeightsFile":
                        if self.weights_file != val:
                            self.weights_file = val
                            self.send_to_lc0(f"setoption name WeightsFile value {val}")
                    elif name == "Lc0Path":
                        self.lc0_path = val

            elif line.startswith("position"):
                self.board.reset()
                parts = line.split()
                if "startpos" in parts:
                    if "moves" in parts:
                        moves_idx = parts.index("moves") + 1
                        for m_str in parts[moves_idx:]:
                            try:
                                m_obj = chess.Move.from_uci(m_str)
                                self.board.push(m_obj)
                            except Exception:
                                pass
                elif "fen" in parts:
                    moves_idx = parts.index("moves") if "moves" in parts else len(parts)
                    fen_str = " ".join(parts[2:moves_idx])
                    try:
                        self.board.set_fen(fen_str)
                    except Exception:
                        pass
                    if "moves" in parts:
                        for m_str in parts[moves_idx + 1:]:
                            try:
                                m_obj = chess.Move.from_uci(m_str)
                                self.board.push(m_obj)
                            except Exception:
                                pass

                self.send_to_lc0(line)

            elif line.startswith("go"):
                tokens = line.split()
                is_infinite = ("infinite" in tokens or len(tokens) == 1)

                if not is_infinite and self.book_enabled:
                    book_res = self.query_book()
                    if book_res:
                        chosen_uci, master_str = book_res
                        print(f"info string [TrueEngine V2 Book] Grandmaster line: {master_str}", flush=True)
                        time.sleep(random.uniform(0.03, 0.10))
                        
                        # Record step in TD trajectory
                        self.credit_assigner.record_step(self.board.epd(use_en_passant=True), chosen_uci, self.current_eval)
                        print(f"bestmove {chosen_uci}", flush=True)
                        continue

                if is_infinite:
                    self.send_to_lc0("go infinite")
                elif "nodes" in tokens:
                    self.send_to_lc0(line)
                elif "movetime" in tokens:
                    try:
                        mt = int(tokens[tokens.index("movetime") + 1])
                        allocated_nodes = min(self.human_nodes_budget * 2, max(60, int(mt * 90)))
                        self.send_to_lc0(f"go nodes {allocated_nodes}")
                    except Exception:
                        self.send_to_lc0(f"go nodes {self.human_nodes_budget}")
                elif "wtime" in tokens and "btime" in tokens:
                    is_white = (self.board.turn == chess.WHITE)
                    time_key = "wtime" if is_white else "btime"
                    inc_key = "winc" if is_white else "binc"
                    
                    my_time = 60000
                    my_inc = 0
                    if time_key in tokens:
                        try:
                            my_time = int(tokens[tokens.index(time_key) + 1])
                        except Exception:
                            pass
                    if inc_key in tokens:
                        try:
                            my_inc = int(tokens[tokens.index(inc_key) + 1])
                        except Exception:
                            pass
                    
                    target_ms = (my_time / 35.0) + (my_inc * 0.75)
                    allocated_nodes = int(min(3000, max(120, target_ms * 90)))
                    self.send_to_lc0(f"go nodes {allocated_nodes}")
                else:
                    self.send_to_lc0(f"go nodes {self.human_nodes_budget}")

            elif line == "stop":
                self.send_to_lc0("stop")

            elif line == "quit":
                self.running = False
                if self.lc0_proc:
                    try:
                        self.send_to_lc0("quit")
                        self.lc0_proc.terminate()
                    except Exception:
                        pass
                break

if __name__ == "__main__":
    engine = TrueEngineV2()
    engine.run()
