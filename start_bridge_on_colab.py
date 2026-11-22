import subprocess
import time
import re

SESSION = "chess-100m-cpu"

start_code = """
import subprocess, time, os, re

# Kill previous bridge & cloudflared if running
subprocess.run("pkill -f cloud_bridge_server", shell=True)
subprocess.run("pkill -f 'cloudflared tunnel'", shell=True)
time.sleep(1)

# 1. Start Python HTTP bridge server on port 8765
subprocess.Popen(
    ["python3", "-u", "/content/cloud_bridge_server.py"],
    stdout=open("/content/bridge_server.log", "w"),
    stderr=subprocess.STDOUT,
    start_new_session=True
)
time.sleep(1)

# 2. Start Cloudflared tunnel
cf_proc = subprocess.Popen(
    ["cloudflared", "tunnel", "--url", "http://127.0.0.1:8765"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    start_new_session=True
)

# Read stderr/stdout of cloudflared until trycloudflare.com URL appears
tunnel_url = None
start_t = time.time()
while time.time() - start_t < 25:
    line = cf_proc.stdout.readline()
    if not line:
        time.sleep(0.1)
        continue
    match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
    if match:
        tunnel_url = match.group(0)
        break

if tunnel_url:
    with open("/content/bridge_url.txt", "w") as f:
        f.write(tunnel_url.strip())
    print("TUNNEL_ONLINE:", tunnel_url)
else:
    print("TUNNEL_FAILED_TO_START")
"""

p = subprocess.Popen(["colab", "exec", "-s", SESSION, "--timeout", "35"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
out, _ = p.communicate(start_code)
print(out)
