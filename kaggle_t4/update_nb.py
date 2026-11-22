import json

nb_path = r'C:\Users\RealTrueHieu\CustomHumanChessEngine\kaggle_t4\trueengine_dual_t4.ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

cell_4_code = '''# 4. Launch Bridge, Start Tunnel, and Notify Local Engine via Webhook!
import subprocess, time, os, re, requests

!pkill -9 -f cloud_t4_engine_bridge || true
!pkill -9 -f cloudflared || true
time.sleep(1)

print("Starting FastAPI server on port 8000...", flush=True)
subprocess.Popen(["python3", "-u", "/root/cloud_t4_engine_bridge.py"], stdout=open("/root/bridge.log", "w"), stderr=subprocess.STDOUT, start_new_session=True)
time.sleep(3)

# Test local health check
try:
    res = requests.get("http://127.0.0.1:8000/health", timeout=5)
    print("FastAPI bridge local status:", res.status_code, res.json(), flush=True)
except Exception as e:
    print("Bridge test warning:", e, flush=True)

print("Launching Cloudflare Tunnel...", flush=True)
cf_log_path = "/root/cloudflared.log"
cf_log = open(cf_log_path, "w")
cf_proc = subprocess.Popen(["/usr/local/bin/cloudflared", "tunnel", "--url", "http://127.0.0.1:8000", "--no-autoupdate"], stdout=cf_log, stderr=subprocess.STDOUT, start_new_session=True)

tunnel_url = None
start_t = time.time()
while time.time() - start_t < 45:
    time.sleep(1)
    if os.path.exists(cf_log_path):
        with open(cf_log_path, "r", errors="ignore") as f:
            content = f.read()
        m = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', content)
        if m:
            tunnel_url = m.group(0)
            break

print("\\n=======================================================", flush=True)
if tunnel_url:
    print(f"🔥 KAGGLE DUAL-T4 TUNNEL ONLINE: {tunnel_url}", flush=True)
    with open("/kaggle/working/tunnel_url.txt", "w") as f:
        f.write(tunnel_url)
    try:
        requests.post("https://ntfy.sh/trueengine_t4_hieu", data=tunnel_url.encode(), timeout=5)
        print("✅ Broadcasted tunnel URL to local engine!", flush=True)
    except Exception as e:
        print("Webhook notice warning:", e, flush=True)
else:
    print("⚠️ Cloudflare tunnel URL not found! Check log below:", flush=True)
    if os.path.exists(cf_log_path):
        with open(cf_log_path, "r", errors="ignore") as f:
            print(f.read(), flush=True)
print("=======================================================", flush=True)

# Keep the Dual-T4 session alive to serve inference
print("\\n🚀 Supercomputing cluster ready! Serving inference requests...", flush=True)
while True:
    time.sleep(30)
'''

lines = [line + '\n' for line in cell_4_code.split('\n')[:-1]] + [cell_4_code.split('\n')[-1]]
nb['cells'][4]['source'] = lines

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print('Notebook successfully updated!')
