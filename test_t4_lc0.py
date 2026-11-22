import subprocess

code = r'''
import subprocess, os

# Download LC0 release
print("Downloading Lc0 release for Linux...")
lc0_url = "https://github.com/LeelaChessZero/lc0/releases/download/v0.31.2/lc0-v0.31.2-linux-cudnn.tar.gz"
subprocess.run(f"curl -sL {lc0_url} | tar -xzf - -C /root/chess_bin", shell=True)
subprocess.run("chmod +x /root/chess_bin/lc0 || chmod +x /root/chess_bin/build/lc0", shell=True)

# Find lc0 binary
bin_path = subprocess.check_output("find /root/chess_bin -name lc0 -type f", shell=True).decode().strip()
print("Lc0 binary found at:", bin_path)

# Download BT4 network
print("Downloading BT4 network...")
bt4_url = "https://storage.lczero.org/files/networks-contrib/BT4-1024x15x32h-swa-6147500-policytune-332.pb.gz"
subprocess.run(f"wget -q -nc {bt4_url} -O /root/chess_bin/bt4.pb.gz", shell=True)
print("BT4 size:", os.path.getsize("/root/chess_bin/bt4.pb.gz"))

# Test run lc0
test_out = subprocess.check_output(f"echo 'uci\nquit' | {bin_path} | head -n 4", shell=True).decode()
print("Lc0 UCI output:\n", test_out)
'''

res = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine'], input=code, text=True, capture_output=True)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
