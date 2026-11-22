import subprocess

code = r'''
import subprocess, os

print("Installing build dependencies...")
subprocess.run("apt-get update -qq && apt-get install -y -qq meson ninja-build libopenblas-dev zlib1g-dev > /dev/null", shell=True)

print("Checking if lc0 exists...")
if not os.path.exists("/root/lc0/build/release/lc0"):
    print("Cloning lc0...")
    subprocess.run("git clone --depth=1 --recurse-submodules https://github.com/LeelaChessZero/lc0.git /root/lc0", shell=True)
    print("Building lc0...")
    res = subprocess.run("cd /root/lc0 && ./build.sh", shell=True, capture_output=True, text=True)
    print("Build stdout:", res.stdout[-400:] if res.stdout else "")
    print("Build stderr:", res.stderr[-400:] if res.stderr else "")

if os.path.exists("/root/lc0/build/release/lc0"):
    print("LC0 BUILT SUCCESSFULLY!")
    out = subprocess.check_output("echo 'uci\nquit' | /root/lc0/build/release/lc0", shell=True).decode()
    print("Lc0 output:\n", out[:300])
else:
    print("Lc0 binary not found at /root/lc0/build/release/lc0")
'''

res = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine'], input=code, text=True, capture_output=True)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
