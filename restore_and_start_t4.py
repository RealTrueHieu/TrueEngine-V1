import subprocess
import time
import os
import re
import json

SESSION = "chess-t4-engine"

setup_code = r'''
import subprocess, os, time, sys

os.makedirs("/root/chess_bin/stockfish", exist_ok=True)

# 1. Apt dependencies
print("1. Installing apt packages...")
subprocess.run("apt-get update -qq && apt-get install -y -qq meson ninja-build libopenblas-dev zlib1g-dev stockfish curl git > /dev/null 2>&1", shell=True)

# Symlink stockfish
subprocess.run("ln -sf /usr/games/stockfish /root/chess_bin/stockfish/stockfish-ubuntu-x86-64-avx2", shell=True)
subprocess.run("chmod +x /root/chess_bin/stockfish/stockfish-ubuntu-x86-64-avx2", shell=True)
print("Stockfish ready:", os.path.exists("/root/chess_bin/stockfish/stockfish-ubuntu-x86-64-avx2"))

# 2. Python packages
print("2. Installing python packages...")
subprocess.run("pip install -q fastapi uvicorn python-chess", shell=True)

# 3. Cloudflared
print("3. Installing cloudflared...")
if not os.path.exists("/usr/local/bin/cloudflared"):
    subprocess.run("curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared", shell=True)
print("Cloudflared ready:", os.path.exists("/usr/local/bin/cloudflared"))

# 4. Download BT4 weights in background
print("4. Starting BT4 network download...")
bt4_url = "https://storage.lczero.org/files/networks-contrib/BT4-1024x15x32h-swa-6147500-policytune-332.pb.gz"
subprocess.Popen(["curl", "-sL", bt4_url, "-o", "/root/chess_bin/bt4.pb.gz"])

# 5. Build Lc0
print("5. Cloning and building Lc0...")
if not os.path.exists("/root/lc0"):
    subprocess.run("git clone --depth=1 --recurse-submodules https://github.com/LeelaChessZero/lc0.git /root/lc0", shell=True)

subprocess.run("meson setup /root/lc0/build/release /root/lc0 --buildtype=release -Dgtest=false", shell=True)
res = subprocess.run("ninja -C /root/lc0/build/release lc0", shell=True, capture_output=True, text=True)
if os.path.exists("/root/lc0/build/release/lc0"):
    print("Lc0 compilation SUCCESS!")
else:
    print("Lc0 compilation FAILED:", res.stderr[-500:])

# Wait for BT4 to finish downloading if not done
while not os.path.exists("/root/chess_bin/bt4.pb.gz") or os.path.getsize("/root/chess_bin/bt4.pb.gz") < 100000000:
    print(f"Waiting for BT4 weights... ({os.path.getsize('/root/chess_bin/bt4.pb.gz') if os.path.exists('/root/chess_bin/bt4.pb.gz') else 0} bytes)")
    time.sleep(3)

print("BT4 size:", os.path.getsize("/root/chess_bin/bt4.pb.gz"))
print("SETUP_ALL_DONE")
'''

print("[1/3] Running fast setup on Colab T4...")
p = subprocess.run(['colab', 'exec', '-s', SESSION, '--timeout', '400'], input=setup_code, text=True, capture_output=True)
print(p.stdout)
if p.stderr:
    print("STDERR:", p.stderr)

if "Lc0 compilation SUCCESS!" not in p.stdout:
    print("Setup did not succeed, aborting.")
    sys.exit(1)

# [2/3] Upload bridge server
print("[2/3] Uploading bridge server...")
with open(r"C:\Users\RealTrueHieu\CustomHumanChessEngine\cloud_t4_engine_bridge.py", "r", encoding="utf-8") as f:
    bridge_code = f.read()

upload_code = f'''
with open("/root/cloud_t4_engine_bridge.py", "w", encoding="utf-8") as f:
    f.write({repr(bridge_code)})
print("UPLOAD_OK")
'''
subprocess.run(['colab', 'exec', '-s', SESSION, '--timeout', '30'], input=upload_code, text=True)

# [3/3] Start FastAPI & Cloudflared
launch_code = r'''
import subprocess, time, os, re

subprocess.run("pkill -f cloud_t4_engine_bridge || pkill -f uvicorn || pkill -f cloudflared", shell=True)
time.sleep(1)

# Start FastAPI
subprocess.Popen(["python3", "/root/cloud_t4_engine_bridge.py"], stdout=open("/root/bridge.log", "w"), stderr=subprocess.STDOUT)
time.sleep(3)

# Start Cloudflared tunnel
cf_proc = subprocess.Popen(["/usr/local/bin/cloudflared", "tunnel", "--url", "http://localhost:8000", "--no-autoupdate"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

tunnel_url = None
start_t = time.time()
while time.time() - start_t < 25:
    line = cf_proc.stdout.readline()
    if not line:
        time.sleep(0.5)
        continue
    m = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
    if m:
        tunnel_url = m.group(0)
        break

print(f"TUNNEL_READY_URL:{tunnel_url}")
'''

print("[3/3] Starting bridge & tunnel...")
res = subprocess.run(['colab', 'exec', '-s', SESSION, '--timeout', '60'], input=launch_code, text=True, capture_output=True)
print(res.stdout)

new_url = None
for line in res.stdout.splitlines():
    if "TUNNEL_READY_URL:https" in line:
        new_url = line.split("TUNNEL_READY_URL:")[1].strip()
        break

if new_url:
    print(f"\n>>> NEW ACTIVE TUNNEL URL: {new_url} <<<")
    cfg_path = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\config\cloud_config.json"
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump({
            "cloud_enabled": True,
            "tunnel_url": new_url,
            "primary_device": "NVIDIA Tesla T4 (16GB VRAM, 320 Tensor Cores)",
            "fallback_device": "NVIDIA GeForce GTX 1660 Ti (Local CUDA FP16)",
            "auto_failover": True,
            "max_cloud_wait_sec": 10.0
        }, f, indent=4)
    print(f"Updated {cfg_path}")
    
    # Also update En Croissant engines.json
    enc_path = r"C:\Users\RealTrueHieu\AppData\Roaming\org.encroissant.app\engines.json"
    if os.path.exists(enc_path):
        try:
            with open(enc_path, "r", encoding="utf-8") as f:
                enc_data = json.load(f)
            for eng in enc_data:
                if "Cloud" in eng.get("name", ""):
                    for opt in eng.get("options", []):
                        if opt.get("name") == "CloudTunnelURL":
                            opt["value"] = new_url
            with open(enc_path, "w", encoding="utf-8") as f:
                json.dump(enc_data, f, indent=2)
            print("Updated En Croissant engines.json with new Cloud URL!")
        except Exception as e:
            print("Could not update engines.json:", e)
else:
    print("FAILED to obtain tunnel URL.")
