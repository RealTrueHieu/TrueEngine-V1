import os
import sys
import subprocess
import threading
import time
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import chess

app = FastAPI(title="TrueEngine Cloud T4 Supercomputing Bridge")

LC0_BIN = "/root/lc0/build/release/lc0"
BT4_WEIGHTS = "/root/chess_bin/bt4.pb.gz"
STOCKFISH_BIN = "/root/chess_bin/stockfish/stockfish-ubuntu-x86-64-avx2"

lc0_proc = None
sf_proc = None
lock = threading.Lock()

class EvalRequest(BaseModel):
    fen: str
    nodes: int = 6000
    depth: int = 28
    oracle_depth: int = 18

def ensure_lc0():
    global lc0_proc
    if lc0_proc is None or lc0_proc.poll() is not None:
        cmd = [LC0_BIN, f"--weights={BT4_WEIGHTS}", "--backend=cuda-fp16", "--threads=2", "--minibatch-size=256"]
        lc0_proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        lc0_proc.stdin.write("uci\nisready\n")
        lc0_proc.stdin.flush()
        while True:
            line = lc0_proc.stdout.readline()
            if "readyok" in line:
                break

def ensure_sf():
    global sf_proc
    if sf_proc is None or sf_proc.poll() is not None:
        sf_proc = subprocess.Popen([STOCKFISH_BIN], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        sf_proc.stdin.write("uci\nsetoption name Threads value 4\nsetoption name Hash value 128\nisready\n")
        sf_proc.stdin.flush()
        while True:
            line = sf_proc.stdout.readline()
            if "readyok" in line:
                break

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "tier": "Primary Tesla T4 GPU",
        "device": "NVIDIA Tesla T4 (16GB VRAM, Tensor Cores Active)",
        "lc0": os.path.exists(LC0_BIN),
        "weights": os.path.exists(BT4_WEIGHTS),
        "stockfish": os.path.exists(STOCKFISH_BIN),
        "time": time.time()
    }

@app.post("/evaluate")
def evaluate(req: EvalRequest):
    with lock:
        try:
            ensure_lc0()
            ensure_sf()

            # 1. Evaluate with Lc0 on Tesla T4 Tensor Cores
            lc0_proc.stdin.write(f"position fen {req.fen}\ngo nodes {req.nodes}\n")
            lc0_proc.stdin.flush()

            bestmove = None
            nps = 0
            score_cp = 0
            depth_reached = 0
            seldepth_reached = 0

            while True:
                line = lc0_proc.stdout.readline()
                if not line:
                    break
                if " nps " in line:
                    m = re.search(r'nps (\d+)', line)
                    if m: nps = int(m.group(1))
                    m2 = re.search(r'score cp (-?\d+)', line)
                    if m2: score_cp = int(m2.group(1))
                    m3 = re.search(r'depth (\d+)', line)
                    if m3: depth_reached = int(m3.group(1))
                    m4 = re.search(r'seldepth (\d+)', line)
                    if m4: seldepth_reached = int(m4.group(1))
                if line.startswith("bestmove"):
                    parts = line.strip().split()
                    bestmove = parts[1] if len(parts) > 1 else None
                    break

            # 2. Stockfish Oracle Anti-Blunder Verification
            sf_blunder = False
            sf_best = None
            if bestmove:
                sf_proc.stdin.write(f"position fen {req.fen}\ngo depth {req.oracle_depth}\n")
                sf_proc.stdin.flush()
                pos_score = 0
                while True:
                    sline = sf_proc.stdout.readline()
                    if not sline: break
                    if "score cp" in sline:
                        sm = re.search(r'score cp (-?\d+)', sline)
                        if sm: pos_score = int(sm.group(1))
                    if sline.startswith("bestmove"):
                        sf_best = sline.strip().split()[1]
                        break

                if sf_best and sf_best != bestmove:
                    # Check eval after candidate move
                    sf_proc.stdin.write(f"position fen {req.fen} moves {bestmove}\ngo depth {max(10, req.oracle_depth - 2)}\n")
                    sf_proc.stdin.flush()
                    after_score = 0
                    while True:
                        sline = sf_proc.stdout.readline()
                        if not sline: break
                        if "score cp" in sline:
                            sm = re.search(r'score cp (-?\d+)', sline)
                            if sm: after_score = -int(sm.group(1))
                        if sline.startswith("bestmove"):
                            break
                    eval_drop = pos_score - after_score
                    if eval_drop >= 65:
                        # Veto and adopt Stockfish's top move
                        bestmove = sf_best
                        sf_blunder = True

            return {
                "bestmove": bestmove,
                "nps": nps,
                "score_cp": score_cp,
                "depth": depth_reached,
                "seldepth": seldepth_reached,
                "oracle_veto": sf_blunder,
                "tier": "Tesla T4 GPU (Cloud Native)"
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
