import subprocess
import time
import json
import os

SESSION = "chess-t4-engine"

code = r'''
import subprocess, os, time, sys

print("Linking Lc0 executable...")
res = subprocess.run("ninja -C /root/lc0/build/release lc0", shell=True, capture_output=True, text=True)
print("Ninja returncode:", res.returncode)
if os.path.exists("/root/lc0/build/release/lc0"):
    os.chmod("/root/lc0/build/release/lc0", 0o755)
    print("LC0_READY_OK")
else:
    print("FAILED:", res.stderr[-500:])
'''

print("Finishing Lc0 build...")
p = subprocess.run(['colab', 'exec', '-s', SESSION, '--timeout', '120'], input=code, text=True, capture_output=True)
print(p.stdout)
if p.stderr:
    print("STDERR:", p.stderr)

if "LC0_READY_OK" in p.stdout:
    # Upload and start bridge
    print("Uploading cloud_t4_engine_bridge.py...")
    with open(r"C:\Users\RealTrueHieu\CustomHumanChessEngine\cloud_t4_engine_bridge.py", "r", encoding="utf-8") as f:
        bridge_code = f.read()

    upload_code = f'''
with open("/root/cloud_t4_engine_bridge.py", "w", encoding="utf-8") as f:
    f.write({repr(bridge_code)})
print("UPLOAD_OK")
'''
    subprocess.run(['colab', 'exec', '-s', SESSION, '--timeout', '30'], input=upload_code, text=True)

    print("Starting bridge and Cloudflare Tunnel...")
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
    res = subprocess.run(['colab', 'exec', '-s', SESSION, '--timeout', '60'], input=launch_code, text=True, capture_output=True)
    print(res.stdout)

    new_url = None
    for line in res.stdout.splitlines():
        if "TUNNEL_READY_URL:https" in line:
            new_url = line.split("TUNNEL_READY_URL:")[1].strip()
            break

    if new_url:
        print(f"\n>>> ACTIVE TUNNEL URL: {new_url} <<<")
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
                print("Updated En Croissant engines.json with new Cloud URL!")
            except Exception as e:
                print("Could not update engines.json:", e)
