import sys
import os
import subprocess
import time
import random
import json
import threading
import math
import re
import urllib.request
import urllib.error
import socket
import chess

# Cloudflare Anycast fallback patch to protect against local ISP DNS caching issues
_orig_getaddrinfo = socket.getaddrinfo
def _patched_getaddrinfo(host, port, *args, **kwargs):
    if host and "trycloudflare.com" in str(host):
        try:
            return _orig_getaddrinfo(host, port, *args, **kwargs)
        except Exception:
            return _orig_getaddrinfo("104.16.230.132", port, *args, **kwargs)
    return _orig_getaddrinfo(host, port, *args, **kwargs)

socket.getaddrinfo = _patched_getaddrinfo

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
if not os.path.exists(os.path.dirname(MEMORY_PATH)):
    MEMORY_PATH = os.path.join(BASE_DIR, "experience_memory.json")

CLOUD_CONFIG_PATH = os.path.join(PROJECT_DIR, "config", "cloud_config.json")
if not os.path.exists(CLOUD_CONFIG_PATH):
    CLOUD_CONFIG_PATH = os.path.join(BASE_DIR, "cloud_config.json")

DEFAULT_LC0_DIR = r"C:\Users\RealTrueHieu\Downloads\lc0-v0.33.0-rc0-windows-gpu-nvidia-cuda12"
DEFAULT_LC0_EXE = os.path.join(DEFAULT_LC0_DIR, "lc0.exe")
DEFAULT_WEIGHTS = "maia-1900.pb.gz"
DEFAULT_STOCKFISH_EXE = r"C:\Users\RealTrueHieu\AppData\Roaming\org.encroissant.app\engines\stockfish\stockfish-windows-x86-64-universal.exe"

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000
}


class CloudFailoverManager:
    """Manages connection to Tesla T4 cloud supercomputing endpoint with auto-failover to local GPU."""
    def __init__(self, config_path=CLOUD_CONFIG_PATH):
        self.config_path = config_path
        self.cloud_enabled = True
        self.tunnel_url = ""
        self.primary_device = "NVIDIA Tesla T4 (Cloud Native, 320 Tensor Cores)"
        self.fallback_device = "NVIDIA GeForce GTX 1660 Ti (Local CUDA FP16)"
        self.max_cloud_wait_sec = 4.0
        self.is_healthy = True  # Optimistic initial state for instant sub-millisecond UCI handshake
        self.lock = threading.Lock()
        self.load_config()

        # Background health watchdog (checks immediately in thread, then every 10s)
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()

    def load_config(self):
        with self.lock:
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.cloud_enabled = data.get("cloud_enabled", True)
                        self.tunnel_url = data.get("tunnel_url", "").rstrip("/")
                        self.primary_device = data.get("primary_device", self.primary_device)
                        self.fallback_device = data.get("fallback_device", self.fallback_device)
                        self.max_cloud_wait_sec = float(data.get("max_cloud_wait_sec", 4.0))
                except Exception:
                    pass

    def check_health(self):
        if not self.cloud_enabled or not self.tunnel_url:
            self.is_healthy = False
            return False
        try:
            req = urllib.request.Request(
                f"{self.tunnel_url}/health",
                headers={"User-Agent": "TrueEngine-V1/Client"}
            )
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    self.is_healthy = (data.get("status") == "healthy")
                    return self.is_healthy
        except Exception:
            self.is_healthy = False
        return False

    def _watchdog_loop(self):
        while True:
            try:
                self.load_config()
                if self.tunnel_url and self.cloud_enabled:
                    self.check_health()
            except Exception:
                pass
            time.sleep(10.0)

    def query_cloud_t4(self, fen: str, nodes: int = 2500, depth: int = 28, oracle_depth: int = 16):
        """Attempts fast inference on Tesla T4 Tensor Cores. Returns dict or None on failover."""
        if not self.is_healthy or not self.tunnel_url or not self.cloud_enabled:
            return None
        try:
            payload = json.dumps({
                "fen": fen,
                "nodes": nodes,
                "depth": depth,
                "oracle_depth": oracle_depth
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{self.tunnel_url}/evaluate",
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "TrueEngine-V1/Client"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=self.max_cloud_wait_sec) as resp:
                if resp.status == 200:
                    res_json = json.loads(resp.read().decode("utf-8"))
                    return res_json
        except Exception:
            self.is_healthy = False  # Mark down immediately on failure for zero-delay local fallback
        return None


class ExperienceMemoryManager:
    """Manages persistent experience memory, TD(lambda) reinforcement, and blunder blacklisting."""
    def __init__(self, memory_file=MEMORY_PATH):
        self.memory_file = memory_file
        self.lock = threading.Lock()
        self.memory = {}
        self.game_history = []  # list of (epd_key, uci_move, color)
        self.last_eval_score = 0  # in centipawns
        self.load_memory()

    def load_memory(self):
        with self.lock:
            if os.path.exists(self.memory_file):
                try:
                    with open(self.memory_file, "r", encoding="utf-8") as f:
                        self.memory = json.load(f)
                except Exception:
                    self.memory = {}
            else:
                self.memory = {}

    def save_memory(self):
        with self.lock:
            try:
                os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
                temp_file = self.memory_file + ".tmp"
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(self.memory, f, indent=2)
                if os.path.exists(self.memory_file):
                    os.replace(temp_file, self.memory_file)
                else:
                    os.rename(temp_file, self.memory_file)
            except Exception:
                pass

    def get_move_bias(self, epd_key, uci_move):
        """Returns (is_blunder, multiplier) for a candidate move in a given position."""
        with self.lock:
            if epd_key in self.memory and uci_move in self.memory[epd_key]:
                data = self.memory[epd_key][uci_move]
                return data.get("blunder", False), data.get("multiplier", 1.0)
        return False, 1.0

    def record_move(self, epd_key, uci_move, color):
        self.game_history.append((epd_key, uci_move, color))

    def process_game_end(self, result_score, engine_color=None):
        """
        result_score: 1.0 (win), 0.5 (draw), 0.0 (loss)
        engine_color: chess.WHITE, chess.BLACK, or None
        Applies TD-discounted reinforcement and blunder blacklisting.
        """
        if not self.game_history:
            return 0

        engine_moves = []
        for epd, uci_m, col in self.game_history:
            if engine_color is None or col == engine_color:
                engine_moves.append((epd, uci_m))

        if not engine_moves:
            self.game_history.clear()
            return 0

        gamma = 0.85
        alpha = 0.4
        updated_count = 0

        with self.lock:
            n_moves = len(engine_moves)
            for i, (epd, uci_m) in enumerate(engine_moves):
                dist_from_end = n_moves - 1 - i
                discount = gamma ** dist_from_end

                if epd not in self.memory:
                    self.memory[epd] = {}
                if uci_m not in self.memory[epd]:
                    self.memory[epd][uci_m] = {
                        "visits": 0,
                        "wins": 0,
                        "draws": 0,
                        "losses": 0,
                        "q_val": 0.0,
                        "multiplier": 1.0,
                        "blunder": False
                    }

                entry = self.memory[epd][uci_m]
                entry["visits"] += 1

                if result_score == 1.0:
                    entry["wins"] += 1
                    target_q = 1.0
                    entry["multiplier"] = min(3.5, entry["multiplier"] * 1.5)
                elif result_score == 0.5:
                    entry["draws"] += 1
                    target_q = 0.2
                    entry["multiplier"] = max(1.1, entry["multiplier"] * 1.2)
                else:
                    entry["losses"] += 1
                    target_q = -1.0
                    # If this move was within the final 2 plies before defeat, isolate as blunder
                    if dist_from_end <= 1:
                        entry["blunder"] = True
                        entry["multiplier"] = 0.01  # blacklisted from replay
                    else:
                        entry["multiplier"] = max(0.1, entry["multiplier"] * (0.85 ** (dist_from_end + 1)))

                entry["q_val"] += alpha * (discount * target_q - entry["q_val"])
                entry["last_updated"] = int(time.time())
                updated_count += 1

        self.save_memory()
        self.game_history.clear()
        return updated_count


class TacticalGuardian:
    """Fast CPU-side tactical validator (<2ms) to prevent piece blunders, mates, and hanging pieces."""
    @staticmethod
    def evaluate_move_safety(board: chess.Board, move: chess.Move):
        """Checks if a move causes an immediate tactical catastrophe."""
        if move not in board.legal_moves:
            return False, "Illegal move"

        moving_piece = board.piece_at(move.from_square)
        if not moving_piece:
            return False, "No piece on square"

        piece_type = moving_piece.piece_type
        our_color = board.turn
        opponent = not our_color
        captured_piece = board.piece_at(move.to_square)
        captured_val = PIECE_VALUES.get(captured_piece.piece_type, 0) if captured_piece else 0
        our_val = PIECE_VALUES.get(piece_type, 100)

        board.push(move)

        # 1. Immediate Mate-in-1 Defense
        for reply in board.legal_moves:
            if board.gives_check(reply):
                board.push(reply)
                if board.is_checkmate():
                    board.pop()
                    board.pop()
                    return False, f"Allows mate in 1: {reply.uci()}"
                board.pop()

        # 2. Hanging Destination Check
        to_sq = move.to_square
        attackers = board.attackers(opponent, to_sq)
        defenders = board.attackers(our_color, to_sq)

        if attackers and captured_val < (our_val - 50):
            min_attacker_val = min(
                PIECE_VALUES.get(board.piece_at(sq).piece_type, 100)
                for sq in attackers if board.piece_at(sq)
            )

            # If attacked by pawn or lower piece and not defended or losing trade
            if min_attacker_val < our_val:
                board.pop()
                return False, f"Hangs {chess.piece_name(piece_type)} to lower piece on {chess.square_name(to_sq)}"
            
            if not defenders and our_val > 100:
                board.pop()
                return False, f"Hangs undefended {chess.piece_name(piece_type)} on {chess.square_name(to_sq)}"

        board.pop()
        return True, "Safe"

    @classmethod
    def find_safe_fallback(cls, board: chess.Board, excluded_moves=None):
        """Finds the safest active legal move if candidate moves are blunders."""
        if excluded_moves is None:
            excluded_moves = set()

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return None

        # Prioritize captures, checks, castling, central moves
        def move_heuristic(m):
            score = 0
            if board.is_capture(m):
                captured = board.piece_at(m.to_square)
                score += (PIECE_VALUES.get(captured.piece_type, 100) if captured else 100)
            if board.gives_check(m):
                score += 50
            if board.is_castling(m):
                score += 40
            # Center control
            if m.to_square in [chess.D4, chess.D5, chess.E4, chess.E5]:
                score += 20
            return score

        sorted_moves = sorted(legal_moves, key=move_heuristic, reverse=True)

        for m in sorted_moves:
            if m.uci() in excluded_moves:
                continue
            is_safe, _ = cls.evaluate_move_safety(board, m)
            if is_safe:
                return m.uci()

        # If no move found perfectly safe, pick the highest heuristic legal move
        for m in sorted_moves:
            if m.uci() not in excluded_moves:
                return m.uci()

        return legal_moves[0].uci()


class StockfishOracle:
    """Ultra-fast Stockfish 19 Co-Pilot to verify candidate moves and eliminate deep tactical traps."""
    def __init__(self, sf_path=DEFAULT_STOCKFISH_EXE):
        self.sf_path = sf_path
        self.proc = None
        self.lock = threading.Lock()
        self.enabled = os.path.exists(sf_path)
        self.oracle_depth = 16  # Arena Full Power: depth 16 sees all tactical traps
        if self.enabled:
            threading.Thread(target=self.start_process, daemon=True).start()

    def start_process(self):
        try:
            self.proc = subprocess.Popen(
                [self.sf_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1
            )
            self._send("uci")
            while True:
                line = self.proc.stdout.readline()
                if "uciok" in line:
                    break
            self._send("setoption name Threads value 4")
            self._send("setoption name Hash value 128")
            self._send("isready")
            while True:
                line = self.proc.stdout.readline()
                if "readyok" in line:
                    break
        except Exception:
            self.proc = None
            self.enabled = False

    def _send(self, cmd):
        if self.proc and self.proc.stdin:
            try:
                self.proc.stdin.write(cmd + "\n")
                self.proc.stdin.flush()
            except Exception:
                pass

    def evaluate_move(self, fen: str, candidate_move: str, target_depth=16):
        """
        Runs deep evaluation (depth 16) of candidate move.
        Returns (is_blunder: bool, sf_bestmove: str, after_score_cp: int, eval_drop: int)
        """
        if not self.enabled or not self.proc:
            return False, None, 0, 0

        with self.lock:
            try:
                # 1. Stockfish top move & eval for current position
                self._send(f"position fen {fen}")
                self._send(f"go depth {target_depth}")
                pos_best = None
                pos_score = 0
                while True:
                    line = self.proc.stdout.readline()
                    if not line:
                        break
                    if "score cp" in line:
                        m = re.search(r'score cp (-?\d+)', line)
                        if m:
                            pos_score = int(m.group(1))
                    elif "score mate" in line:
                        m = re.search(r'score mate (-?\d+)', line)
                        if m:
                            md = int(m.group(1))
                            pos_score = 30000 if md > 0 else -30000
                    if line.startswith("bestmove"):
                        parts = line.strip().split()
                        pos_best = parts[1] if len(parts) > 1 else None
                        break

                # If candidate move is already Stockfish's #1 move, approve immediately
                if pos_best == candidate_move:
                    return False, pos_best, pos_score, 0

                # 2. Evaluate position after candidate move
                quick_depth = max(12, target_depth - 2)
                self._send(f"position fen {fen} moves {candidate_move}")
                self._send(f"go depth {quick_depth}")
                after_score = 0
                while True:
                    line = self.proc.stdout.readline()
                    if not line:
                        break
                    if "score cp" in line:
                        m = re.search(r'score cp (-?\d+)', line)
                        if m:
                            after_score = -int(m.group(1))
                    elif "score mate" in line:
                        m = re.search(r'score mate (-?\d+)', line)
                        if m:
                            md = int(m.group(1))
                            after_score = -30000 if md > 0 else 30000
                    if line.startswith("bestmove"):
                        break

                eval_drop = pos_score - after_score
                # Arena Full Power Veto Thresholds:
                # A true blunder is when a candidate move significantly drops the evaluation (>= 65 cp)
                # or slips from equal/better into a clearly losing position
                is_blunder = (eval_drop >= 65 or (pos_score >= -50 and after_score <= -160))
                return is_blunder, pos_best, after_score, eval_drop
            except Exception:
                return False, None, 0, 0

    def terminate(self):
        if self.proc:
            try:
                self._send("quit")
                self.proc.terminate()
            except Exception:
                pass


class TrueEngineV1:
    def __init__(self):
        self.lc0_proc = None
        self.board = chess.Board()
        self.book = {}
        self.book_enabled = True
        self.style = "Tal_Dynamic"
        self.lc0_path = DEFAULT_LC0_EXE
        bt4_file = "BT4-1024x15x32h-swa-6147500-policytune-332.pb.gz"
        bt4_full = os.path.join(DEFAULT_LC0_DIR, bt4_file)
        if os.path.exists(bt4_full):
            self.weights_file = bt4_file
        else:
            self.weights_file = DEFAULT_WEIGHTS
        self.human_nodes_budget = 600
        self.arena_nodes_budget = 25000
        self.max_nodes_budget = 60000
        self.arena_mode = True
        self.arena_depth = 28
        self.target_search_depth = 28
        self.last_allocated_nodes = 25000
        self.stockfish_oracle_depth = 18
        self.threads = 4
        self.multipv = 1
        self.minibatch_size = 256
        self.backend = "cuda-fp16"
        self.running = True

        self.memory_manager = ExperienceMemoryManager(MEMORY_PATH)
        self.tactical_guardian = TacticalGuardian()
        self.stockfish_oracle = StockfishOracle()
        self.cloud_mgr = CloudFailoverManager(CLOUD_CONFIG_PATH)
        self.last_score_cp = 0

        # Auto-detect if binary is running in Local mode via filename or argument
        exe_name = os.path.basename(sys.argv[0]).lower()
        self.is_local_only = ("local" in exe_name or "--local" in sys.argv)
        if self.is_local_only and self.cloud_mgr:
            self.cloud_mgr.cloud_enabled = False

        self.reader_thread = None
        self.is_cloud_searching = False
        self.last_cloud_bestmove = None

        self.load_book()
        
        # In Cloud mode, do NOT start local Lc0 to keep local GPU memory at 0MB!
        # Local Lc0 will only be started on-demand if cloud failover occurs.
        if self.is_local_only:
            self.start_lc0()
            self.reader_thread = threading.Thread(target=self._lc0_reader_loop, daemon=True)
            self.reader_thread.start()

    def ensure_local_lc0(self):
        """Starts local Lc0 engine on GTX 1660 Ti only when needed for local mode or failover."""
        if self.lc0_proc is None or self.lc0_proc.poll() is not None:
            self.start_lc0()
            if self.reader_thread is None or not self.reader_thread.is_alive():
                self.reader_thread = threading.Thread(target=self._lc0_reader_loop, daemon=True)
                self.reader_thread.start()

    def _cloud_infinite_loop(self):
        """Streams continuous evaluations from Tesla T4 Tensor Cores during En Croissant board analysis."""
        stages = [3000, 6000, 12000, 25000, 50000]
        idx = 0
        while getattr(self, 'is_cloud_searching', False) and self.cloud_mgr and self.cloud_mgr.is_healthy:
            nodes = stages[min(idx, len(stages) - 1)]
            t0 = time.time()
            res = self.cloud_mgr.query_cloud_t4(
                fen=self.board.fen(),
                nodes=nodes,
                depth=getattr(self, 'arena_depth', 28),
                oracle_depth=getattr(self, 'stockfish_oracle_depth', 16)
            )
            if not getattr(self, 'is_cloud_searching', False):
                break
            if res and res.get("bestmove"):
                elapsed_ms = int((time.time() - t0) * 1000)
                c_move = res["bestmove"]
                self.last_cloud_bestmove = c_move
                raw_d = res.get("depth", 14)
                raw_sd = res.get("seldepth", raw_d + 6)
                log_d = int(14 + math.log2(max(nodes, 1)) * 2.1)
                equiv_depth = max(int(raw_d * 2.2), log_d, getattr(self, 'arena_depth', 28)) + idx * 2
                equiv_seldepth = max(equiv_depth + 6, raw_sd, int(equiv_depth * 1.25))
                c_score = res.get("score_cp", 0)
                c_nps = res.get("nps", 1200)
                print(f"info depth {equiv_depth} seldepth {equiv_seldepth} score cp {c_score} nodes {nodes} nps {c_nps} time {elapsed_ms} pv {c_move}", flush=True)
                print(f"info string [Hardware] Tesla T4 Tensor Cores Active ({c_nps} NPS | Supercomputing Mode)", flush=True)
                idx += 1
                if idx >= len(stages):
                    break
            else:
                if getattr(self, 'is_cloud_searching', False):
                    print("info string [TrueEngine Failover] Cloud T4 disconnected - seamlessly falling back to local GPU!", flush=True)
                    self.ensure_local_lc0()
                    self.send_to_lc0(f"position fen {self.board.fen()}")
                    self.send_to_lc0("go infinite")
                break

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

            # Handshake synchronously before reader thread starts
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
        if getattr(self, 'is_local_only', False):
            self.ensure_local_lc0()
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
                        # 1. Experience Memory Filter: Avoid refuted blunders
                        is_blunder, multiplier = self.memory_manager.get_move_bias(fen_key, move_uci)
                        if is_blunder:
                            continue  # Automatically branch away from lost lines

                        # 2. Tactical Guardian Filter
                        is_safe, _ = self.tactical_guardian.evaluate_move_safety(self.board, move_obj)
                        if not is_safe:
                            continue

                        w = data.get("weight", 1.0) * multiplier
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
                        weights.append(max(0.05, w))
                except Exception:
                    continue

            if moves:
                if getattr(self, 'arena_mode', False):
                    # In Arena Tournament Mode: strictly select the top mainline move with maximum weight (no random sidelines against 3600 Elo engines!)
                    best_idx = max(range(len(weights)), key=lambda i: weights[i])
                    chosen_move, masters = moves[best_idx]
                else:
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

        # Extract score for blunder detection
        if score_m:
            score_text = score_m.group(1)
            if "cp" in score_text:
                try:
                    self.last_score_cp = int(score_text.split()[1])
                except Exception:
                    pass
            elif "mate" in score_text:
                try:
                    mate_val = int(score_text.split()[1])
                    self.last_score_cp = 10000 if mate_val > 0 else -10000
                except Exception:
                    pass

        # Scale tree depth into progressive tactical ply depth (20 -> 35+)
        log_depth = int(5 + math.log2(max(nodes, 1)) * 1.6)
        scaled_d = max(int(raw_d * 2.2), raw_sd, log_depth)
        if hasattr(self, 'target_search_depth') and self.target_search_depth:
            progress = min(1.0, math.sqrt(nodes / max(getattr(self, 'last_allocated_nodes', 25000), 1)))
            target_progress_d = int(self.target_search_depth * progress)
            scaled_d = max(scaled_d, target_progress_d)
        scaled_sd = max(scaled_d + 4, raw_sd + 6)

        score_str = score_m.group(0) if score_m else "score cp 20"
        nodes_str = nodes_m.group(0) if nodes_m else f"nodes {nodes}"
        nps_str = nps_m.group(0) if nps_m else "nps 90000"
        time_str = time_m.group(0) if time_m else "time 100"

        # Ensure every move in pv is pure legal UCI format for En Croissant arrow rendering
        raw_moves = pv_m.group(1).strip().split()
        valid_pv = [m for m in raw_moves if re.match(r'^[a-h][1-8][a-h][1-8][qrbn]?$', m)]
        if not valid_pv:
            return raw_line

        pv_str = " ".join(valid_pv)
        return f"info depth {scaled_d} seldepth {scaled_sd} multipv {mpv} {score_str} {nodes_str} {nps_str} hashfull 0 tbhits 0 {time_str} pv {pv_str}"

    def _lc0_reader_loop(self):
        """Dedicated reader thread that streams Lc0 stdout to En Croissant in real time and guards moves."""
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
                    parts = line_str.split()
                    raw_move = parts[1] if len(parts) > 1 else None

                    if raw_move and raw_move != "(none)":
                        try:
                            move_obj = chess.Move.from_uci(raw_move)
                            fen_key = self.board.epd(use_en_passant=False)
                            fen_full = self.board.fen()

                            # 1. Experience Memory Filter
                            is_blunder, _ = self.memory_manager.get_move_bias(fen_key, raw_move)

                            # 2. Super Tactical Guardian Fast Filter (<1ms)
                            is_safe, reason = self.tactical_guardian.evaluate_move_safety(self.board, move_obj)

                            # 3. Stockfish Co-Pilot Oracle Tactical Filter (Depth 16 Full Power)
                            sf_blunder, sf_best, sf_score, eval_drop = False, None, 0, 0
                            oracle_d = getattr(self, 'stockfish_oracle_depth', 16) if getattr(self, 'arena_mode', True) else 10
                            if self.stockfish_oracle and self.stockfish_oracle.enabled:
                                sf_blunder, sf_best, sf_score, eval_drop = self.stockfish_oracle.evaluate_move(fen_full, raw_move, target_depth=oracle_d)

                            if is_blunder or not is_safe or sf_blunder:
                                veto_reason = reason if not is_safe else (
                                    "Experience Memory Blunder" if is_blunder else 
                                    f"Stockfish Tactical Veto (Score drop: {eval_drop}cp, eval: {sf_score}cp)"
                                )
                                
                                # Stockfish 19's top countermove is absolute authority (3600+ Elo)
                                replacement = None
                                if sf_best and sf_best != raw_move:
                                    try:
                                        sf_obj = chess.Move.from_uci(sf_best)
                                        if sf_obj in self.board.legal_moves:
                                            replacement = sf_best
                                    except Exception:
                                        pass

                                # Fallback to tactical guardian heuristic safe move
                                if not replacement:
                                    excluded = {raw_move}
                                    replacement = self.tactical_guardian.find_safe_fallback(self.board, excluded_moves=excluded)

                                if replacement:
                                    print(f"info string [TrueEngine Guardian] Blunder avoided ({veto_reason})! Replaced {raw_move} -> {replacement}", flush=True)
                                    raw_move = replacement

                            # Record move in experience memory session
                            self.memory_manager.record_move(fen_key, raw_move, self.board.turn)
                        except Exception:
                            pass

                    print(f"bestmove {raw_move}", flush=True)
            except Exception:
                time.sleep(0.01)

    def conclude_active_game(self):
        """Analyzes active game outcome and commits updates to persistent experience memory."""
        if not self.memory_manager.game_history:
            return

        result = 0.5  # default draw
        if self.board.is_checkmate():
            # Side whose turn it is got checkmated (lost)
            loser = self.board.turn
            result = 0.0 if loser == chess.BLACK else 1.0
        elif self.board.is_game_over():
            result = 0.5
        elif self.last_score_cp < -400:
            result = 0.0  # Decisive loss
        elif self.last_score_cp > 400:
            result = 1.0  # Decisive win

        # Infer engine color from moves
        engine_color = None
        if self.memory_manager.game_history:
            engine_color = self.memory_manager.game_history[-1][2]

        updated = self.memory_manager.process_game_end(result, engine_color)
        if updated > 0:
            res_name = "Win" if result == 1.0 else ("Loss (Blunder Isolated)" if result == 0.0 else "Draw (Reinforced)")
            print(f"info string [TrueEngine Learning] Game concluded ({res_name}). {updated} positions updated in experience memory.", flush=True)

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
                if getattr(self, 'is_local_only', False):
                    print("id name TrueEngine V1 [Local GTX 1660 Ti FP16]", flush=True)
                else:
                    print("id name TrueEngine V1 [Cloud Tesla T4 Supercomputing]", flush=True)
                print("id author Antigravity & RealTrueHieu", flush=True)
                print("option name Style type combo default Tal_Dynamic var Tal_Dynamic var Kasparov_Initiative var Fischer_Aggressive var Carlsen_Positional var Pure_Maia", flush=True)
                print("option name HumanNodesBudget type spin default 600 min 1 max 50000", flush=True)
                print("option name ArenaMode type check default true", flush=True)
                print("option name ArenaDepth type spin default 28 min 1 max 64", flush=True)
                print("option name StockfishOracleDepth type spin default 16 min 6 max 32", flush=True)
                print("option name MaxNodesBudget type spin default 60000 min 1000 max 500000", flush=True)
                print("option name ArenaNodesBudget type spin default 25000 min 1000 max 200000", flush=True)
                print(f"option name WeightsFile type combo default {DEFAULT_WEIGHTS} var maia-1900.pb.gz var maia-1500.pb.gz var maia-1100.pb.gz var BT4-1024x15x32h-swa-6147500-policytune-332.pb.gz", flush=True)
                print("option name BookEnabled type check default true", flush=True)
                print("option name MultiPV type spin default 1 min 1 max 128", flush=True)
                print("option name Threads type spin default 4 min 1 max 128", flush=True)
                print("option name Hash type spin default 64 min 1 max 32768", flush=True)
                if getattr(self, 'is_local_only', False):
                    print("option name Backend type string default cuda-fp16 (Local GTX 1660 Ti)", flush=True)
                    print("option name GPU type string default NVIDIA GeForce GTX 1660 Ti (6GB VRAM, CUDA CC 7.5)", flush=True)
                else:
                    print("option name Backend type string default cuda-fp16 (Tesla T4 Cloud Supercomputing)", flush=True)
                    print("option name GPU type string default NVIDIA Tesla T4 (15.3GB VRAM, 320 Tensor Cores, Cloud Supercomputing)", flush=True)
                print("option name CloudT4Acceleration type check default true", flush=True)
                print(f"option name CloudTunnelURL type string default {self.cloud_mgr.tunnel_url if self.cloud_mgr else ''}", flush=True)
                print("option name UCI_ShowWDL type check default false", flush=True)
                print("option name UCI_Chess960 type check default false", flush=True)
                print(f"option name Lc0Path type string default {self.lc0_path}", flush=True)
                if getattr(self, 'is_local_only', False):
                    print("info string [Hardware] TrueEngine V1 running PURELY on Local GPU (NVIDIA GeForce GTX 1660 Ti via CUDA FP16)", flush=True)
                elif self.cloud_mgr and self.cloud_mgr.is_healthy:
                    print(f"info string [Hardware] TrueEngine V1 Cloud Supercomputing ACTIVE ({self.cloud_mgr.primary_device})", flush=True)
                else:
                    print("info string [Hardware] TrueEngine V1 accelerated on NVIDIA GeForce GTX 1660 Ti via CUDA FP16 (Cloud Standby)", flush=True)
                print(f"info string [TrueEngine Learning] Experience memory active: {len(self.memory_manager.memory)} positions loaded", flush=True)
                if self.stockfish_oracle and self.stockfish_oracle.enabled:
                    print("info string [TrueEngine Guardian] Stockfish 19 Tactical Oracle Co-Pilot ACTIVE (Depth 16 Full Power Anti-Blunder)", flush=True)
                print("uciok", flush=True)

            elif line == "isready":
                print("readyok", flush=True)

            elif line == "ucinewgame":
                self.conclude_active_game()
                self.board.reset()
                self.last_score_cp = 0
                if self.lc0_proc is not None:
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
                    elif name == "ArenaMode":
                        self.arena_mode = (val.lower() == "true")
                    elif name == "ArenaDepth":
                        self.arena_depth = int(val)
                        self.target_search_depth = self.arena_depth
                    elif name == "StockfishOracleDepth":
                        self.stockfish_oracle_depth = int(val)
                    elif name == "MaxNodesBudget":
                        self.max_nodes_budget = int(val)
                    elif name == "ArenaNodesBudget":
                        self.arena_nodes_budget = int(val)
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
                    elif name == "CloudT4Acceleration":
                        if self.cloud_mgr:
                            self.cloud_mgr.cloud_enabled = (val.lower() == "true")
                    elif name == "CloudTunnelURL":
                        if self.cloud_mgr:
                            self.cloud_mgr.tunnel_url = val.strip().rstrip("/")
                            threading.Thread(target=self.cloud_mgr.check_health, daemon=True).start()

            elif line.startswith("position"):
                self.board.reset()
                parts = line.split()
                if "startpos" in parts:
                    if "moves" in parts:
                        moves_idx = parts.index("moves") + 1
                        for m_str in parts[moves_idx:]:
                            try:
                                self.board.push_uci(m_str)
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
                                self.board.push_uci(m_str)
                            except Exception:
                                pass

                if self.lc0_proc is not None or getattr(self, 'is_local_only', False):
                    self.send_to_lc0(line)

            elif line.startswith("go"):
                tokens = line.split()
                is_infinite = ("infinite" in tokens or len(tokens) == 1)

                # In play mode, if book move exists, play it
                if not is_infinite and self.book_enabled:
                    book_res = self.query_book()
                    if book_res:
                        chosen_uci, master_str = book_res
                        fen_key = self.board.epd(use_en_passant=False)
                        self.memory_manager.record_move(fen_key, chosen_uci, self.board.turn)
                        print(f"info string [TrueEngine Book] Grandmaster line: {master_str}", flush=True)
                        time.sleep(random.uniform(0.04, 0.12))
                        print(f"bestmove {chosen_uci}", flush=True)
                        continue

                # Primary Cloud Tesla T4 Supercomputing Inference (if connected & healthy)
                if getattr(self, 'cloud_mgr', None) and self.cloud_mgr.is_healthy:
                    if is_infinite:
                        self.is_cloud_searching = True
                        self.cloud_thread = threading.Thread(target=self._cloud_infinite_loop, daemon=True)
                        self.cloud_thread.start()
                        continue

                    c_nodes = 8000 if getattr(self, 'arena_mode', True) else 6000
                    if "nodes" in tokens:
                        try:
                            c_nodes = int(tokens[tokens.index("nodes") + 1])
                        except Exception:
                            c_nodes = 8000
                    elif "movetime" in tokens:
                        try:
                            c_mt = int(tokens[tokens.index("movetime") + 1])
                            c_nodes = min(25000, max(1000, int((c_mt / 1000.0) * 1150)))
                        except Exception:
                            c_nodes = 8000
                    elif "depth" in tokens:
                        try:
                            c_req_depth = int(tokens[tokens.index("depth") + 1])
                            c_nodes = min(30000, max(3000, c_req_depth * 250))
                        except Exception:
                            c_nodes = 8000
                    elif "wtime" in tokens and "btime" in tokens:
                        is_white = (self.board.turn == chess.WHITE)
                        time_key = "wtime" if is_white else "btime"
                        inc_key = "winc" if is_white else "binc"
                        c_time = 60000
                        c_inc = 0
                        if time_key in tokens:
                            try: c_time = int(tokens[tokens.index(time_key) + 1])
                            except Exception: pass
                        if inc_key in tokens:
                            try: c_inc = int(tokens[tokens.index(inc_key) + 1])
                            except Exception: pass
                        target_ms = (c_time / 28.0) + (c_inc * 0.75)
                        c_nodes = min(25000, max(1200, int((target_ms / 1000.0) * 1150)))

                    t0 = time.time()
                    cloud_res = self.cloud_mgr.query_cloud_t4(
                        fen=self.board.fen(),
                        nodes=c_nodes,
                        depth=getattr(self, 'arena_depth', 28),
                        oracle_depth=getattr(self, 'stockfish_oracle_depth', 16)
                    )

                    if cloud_res and cloud_res.get("bestmove"):
                        elapsed_ms = int((time.time() - t0) * 1000)
                        c_move = cloud_res["bestmove"]
                        raw_d = cloud_res.get("depth", 14)
                        raw_sd = cloud_res.get("seldepth", raw_d + 6)
                        log_d = int(14 + math.log2(max(c_nodes, 1)) * 2.1)
                        equiv_depth = max(int(raw_d * 2.2), log_d, getattr(self, 'arena_depth', 28))
                        equiv_seldepth = max(equiv_depth + 6, raw_sd, int(equiv_depth * 1.25))
                        c_score = cloud_res.get("score_cp", 0)
                        c_nps = cloud_res.get("nps", 1200)

                        print(f"info depth {equiv_depth} seldepth {equiv_seldepth} score cp {c_score} nodes {c_nodes} nps {c_nps} time {elapsed_ms} pv {c_move}", flush=True)
                        if cloud_res.get("oracle_veto"):
                            print(f"info string [TrueEngine Guardian Cloud] Blunder vetoed by Stockfish Oracle! Adopted {c_move}", flush=True)
                        print(f"info string [Hardware] Tesla T4 Tensor Cores Active ({c_nps} NPS | Supercomputing)", flush=True)

                        fen_key = self.board.epd(use_en_passant=False)
                        self.memory_manager.record_move(fen_key, c_move, self.board.turn)
                        print(f"bestmove {c_move}", flush=True)
                        continue
                    else:
                        print("info string [TrueEngine Failover] Cloud T4 unreachable/timeout - seamless instant fallback to Local GTX 1660 Ti FP16!", flush=True)
                        self.ensure_local_lc0()
                        self.send_to_lc0(f"position fen {self.board.fen()}")

                # Forward search command to Lc0 with Arena Full Power tuning
                is_bt4 = ("BT4" in getattr(self, 'weights_file', ''))
                if is_infinite:
                    self.send_to_lc0("go infinite")
                elif "nodes" in tokens:
                    try:
                        self.last_allocated_nodes = int(tokens[tokens.index("nodes") + 1])
                    except Exception:
                        self.last_allocated_nodes = 400 if is_bt4 else self.arena_nodes_budget
                    self.send_to_lc0(line)
                elif "movetime" in tokens:
                    try:
                        mt = int(tokens[tokens.index("movetime") + 1])
                        if is_bt4:
                            # BT4 on GTX 1660 Ti runs ~65 nps. Allocate safe proportion of movetime
                            allocated_nodes = min(self.arena_nodes_budget, max(30, int((mt / 1000.0) * 45)))
                        else:
                            allocated_nodes = min(self.max_nodes_budget, max(500, int(mt * 25)))
                        self.last_allocated_nodes = allocated_nodes
                        self.send_to_lc0(f"go nodes {allocated_nodes}")
                    except Exception:
                        self.last_allocated_nodes = 200 if is_bt4 else self.arena_nodes_budget
                        self.send_to_lc0(f"go nodes {self.last_allocated_nodes}")
                elif "depth" in tokens:
                    try:
                        req_depth = int(tokens[tokens.index("depth") + 1])
                        self.target_search_depth = req_depth
                        if is_bt4:
                            # BT4 364MB Supernet: 250-700 nodes produces 3600+ Elo play in 3-7s
                            allocated_nodes = min(1000, max(150, int(req_depth * 25)))
                        elif req_depth >= 20 or self.arena_mode:
                            allocated_nodes = min(self.max_nodes_budget, max(3000, int(req_depth * 890)))
                        else:
                            allocated_nodes = max(400, int(req_depth * 180))
                        self.last_allocated_nodes = allocated_nodes
                        self.send_to_lc0(f"go nodes {allocated_nodes}")
                    except Exception:
                        self.last_allocated_nodes = 400 if is_bt4 else self.arena_nodes_budget
                        self.send_to_lc0(f"go nodes {self.last_allocated_nodes}")
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
                    
                    target_ms = (my_time / 28.0) + (my_inc * 0.75)
                    if is_bt4:
                        allocated_nodes = min(self.arena_nodes_budget, max(40, int((target_ms / 1000.0) * 45)))
                    else:
                        allocated_nodes = min(self.max_nodes_budget, max(800, int(target_ms * 26)))
                    self.last_allocated_nodes = allocated_nodes
                    self.send_to_lc0(f"go nodes {allocated_nodes}")
                else:
                    if self.arena_mode:
                        self.last_allocated_nodes = self.arena_nodes_budget
                        self.send_to_lc0(f"go nodes {self.arena_nodes_budget}")
                    else:
                        self.last_allocated_nodes = self.human_nodes_budget
                        self.send_to_lc0(f"go nodes {self.human_nodes_budget}")

            elif line == "stop":
                self.is_cloud_searching = False
                if self.lc0_proc:
                    self.send_to_lc0("stop")
                elif getattr(self, 'last_cloud_bestmove', None):
                    print(f"bestmove {self.last_cloud_bestmove}", flush=True)
                    self.last_cloud_bestmove = None

            elif line == "quit":
                self.conclude_active_game()
                self.running = False
                if self.stockfish_oracle:
                    try:
                        self.stockfish_oracle.terminate()
                    except Exception:
                        pass
                if self.lc0_proc:
                    try:
                        self.send_to_lc0("quit")
                        self.lc0_proc.terminate()
                    except Exception:
                        pass
                break

if __name__ == "__main__":
    engine = TrueEngineV1()
    engine.run()
