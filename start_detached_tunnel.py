import subprocess
import time
import os
import re
import json

SESSION = "chess-t4-engine"

daemon_code = r'''
import subprocess, time, os, re

# Kill previous
subprocess.run("pkill -9 -f cloud_t4_engine_bridge || true", shell=True)
subprocess.run("pkill -9 -f cloudflared || true", shell=True)
time.sleep(1)

# 1. Launch FastAPI as detached background process
with open("/root/bridge_out.log", "w") as out:
    subprocess.Popen(
        ["python3", "-u", "/root/cloud_t4_engine_bridge.py"],
        stdout=out,
        stderr=subprocess.STDOUT,
        start_new_session=True
    )

time.sleep(3)

# 2. Launch cloudflared tunnel as detached background process
cf_log = open("/root/cloudflared.log", "w")
cf_proc = subprocess.Popen(
    ["/usr/local/bin/cloudflared", "tunnel", "--url", "http://127.0.0.1:8000", "--no-autoupdate"],
    stdout=cf_log,
    stderr=subprocess.STDOUT,
    start_new_session=True
)

# 3. Read cloudflared.log until tunnel URL is written
tunnel_url = None
start_t = time.time()
while time.time() - start_t < 25:
    time.sleep(0.5)
    if os.path.exists("/root/cloudflared.log"):
        with open("/root/cloudflared.log", "r") as f:
            content = f.read()
        m = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', content)
        if m:
            tunnel_url = m.group(0)
            break

print(f"DAEMON_TUNNEL_URL:{tunnel_url}")
'''

p = subprocess.run(['colab', 'exec', '-s', SESSION, '--timeout', '40'], input=daemon_code, text=True, capture_output=True)
print(p.stdout)
if p.stderr:
    print("STDERR:", p.stderr)

new_url = None
for line in p.stdout.splitlines():
    if "DAEMON_TUNNEL_URL:https" in line:
        new_url = line.split("DAEMON_TUNNEL_URL:")[1].strip()
        break

if new_url:
    print(f"\n>>> ACTIVE DETACHED TUNNEL: {new_url} <<<")
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
            print("Updated En Croissant engines.json!")
        except Exception as e:
            print("Error updating engines.json:", e)
