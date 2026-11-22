import subprocess
import os
import sys
import time

SESSION = "chess-100m-t4"
PROJECT_DIR = r"C:\Users\RealTrueHieu\CustomHumanChessEngine"
STREAMER_PATH = os.path.join(PROJECT_DIR, "t4_100m_selfplay_streamer.py")
BRIDGE_PATH = os.path.join(PROJECT_DIR, "cloud_bridge_server.py")

print("=== DEPLOYING TO T4 GPU SESSION ===")

# 1. Symlink stockfish and check CUDA
setup_script = """
import os, subprocess, torch
if os.path.exists("/usr/games/stockfish") and not os.path.exists("/usr/local/bin/stockfish"):
    try:
        os.symlink("/usr/games/stockfish", "/usr/local/bin/stockfish")
    except Exception:
        pass

print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0), "| VRAM:", torch.cuda.get_device_properties(0).total_memory / (1024**3), "GB")

# Install cloudflared
if not os.path.exists("/usr/local/bin/cloudflared"):
    print("Installing cloudflared...")
    subprocess.run("curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared", shell=True)
print("Cloudflared installed:", os.path.exists("/usr/local/bin/cloudflared"))
"""

p = subprocess.Popen(["colab", "exec", "-s", SESSION, "--timeout", "60"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
out, _ = p.communicate(setup_script)
print(out)

# 2. Upload streamer script
print("Uploading t4_100m_selfplay_streamer.py...")
res = subprocess.run(["colab", "upload", "-s", SESSION, STREAMER_PATH, "/content/t4_100m_selfplay_streamer.py"], capture_output=True, text=True)
print("Upload streamer:", res.stdout.strip())

# 3. Upload bridge server
print("Uploading cloud_bridge_server.py...")
res = subprocess.run(["colab", "upload", "-s", SESSION, BRIDGE_PATH, "/content/cloud_bridge_server.py"], capture_output=True, text=True)
print("Upload bridge:", res.stdout.strip())

# 4. Launch streamer & bridge & cloudflared
launch_script = """
import subprocess, time, os

# Kill existing if any
subprocess.run("pkill -f t4_100m_selfplay_streamer", shell=True)
subprocess.run("pkill -f cloud_bridge_server", shell=True)
subprocess.run("pkill -f cloudflared", shell=True)
time.sleep(1)

# Launch bridge
p_bridge = subprocess.Popen(
    ["python3", "-u", "/content/cloud_bridge_server.py"],
    stdout=open("/content/bridge.log", "w"),
    stderr=subprocess.STDOUT,
    start_new_session=True
)

# Launch streamer on T4 GPU
p_streamer = subprocess.Popen(
    ["python3", "-u", "/content/t4_100m_selfplay_streamer.py"],
    stdout=open("/content/streamer.log", "w"),
    stderr=subprocess.STDOUT,
    start_new_session=True
)

# Launch cloudflared tunnel
p_cf = subprocess.Popen(
    ["cloudflared", "tunnel", "--url", "http://127.0.0.1:8765"],
    stdout=open("/content/tunnel.log", "w"),
    stderr=subprocess.STDOUT,
    start_new_session=True
)

time.sleep(3)
print("Streamer PID:", p_streamer.pid)
print("Bridge PID:", p_bridge.pid)
print("Cloudflared PID:", p_cf.pid)
"""

p = subprocess.Popen(["colab", "exec", "-s", SESSION, "--timeout", "30"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
out, _ = p.communicate(launch_script)
print(out)

time.sleep(4)
# 5. Extract tunnel URL
p = subprocess.Popen(["colab", "exec", "-s", SESSION, "--timeout", "15"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
out, _ = p.communicate("import os; print(open('/content/tunnel.log').read() if os.path.exists('/content/tunnel.log') else 'no log')")
print("=== TUNNEL OUTPUT ===")
for line in out.splitlines():
    if "trycloudflare.com" in line:
        print("NEW TUNNEL URL:", line.strip())
