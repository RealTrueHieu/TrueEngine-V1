import subprocess

code = r'''
import subprocess, os, time

os.makedirs("/root/chess_bin", exist_ok=True)

# 1. Fast apt dependencies
print("1. Installing build dependencies...")
subprocess.run("apt-get update -qq && apt-get install -y -qq meson ninja-build libopenblas-dev zlib1g-dev stockfish curl > /dev/null 2>&1", shell=True)

# 2. Fast Python dependencies
print("2. Installing python packages...")
subprocess.run("pip install -q fastapi uvicorn python-chess", shell=True)

# 3. Cloudflared
print("3. Installing cloudflared...")
subprocess.run("curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared", shell=True)

# 4. Download BT4 network in background
print("4. Downloading BT4 network weights...")
bt4_url = "https://storage.lczero.org/files/networks-contrib/BT4-1024x15x32h-swa-6147500-policytune-332.pb.gz"
subprocess.Popen(["curl", "-sL", bt4_url, "-o", "/root/chess_bin/bt4.pb.gz"])

# 5. Build Lc0 (with -Dgtest=false for super fast compilation!)
print("5. Cloning and compiling Lc0 (skipping tests for max speed)...")
if not os.path.exists("/root/lc0"):
    subprocess.run("git clone --depth=1 --recurse-submodules https://github.com/LeelaChessZero/lc0.git /root/lc0", shell=True)

# Meson setup without tests
subprocess.run("meson setup /root/lc0/build/release /root/lc0 --buildtype=release -Dgtest=false", shell=True)
res = subprocess.run("ninja -C /root/lc0/build/release lc0", shell=True, capture_output=True, text=True)
print("Ninja returncode:", res.returncode)

if os.path.exists("/root/lc0/build/release/lc0"):
    os.chmod("/root/lc0/build/release/lc0", 0o755)
    print("SUCCESS: Lc0 binary is compiled and ready!")
else:
    print("FAILED: Lc0 compilation error:")
    print(res.stderr[-500:])
'''

print("Starting fast automated T4 build...")
res = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine', '--timeout', '300'], input=code, text=True)
print("Completed setup script.")
