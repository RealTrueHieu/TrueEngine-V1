import subprocess

SESSION = "chess-100m-cpu"

setup_code = """
import os, subprocess, time

print("Setting up Cloudflared tunnel...")
if not os.path.exists("/usr/local/bin/cloudflared"):
    subprocess.run("wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared", shell=True, check=True)

res = subprocess.run(["cloudflared", "--version"], capture_output=True, text=True)
print("Cloudflared version:", res.stdout.strip())
"""

p = subprocess.Popen(["colab", "exec", "-s", SESSION, "--timeout", "60"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
out, _ = p.communicate(setup_code)
print(out)
