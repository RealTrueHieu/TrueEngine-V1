import os
import sys
import time
import random
import json
import threading
import subprocess
from collections import deque
import numpy as np

import chess
import chess.engine
import torch
import torch.nn as nn
import torch.optim as optim
from torch.cuda.amp import autocast, GradScaler

# Ensure stockfish is in PATH
if os.path.exists("/usr/games/stockfish") and not os.path.exists("/usr/local/bin/stockfish"):
    try:
        os.symlink("/usr/games/stockfish", "/usr/local/bin/stockfish")
    except Exception:
        pass

SF_PATH = "/usr/games/stockfish" if os.path.exists("/usr/games/stockfish") else "stockfish"
CHECKPOINT_DIR = "/content/checkpoints"
os.makedirs(CHECKPOINT_DIR, exist_ok=True)
STATUS_LOG = "/content/selfplay_100m_status.log"
METRICS_JSON = "/content/selfplay_100m_metrics.json"
DISTILLED_JSON = "/content/colab_distilled_experience.json"

USE_CUDA = torch.cuda.is_available()
DEVICE = torch.device("cuda" if USE_CUDA else "cpu")
if not USE_CUDA:
    torch.set_num_threads(os.cpu_count() or 2)

PIECE_MAP = {
    chess.PAWN: 0,
    chess.KNIGHT: 1,
    chess.BISHOP: 2,
    chess.ROOK: 3,
    chess.QUEEN: 4,
    chess.KING: 5
}

def board_to_tensor(board: chess.Board):
    """Encodes board state into (14, 8, 8) float32 tensor."""
    planes = np.zeros((14, 8, 8), dtype=np.float32)
    for sq, piece in board.piece_map().items():
        row = sq // 8
        col = sq % 8
        plane_idx = PIECE_MAP[piece.piece_type]
        if piece.color == chess.BLACK:
            plane_idx += 6
        planes[plane_idx, row, col] = 1.0
    
    # Plane 12: Turn (1 if white, 0 if black)
    if board.turn == chess.WHITE:
        planes[12, :, :] = 1.0
    
    # Plane 13: Castling rights
    if board.has_kingside_castling_rights(chess.WHITE):
        planes[13, 0, 4:8] = 1.0
    if board.has_queenside_castling_rights(chess.WHITE):
        planes[13, 0, 0:4] = 1.0
    if board.has_kingside_castling_rights(chess.BLACK):
        planes[13, 7, 4:8] = 1.0
    if board.has_queenside_castling_rights(chess.BLACK):
        planes[13, 7, 0:4] = 1.0

    return planes

def move_to_index(move: chess.Move):
    """Encodes move (from_square * 64 + to_square) -> [0, 4095]."""
    return move.from_square * 64 + move.to_square

class ResidualBlock(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x):
        res = x
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += res
        return self.relu(out)

class TrueEngineSuperNet(nn.Module):
    def __init__(self, in_channels=14, channels=128, num_blocks=6):
        super().__init__()
        self.in_conv = nn.Sequential(
            nn.Conv2d(in_channels, channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True)
        )
        self.blocks = nn.ModuleList([ResidualBlock(channels) for _ in range(num_blocks)])
        
        # Policy Head (4096 moves)
        self.policy_head = nn.Sequential(
            nn.Conv2d(channels, 32, kernel_size=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Flatten(),
            nn.Linear(32 * 8 * 8, 4096)
        )
        
        # Value Head (Scalar in [-1, 1])
        self.value_head = nn.Sequential(
            nn.Conv2d(channels, 16, kernel_size=1, bias=False),
            nn.BatchNorm2d(16),
            nn.ReLU(inplace=True),
            nn.Flatten(),
            nn.Linear(16 * 8 * 8, 256),
            nn.ReLU(inplace=True),
            nn.Linear(256, 1),
            nn.Tanh()
        )

    def forward(self, x):
        out = self.in_conv(x)
        for b in self.blocks:
            out = b(out)
        p = self.policy_head(out)
        v = self.value_head(out)
        return p, v

class StreamingReplayBuffer:
    def __init__(self, capacity=250000):
        self.capacity = capacity
        self.states = np.zeros((capacity, 14, 8, 8), dtype=np.float32)
        self.target_moves = np.zeros(capacity, dtype=np.int64)
        self.target_values = np.zeros(capacity, dtype=np.float32)
        self.idx = 0
        self.size = 0
        self.lock = threading.Lock()

    def add_game(self, transitions):
        with self.lock:
            for s, m, v in transitions:
                self.states[self.idx] = s
                self.target_moves[self.idx] = m
                self.target_values[self.idx] = v
                self.idx = (self.idx + 1) % self.capacity
                if self.size < self.capacity:
                    self.size += 1

    def sample_batch(self, batch_size=512):
        with self.lock:
            if self.size < batch_size:
                return None
            indices = np.random.choice(self.size, batch_size, replace=False)
            b_s = torch.from_numpy(self.states[indices])
            if USE_CUDA:
                b_s = b_s.pin_memory()
            b_m = torch.from_numpy(self.target_moves[indices])
            b_v = torch.from_numpy(self.target_values[indices])
            return b_s, b_m, b_v

class Massive100MSelfPlayCoordinator:
    def __init__(self, target_games=100000000):
        self.target_games = target_games
        self.buffer = StreamingReplayBuffer(capacity=250000)
        self.model = TrueEngineSuperNet().to(DEVICE)
        self.optimizer = optim.AdamW(self.model.parameters(), lr=1e-3, weight_decay=1e-4)
        self.scaler = GradScaler() if USE_CUDA else None
        self.policy_loss_fn = nn.CrossEntropyLoss()
        self.value_loss_fn = nn.MSELoss()

        self.games_completed = 0
        self.positions_generated = 0
        self.start_time = time.time()
        self.running = True
        self.distilled_memory = {}
        self.distilled_lock = threading.Lock()

        # Diverse Opening Seed FENs for comprehensive opening exploration
        self.seed_openings = [
            chess.STARTING_FEN,
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",  # 1. e4
            "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq d3 0 1",  # 1. d4
            "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",  # French
            "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",  # Caro-Kann
            "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3", # Ruy/Italian
            "rnbqkb1r/pppppp1p/5np1/8/2PP4/8/PP2PPPP/RNBQKBNR w KQkq - 0 2", # King's Indian
            "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2"   # Sicilian
        ]

    def _select_policy_move(self, board, temperature=0.3):
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return None
        
        # Fast evaluation with network
        with torch.no_grad():
            s_tensor = torch.from_numpy(board_to_tensor(board)).unsqueeze(0).to(DEVICE)
            if USE_CUDA:
                with autocast():
                    p_logits, _ = self.model(s_tensor)
            else:
                p_logits, _ = self.model(s_tensor)
            p_logits = p_logits[0].cpu().numpy()

        legal_indices = [move_to_index(m) for m in legal_moves]
        sub_logits = p_logits[legal_indices] / max(temperature, 0.05)
        
        # Softmax with numerical stability
        exp_logits = np.exp(sub_logits - np.max(sub_logits))
        probs = exp_logits / np.sum(exp_logits)
        
        chosen_idx = np.random.choice(len(legal_moves), p=probs)
        return legal_moves[chosen_idx]

    def worker_selfplay(self, worker_id):
        """Worker thread generating high-speed self-play games."""
        while self.running:
            board = chess.Board(random.choice(self.seed_openings))
            transitions = []  # (state, move_idx, turn)
            moves_count = 0
            max_moves = 120

            while not board.is_game_over() and moves_count < max_moves:
                turn = board.turn
                s_np = board_to_tensor(board)
                
                # Temperature: explore more in early moves
                temp = 1.0 if moves_count < 8 else 0.2
                move = self._select_policy_move(board, temperature=temp)
                if not move:
                    break

                m_idx = move_to_index(move)
                transitions.append((s_np, m_idx, turn, board.epd(use_en_passant=False), move.uci()))
                board.push(move)
                moves_count += 1

            # Determine game outcome
            result = board.result()
            if result == "1-0":
                val_white = 1.0
            elif result == "0-1":
                val_white = -1.0
            else:
                val_white = 0.0

            # Store in replay buffer & distill knowledge
            game_samples = []
            for s_np, m_idx, turn, epd_key, uci_move in transitions:
                z = val_white if turn == chess.WHITE else -val_white
                game_samples.append((s_np, m_idx, z))

                # Update distilled knowledge dictionary
                with self.distilled_lock:
                    if epd_key not in self.distilled_memory:
                        self.distilled_memory[epd_key] = {}
                    if uci_move not in self.distilled_memory[epd_key]:
                        self.distilled_memory[epd_key][uci_move] = {"visits": 0, "wins": 0, "losses": 0, "multiplier": 1.0}
                    entry = self.distilled_memory[epd_key][uci_move]
                    entry["visits"] += 1
                    if z == 1.0:
                        entry["wins"] += 1
                        entry["multiplier"] = min(3.5, entry["multiplier"] * 1.05)
                    elif z == -1.0:
                        entry["losses"] += 1
                        entry["multiplier"] = max(0.01, entry["multiplier"] * 0.90)

            self.buffer.add_game(game_samples)
            self.games_completed += 1
            self.positions_generated += len(game_samples)

    def worker_stockfish_sparring(self):
        """Worker sparring against Stockfish at depth 3 to anchor tactical fundamentals."""
        if not os.path.exists(SF_PATH):
            return
        
        try:
            engine = chess.engine.SimpleEngine.popen_uci(SF_PATH)
            engine.configure({"Threads": 1, "Hash": 16})
        except Exception:
            return

        while self.running:
            board = chess.Board()
            transitions = []
            moves_count = 0
            our_color = random.choice([chess.WHITE, chess.BLACK])

            while not board.is_game_over() and moves_count < 100:
                turn = board.turn
                s_np = board_to_tensor(board)

                if turn == our_color:
                    move = self._select_policy_move(board, temperature=0.2)
                    if not move:
                        break
                    m_idx = move_to_index(move)
                    transitions.append((s_np, m_idx, turn))
                    board.push(move)
                else:
                    # Stockfish rapid response
                    try:
                        res = engine.play(board, chess.engine.Limit(depth=3, time=0.005))
                        board.push(res.move)
                    except Exception:
                        break
                moves_count += 1

            result = board.result()
            val = 1.0 if result == "1-0" else (-1.0 if result == "0-1" else 0.0)
            our_val = val if our_color == chess.WHITE else -val

            game_samples = [(s_np, m_idx, our_val) for s_np, m_idx, turn in transitions]
            self.buffer.add_game(game_samples)
            self.games_completed += 1
            self.positions_generated += len(game_samples)

    def train_continuous(self):
        """Continuous training loop powered by Tesla T4 GPU Tensor Cores."""
        step = 0
        last_log_time = time.time()
        last_distill_time = time.time()
        last_checkpoint_games = 0

        print(f"[TrueEngine Streamer] Continuous training activated on {DEVICE}...")

        while self.running and self.games_completed < self.target_games:
            batch = self.buffer.sample_batch(batch_size=512)
            if batch is None:
                time.sleep(0.05)
                continue

            b_s, b_m, b_v = batch
            b_s = b_s.to(DEVICE, non_blocking=True)
            b_m = b_m.to(DEVICE, non_blocking=True)
            b_v = b_v.to(DEVICE, non_blocking=True).unsqueeze(1)

            self.optimizer.zero_grad(set_to_none=True)
            if USE_CUDA:
                with autocast():
                    p_out, v_out = self.model(b_s)
                    p_loss = self.policy_loss_fn(p_out, b_m)
                    v_loss = self.value_loss_fn(v_out, b_v)
                    loss = p_loss + 0.5 * v_loss

                self.scaler.scale(loss).backward()
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                p_out, v_out = self.model(b_s)
                p_loss = self.policy_loss_fn(p_out, b_m)
                v_loss = self.value_loss_fn(v_out, b_v)
                loss = p_loss + 0.5 * v_loss
                loss.backward()
                self.optimizer.step()

            step += 1

            # Log metrics every 3 seconds
            if time.time() - last_log_time > 3.0:
                elapsed = time.time() - self.start_time
                gps = self.games_completed / max(1.0, elapsed)
                pps = self.positions_generated / max(1.0, elapsed)
                
                # Accuracy calculation
                with torch.no_grad():
                    pred_top1 = (torch.argmax(p_out, dim=1) == b_m).float().mean().item() * 100.0

                log_line = (
                    f"[{time.strftime('%H:%M:%S')}] Games: {self.games_completed:,}/{self.target_games:,} "
                    f"({(self.games_completed/self.target_games)*100:.3f}%) | "
                    f"Positions: {self.positions_generated:,} | "
                    f"Speed: {gps:.1f} games/s ({pps:.1f} pos/s) | "
                    f"P-Loss: {p_loss.item():.4f} | V-Loss: {v_loss.item():.4f} | "
                    f"Top-1 Acc: {pred_top1:.1f}%"
                )
                print(log_line, flush=True)

                with open(STATUS_LOG, "w", encoding="utf-8") as f:
                    f.write(log_line + "\n")

                metrics_data = {
                    "games_completed": self.games_completed,
                    "target_games": self.target_games,
                    "positions_generated": self.positions_generated,
                    "games_per_sec": round(gps, 2),
                    "pos_per_sec": round(pps, 2),
                    "policy_loss": round(p_loss.item(), 4),
                    "value_loss": round(v_loss.item(), 4),
                    "top1_acc": round(pred_top1, 2),
                    "elapsed_sec": round(elapsed, 1),
                    "timestamp": int(time.time())
                }
                with open(METRICS_JSON, "w", encoding="utf-8") as f:
                    json.dump(metrics_data, f, indent=2)

                last_log_time = time.time()

            # Auto-Distill: Export distilled knowledge memory every 30 seconds
            if time.time() - last_distill_time > 30.0 and len(self.distilled_memory) > 0:
                with self.distilled_lock:
                    temp_dist = DISTILLED_JSON + ".tmp"
                    with open(temp_dist, "w", encoding="utf-8") as f:
                        json.dump(self.distilled_memory, f)
                    if os.path.exists(DISTILLED_JSON):
                        os.replace(temp_dist, DISTILLED_JSON)
                    else:
                        os.rename(temp_dist, DISTILLED_JSON)
                print(f"[Auto-Distill] Streamed {len(self.distilled_memory)} positions to {DISTILLED_JSON}", flush=True)
                last_distill_time = time.time()

            # Checkpoint every 1,000 games
            if self.games_completed - last_checkpoint_games >= 1000:
                ckpt_path = os.path.join(CHECKPOINT_DIR, f"trueengine_supernet_{self.games_completed}.pt")
                torch.save({
                    "model_state": self.model.state_dict(),
                    "games_completed": self.games_completed,
                    "positions_generated": self.positions_generated,
                    "optimizer_state": self.optimizer.state_dict()
                }, ckpt_path)
                
                # Also save canonical latest weights
                torch.save(self.model.state_dict(), "/content/trueengine_supernet_latest.pt")
                print(f"[Checkpoint Saved] -> {ckpt_path}", flush=True)
                last_checkpoint_games = self.games_completed

    def launch(self):
        print(f"===============================================================")
        print(f" TrueEngine V1: 100 Million Massive Self-Play & Stream Training")
        print(f" Target: {self.target_games:,} Games | Hardware: Tesla T4 (FP16)")
        print(f"===============================================================")

        # Spawn 4 Parallel Generation Workers
        threads = []
        for i in range(3):
            t = threading.Thread(target=self.worker_selfplay, args=(i,), daemon=True)
            t.start()
            threads.append(t)
        
        # 1 Stockfish Sparring Worker for tactical discipline
        t_sf = threading.Thread(target=self.worker_stockfish_sparring, daemon=True)
        t_sf.start()
        threads.append(t_sf)

        # Main thread runs continuous training on GPU
        try:
            self.train_continuous()
        except KeyboardInterrupt:
            self.running = False
            print("Stopping workers cleanly...")

if __name__ == "__main__":
    coordinator = Massive100MSelfPlayCoordinator(target_games=100000000)
    coordinator.launch()
