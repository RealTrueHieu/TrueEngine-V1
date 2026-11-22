import subprocess
import time
import re

code = r'''
import subprocess, time, os, re

# 1. Download cloudflared if not present
if not os.path.exists("/usr/local/bin/cloudflared"):
    print("Installing cloudflared...")
    subprocess.run("curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared", shell=True)

# 2. Kill old processes on port 8000 or old bridge
subprocess.run("pkill -f cloud_t4_engine_bridge || pkill -f uvicorn || pkill -f cloudflared", shell=True)
time.sleep(1)

# 3. Start FastAPI bridge server
print("Starting Cloud T4 FastAPI Bridge Server...")
bridge_proc = subprocess.Popen(["python3", "/root/cloud_t4_engine_bridge.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

# Wait 3s for uvicorn to bind
time.sleep(3)

# 4. Start cloudflared tunnel
print("Launching Cloudflare Tunnel for T4...")
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

# First upload cloud_t4_engine_bridge.py to /root/
with open(r"C:\Users\RealTrueHieu\CustomHumanChessEngine\cloud_t4_engine_bridge.py", "r", encoding="utf-8") as f:
    bridge_code = f.read()

upload_code = f'''
with open("/root/cloud_t4_engine_bridge.py", "w", encoding="utf-8") as f:
    f.write({repr(bridge_code)})
print("Uploaded bridge server code to /root/cloud_t4_engine_bridge.py")
'''

print("Uploading bridge code...")
subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine', '--timeout', '30'], input=upload_code, text=True)

print("Starting service and creating tunnel...")
res = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine', '--timeout', '60'], input=code, text=True, capture_output=True)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)

# Parse tunnel URL and write to cloud_config.json
for line in res.stdout.splitlines():
    if "TUNNEL_READY_URL:https" in line:
        url = line.split("TUNNEL_READY_URL:")[1].strip()
        print(f"SUCCESS: Extracted Cloud T4 Tunnel URL: {url}")
        cfg_path = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\config\cloud_config.json"
        import json
        cfg = {
            "cloud_enabled": True,
            "tunnel_url": url,
            "primary_device": "NVIDIA Tesla T4 (16GB VRAM, 320 Tensor Cores)",
            "fallback_device": "NVIDIA GeForce GTX 1660 Ti (Local CUDA FP16)",
            "auto_failover": True,
            "max_cloud_wait_sec": 4.0
        }
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        print(f"Updated {cfg_path} with active T4 URL!")
        break
