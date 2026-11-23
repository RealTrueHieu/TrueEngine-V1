#!/usr/bin/env python3
"""
TrueEngine V1: Dedicated Molab Blackwell RPC Worker
=====================================================
Target Hardware: NVIDIA RTX PRO 6000 Blackwell (98 GB VRAM)
Operating Role: Dedicated Neural Inference Engine for Public Users & En Croissant UCI
Hub: https://trueengine.truehieu.qzz.io
"""

import os
import sys
import time
import json
import logging
import requests
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import chess

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BlackwellWorker")

GATEWAY_URL = os.environ.get("GATEWAY_URL", "https://trueengine.truehieu.qzz.io")
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

logger.info(f"Initialized Blackwell Worker on {DEVICE}")
if torch.cuda.is_available():
    logger.info(f"CUDA Device: {torch.cuda.get_device_name(0)}")
    vram_gb = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
    logger.info(f"Total Dedicated VRAM: {vram_gb} GB")

# --- MODEL ARCHITECTURE ---
class ResidualBlock(nn.Module):
    def __init__(self, channels=128):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x):
        res = x
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.bn2(self.conv2(x))
        return F.relu(x + res)

class TrueEngineChessNet(nn.Module):
    def __init__(self, in_channels=12, num_blocks=6, channels=128):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(in_channels, channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True)
        )
        self.blocks = nn.ModuleList([ResidualBlock(channels) for _ in range(num_blocks)])
        self.policy_from = nn.Sequential(
            nn.Conv2d(channels, 32, 1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Flatten(),
            nn.Linear(32 * 8 * 8, 64)
        )
        self.policy_to = nn.Sequential(
            nn.Conv2d(channels, 32, 1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Flatten(),
            nn.Linear(32 * 8 * 8, 64)
        )
        self.value_head = nn.Sequential(
            nn.Conv2d(channels, 16, 1),
            nn.BatchNorm2d(16),
            nn.ReLU(inplace=True),
            nn.Flatten(),
            nn.Linear(16 * 8 * 8, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, 1),
            nn.Tanh()
        )

    def forward(self, x):
        h = self.stem(x)
        for block in self.blocks:
            h = block(h)
        return self.policy_from(h), self.policy_to(h), self.value_head(h)

def board_to_tensor(board: chess.Board):
    planes = np.zeros((12, 8, 8), dtype=np.float32)
    piece_map = {
        chess.PAWN: 0, chess.KNIGHT: 1, chess.BISHOP: 2,
        chess.ROOK: 3, chess.QUEEN: 4, chess.KING: 5
    }
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is not None:
            r = 7 - (sq // 8)
            c = sq % 8
            offset = 0 if piece.color == chess.WHITE else 6
            planes[piece_map[piece.piece_type] + offset, r, c] = 1.0
    return torch.from_numpy(planes).unsqueeze(0).to(DEVICE)

def evaluate_and_predict(model, board: chess.Board):
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return None, "", 0, 0.0, 0.5, []

    x = board_to_tensor(board)
    with torch.no_grad():
        p_from, p_to, val = model(x)
        val_scalar = float(val.squeeze().cpu().item())
        probs_from = F.softmax(p_from.squeeze(0), dim=-1).cpu().numpy()
        probs_to = F.softmax(p_to.squeeze(0), dim=-1).cpu().numpy()

    scored_moves = []
    for m in legal_moves:
        score = float(probs_from[m.from_square] * probs_to[m.to_square])
        if board.is_capture(m):
            score *= 1.15
        if m.promotion:
            score *= 1.25
        scored_moves.append((score, m))

    scored_moves.sort(key=lambda s: s[0], reverse=True)
    best_score, best_move = scored_moves[0]

    pov_val = val_scalar if board.turn == chess.WHITE else -val_scalar
    win_prob = round((pov_val + 1.0) / 2.0, 4)
    cp = int(pov_val * 400.0)

    top_moves = [
        {"uci": m.uci(), "san": board.san(m), "score": round(score, 4)}
        for score, m in scored_moves[:5]
    ]

    return best_move.uci(), board.san(best_move), cp, pov_val, win_prob, top_moves

def load_model():
    model = TrueEngineChessNet().to(DEVICE)
    ckpt_paths = [
        "models/trueengine_v1_latest.pt",
        "/marimo/TrueEngine-V1/models/trueengine_v1_latest.pt",
        "trueengine_v1_latest.pt"
    ]
    ckpt_file = None
    for p in ckpt_paths:
        if os.path.exists(p):
            ckpt_file = p
            break

    if not ckpt_file:
        logger.info("Downloading latest checkpoint from gateway...")
        try:
            r = requests.get(f"{GATEWAY_URL}/download/model", timeout=30)
            if r.status_code == 200:
                with open("trueengine_v1_latest.pt", "wb") as f:
                    f.write(r.content)
                ckpt_file = "trueengine_v1_latest.pt"
                logger.info("Checkpoint downloaded successfully.")
        except Exception as e:
            logger.warning(f"Could not download checkpoint: {e}")

    if ckpt_file:
        logger.info(f"Loading weights from {ckpt_file}...")
        ckpt = torch.load(ckpt_file, map_location=DEVICE)
        sd = ckpt["model_state_dict"] if "model_state_dict" in ckpt else ckpt
        model.load_state_dict(sd)
        logger.info("Model loaded successfully!")
    else:
        logger.warning("No checkpoint found; running with initialized weights.")

    model.eval()
    return model

def main():
    logger.info("Starting TrueEngine Blackwell RPC Worker loop...")
    model = load_model()

    session = requests.Session()
    poll_url = f"{GATEWAY_URL}/api/rpc/poll"
    result_url = f"{GATEWAY_URL}/api/rpc/result"

    consecutive_errors = 0
    while True:
        try:
            resp = session.get(poll_url, timeout=5)
            if resp.status_code != 200:
                time.sleep(1.0)
                continue

            consecutive_errors = 0
            data = resp.json()
            task = data.get("task")
            if not task:
                time.sleep(0.05)
                continue

            t0 = time.time()
            task_id = task["task_id"]
            fen = task.get("fen", chess.STARTING_FEN)
            board = chess.Board(fen)

            best_uci, san, cp, val, win_prob, top_moves = evaluate_and_predict(model, board)
            inference_ms = round((time.time() - t0) * 1000, 2)

            payload = {
                "task_id": task_id,
                "best_move": best_uci or "0000",
                "san": san,
                "evaluation_cp": cp,
                "evaluation_val": val,
                "win_probability": win_prob,
                "inference_ms": inference_ms,
                "top_moves": top_moves
            }

            session.post(result_url, json=payload, timeout=5)
            logger.info(f"Task {task_id[:8]} served in {inference_ms}ms -> {best_uci} ({san}) [cp: {cp}]")

        except requests.exceptions.RequestException as e:
            consecutive_errors += 1
            if consecutive_errors % 10 == 0:
                logger.warning(f"Connection issue with gateway: {e}")
            time.sleep(1.0)
        except Exception as e:
            logger.error(f"Inference error: {e}")
            time.sleep(0.1)

if __name__ == "__main__":
    main()
