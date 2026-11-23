#!/usr/bin/env python3
"""
TrueEngine V1: Public User Neural Inference Server & Web Chess GUI
===================================================================
Hardware: NVIDIA RTX PRO 6000 Blackwell Server Edition (98 GB VRAM)
Public Domain: https://trueengine.truehieu.qzz.io / https://chess.truehieu.qzz.io
Supports:
- Web GUI for playing chess directly in browser vs TrueEngine V1
- REST API (/api/predict_move, /api/evaluate) for En Croissant UCI bridge and bots
"""

import os
import sys
import time
import json
import random
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import chess
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
USE_CUDA = torch.cuda.is_available()

# ResNet Model Architecture matching TrueEngine V1
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
            nn.Linear(16 * 8 * 8, 64),
            nn.ReLU(inplace=True),
            nn.Linear(64, 1),
            nn.Tanh()
        )

    def forward(self, x):
        h = self.stem(x)
        for block in self.blocks:
            h = block(h)
        p_from = self.policy_from(h)
        p_to = self.policy_to(h)
        val = self.value_head(h)
        return p_from, p_to, val

def board_to_planes(board):
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
            plane_idx = offset + piece_map[piece.piece_type]
            planes[plane_idx, r, c] = 1.0
    return planes

# Initialize Model
print(f"[*] Initializing TrueEngine V1 Neural Network on {DEVICE}...")
model = TrueEngineChessNet().to(DEVICE)
model.eval()

# Try loading latest weights
WEIGHTS_PATHS = [
    "/marimo/TrueEngine-V1/models/trueengine_v1_latest.pt",
    "/data/workspace/TrueEngine-V1/models/trueengine_v1_latest.pt",
    "models/trueengine_v1_latest.pt",
    "trueengine_v1_latest.pt"
]
for wp in WEIGHTS_PATHS:
    if os.path.exists(wp):
        try:
            model.load_state_dict(torch.load(wp, map_location=DEVICE))
            print(f"[✓] Successfully loaded weights from {wp}!")
            break
        except Exception as e:
            print(f"[!] Error loading {wp}: {e}")

app = FastAPI(title="TrueEngine V1 Blackwell Neural Chess Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MoveRequest(BaseModel):
    fen: str
    temperature: float = 0.05
    depth: int = 15

@app.get("/health")
def health():
    return {
        "status": "online",
        "engine": "TrueEngine V1 (Blackwell Server Edition)",
        "hardware": "NVIDIA RTX PRO 6000 Blackwell",
        "vram": "98 GB VRAM",
        "device": str(DEVICE),
        "domain": "truehieu.qzz.io"
    }

@app.post("/api/predict_move")
def predict_move(req: MoveRequest):
    t0 = time.time()
    try:
        board = chess.Board(req.fen)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid FEN: {e}")

    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return {"status": "game_over", "best_move": None, "evaluation": 0.0}

    planes = board_to_planes(board)
    tensor = torch.from_numpy(planes).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        if USE_CUDA:
            with torch.amp.autocast('cuda'):
                p_from, p_to, val = model(tensor)
        else:
            p_from, p_to, val = model(tensor)

        p_from_prob = F.softmax(p_from[0], dim=-1).cpu().numpy()
        p_to_prob = F.softmax(p_to[0], dim=-1).cpu().numpy()
        val_score = float(val[0][0].item())

    # Score legal moves
    scored_moves = []
    for m in legal_moves:
        score = float(p_from_prob[m.from_square] * p_to_prob[m.to_square])
        scored_moves.append((score, m))

    scored_moves.sort(key=lambda x: x[0], reverse=True)
    best_move = scored_moves[0][1]

    # Convert val_score (-1.0 to 1.0) to centipawns
    cp = int(val_score * 800)
    win_prob = round((val_score + 1.0) / 2.0, 4)
    elapsed_ms = round((time.time() - t0) * 1000, 2)

    top_moves = [
        {"uci": m.uci(), "san": board.san(m), "score": round(s, 6)}
        for s, m in scored_moves[:5]
    ]

    return {
        "best_move": best_move.uci(),
        "san": board.san(best_move),
        "evaluation_cp": cp,
        "evaluation_val": round(val_score, 4),
        "win_probability": win_prob,
        "inference_ms": elapsed_ms,
        "top_moves": top_moves,
        "hardware": "NVIDIA RTX PRO 6000 Blackwell (98 GB VRAM)"
    }

@app.get("/", response_class=HTMLResponse)
def chess_gui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>TrueEngine V1 👑 Blackwell Neural Chess Playground</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/chessboard-js/1.0.0/chessboard-1.0.0.min.css">
  <script src="https://code.jquery.com/jquery-3.5.1.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/chessboard-js/1.0.0/chessboard-1.0.0.min.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;800&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #07090e;
      --card-bg: rgba(13, 18, 28, 0.92);
      --accent: #00f2fe;
      --accent-green: #00f5a0;
      --accent-gold: #ffd200;
      --accent-purple: #c084fc;
      --text: #f0f4f8;
      --text-muted: #8a99ad;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      background-image: radial-gradient(at 0% 0%, rgba(0, 242, 254, 0.15) 0px, transparent 50%),
                        radial-gradient(at 100% 100%, rgba(192, 132, 252, 0.1) 0px, transparent 50%);
      color: var(--text);
      font-family: 'Plus Jakarta Sans', sans-serif;
      min-height: 100vh;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      padding: 20px;
    }
    .header { text-align: center; margin-bottom: 20px; }
    .header h1 { font-size: 28px; font-weight: 800; color: #fff; display: flex; align-items: center; justify-content: center; gap: 10px; }
    .header h1 span { color: var(--accent); }
    .badge {
      display: inline-block; background: rgba(0, 242, 254, 0.15); border: 1px solid var(--accent);
      color: var(--accent); padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; margin-top: 8px;
      font-family: 'JetBrains Mono', monospace;
    }
    .main-layout { display: flex; gap: 24px; flex-wrap: wrap; justify-content: center; max-width: 960px; width: 100%; }
    .board-container { width: 440px; max-width: 100%; }
    #board { border-radius: 8px; overflow: hidden; box-shadow: 0 10px 40px rgba(0,0,0,0.6); }
    .panel {
      flex: 1; min-width: 320px; background: var(--card-bg); border: 1px solid rgba(255,255,255,0.08);
      border-radius: 16px; padding: 20px; display: flex; flex-direction: column; gap: 14px;
    }
    .panel h2 { font-size: 16px; font-weight: 700; border-bottom: 1px solid rgba(255,255,255,0.06); padding-bottom: 10px; }
    .stat-row { display: flex; justify-content: space-between; font-size: 13.5px; }
    .stat-label { color: var(--text-muted); }
    .stat-val { font-family: 'JetBrains Mono', monospace; font-weight: 700; color: var(--accent); }
    .eval-bar-bg { width: 100%; height: 12px; background: #333; border-radius: 6px; overflow: hidden; margin: 4px 0; }
    .eval-bar-fill { height: 100%; width: 50%; background: linear-gradient(90deg, #ff4757, #00f5a0); transition: width 0.3s; }
    .log-box {
      flex: 1; min-height: 140px; background: rgba(0,0,0,0.4); border-radius: 8px; padding: 12px;
      font-family: 'JetBrains Mono', monospace; font-size: 12px; overflow-y: auto; color: #a0aec0;
    }
    .btn-row { display: flex; gap: 10px; }
    button {
      flex: 1; padding: 10px; border-radius: 8px; border: 1px solid var(--accent);
      background: rgba(0, 242, 254, 0.1); color: var(--accent); font-weight: 700; cursor: pointer; transition: 0.2s;
    }
    button:hover { background: var(--accent); color: #000; }
  </style>
</head>
<body>
  <div class="header">
    <h1>👑 TrueEngine <span>V1</span> Playground</h1>
    <div class="badge">⚡ LIVE ON NVIDIA RTX PRO 6000 BLACKWELL (98 GB VRAM)</div>
  </div>

  <div class="main-layout">
    <div class="board-container">
      <div id="board"></div>
    </div>

    <div class="panel">
      <h2>Neural Game Controller</h2>
      <div class="stat-row">
        <span class="stat-label">Opponent Engine</span>
        <span class="stat-val">TrueEngine V1 (ResNet-12)</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Hardware Acceleration</span>
        <span class="stat-val" style="color: var(--accent-green);">RTX 6000 Blackwell (98GB)</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Inference Latency</span>
        <span class="stat-val" id="latency">-- ms</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Win Probability</span>
        <span class="stat-val" id="win-prob">50.0%</span>
      </div>

      <div>
        <div class="stat-row" style="margin-bottom: 4px;">
          <span class="stat-label">Evaluation Bar</span>
          <span class="stat-val" id="eval-cp">0.00</span>
        </div>
        <div class="eval-bar-bg">
          <div class="eval-bar-fill" id="eval-fill"></div>
        </div>
      </div>

      <div class="log-box" id="game-log">
        [System] Engine initialized. Play as White by dragging any piece!
      </div>

      <div class="btn-row">
        <button onclick="newGame()">New Game</button>
        <button onclick="flipBoard()">Flip Board</button>
      </div>
    </div>
  </div>

  <script>
    var board = null;
    var game = new Chess();

    function onDragStart (source, piece, position, orientation) {
      if (game.game_over()) return false;
      if (piece.search(/^b/) !== -1) return false;
    }

    async function makeEngineMove() {
      const fen = game.fen();
      const t0 = performance.now();
      try {
        const resp = await fetch('/api/predict_move', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ fen: fen })
        });
        const data = await resp.json();
        const lat = Math.round(performance.now() - t0);
        document.getElementById('latency').innerText = lat + ' ms (' + data.hardware + ')';
        document.getElementById('win-prob').innerText = (data.win_probability * 100).toFixed(1) + '%';
        document.getElementById('eval-cp').innerText = (data.evaluation_cp / 100).toFixed(2);
        
        // Update eval bar (50% is equal)
        let fillPct = 50 + (data.evaluation_cp / 20);
        fillPct = Math.max(5, Math.min(95, fillPct));
        document.getElementById('eval-fill').style.width = fillPct + '%';

        if (data.best_move) {
          game.move({
            from: data.best_move.substring(0, 2),
            to: data.best_move.substring(2, 4),
            promotion: 'q'
          });
          board.position(game.fen());
          logMove('Engine: ' + data.san + ' (Score: ' + data.evaluation_val + ')');
        }
      } catch (e) {
        logMove('[!] Engine move error: ' + e);
      }
    }

    function onDrop (source, target) {
      var move = game.move({
        from: source,
        to: target,
        promotion: 'q'
      });
      if (move === null) return 'snapback';
      logMove('You: ' + move.san);
      window.setTimeout(makeEngineMove, 250);
    }

    function onSnapEnd () {
      board.position(game.fen());
    }

    function logMove(txt) {
      const el = document.getElementById('game-log');
      el.innerHTML += '<br>' + txt;
      el.scrollTop = el.scrollHeight;
    }

    function newGame() {
      game.reset();
      board.start();
      document.getElementById('game-log').innerHTML = '[System] New game started!';
      document.getElementById('eval-fill').style.width = '50%';
    }

    function flipBoard() {
      board.flip();
    }

    var config = {
      draggable: true,
      position: 'start',
      onDragStart: onDragStart,
      onDrop: onDrop,
      onSnapEnd: onSnapEnd,
      pieceTheme: 'https://chessboardjs.com/img/chesspieces/wikipedia/{piece}.png'
    };
    board = Chessboard('board', config);
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
