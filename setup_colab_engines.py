import os
import subprocess
import sys

print("=== INSTALLING CHESS ENGINES & PACKAGES ON COLAB T4 ===")

# Install stockfish and python-chess
res = subprocess.run(["apt-get", "update", "-qq"], capture_output=True, text=True)
res2 = subprocess.run(["apt-get", "install", "-y", "-qq", "stockfish"], capture_output=True, text=True)
print("[Apt] Stockfish install code:", res2.returncode)

res3 = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "python-chess"], capture_output=True, text=True)
print("[Pip] python-chess install code:", res3.returncode)

# Verify stockfish binary
stockfish_path = "/usr/games/stockfish"
if not os.path.exists(stockfish_path):
    stockfish_path = "/usr/bin/stockfish"

print(f"[Stockfish] Path: {stockfish_path} | Exists: {os.path.exists(stockfish_path)}")
if os.path.exists(stockfish_path):
    p = subprocess.Popen([stockfish_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    p.stdin.write("uci\nquit\n")
    p.stdin.flush()
    out = p.stdout.read()
    print("[Stockfish UCI Handshake]:\n", "\n".join(out.strip().split("\n")[:4]))
