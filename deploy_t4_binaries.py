import subprocess

code = r'''
import subprocess, os

print("Downloading Stockfish for Linux...")
subprocess.run("mkdir -p /root/chess_bin", shell=True)
sf_url = "https://github.com/official-stockfish/Stockfish/releases/download/sf_17/stockfish-ubuntu-x86-64-avx2.tar"
subprocess.run(f"curl -sL {sf_url} | tar xf - -C /root/chess_bin", shell=True)
subprocess.run("find /root/chess_bin -type f -name '*stockfish*' -exec mv {} /root/chess_bin/stockfish \;", shell=True)
subprocess.run("chmod +x /root/chess_bin/stockfish", shell=True)

# Test Stockfish
sf_res = subprocess.check_output("echo 'uci' | /root/chess_bin/stockfish | head -n 3", shell=True).decode()
print("Stockfish status:")
print(sf_res)

# Install lc0
print("Installing Lc0 / dependencies...")
subprocess.run("apt-get update -qq && apt-get install -y -qq lc0 curl wget > /dev/null", shell=True)
lc0_res = subprocess.check_output("which lc0 || echo 'not found'", shell=True).decode()
print("Lc0 path:", lc0_res.strip())

# Check pip packages
subprocess.run("pip install -q fastapi uvicorn python-chess", shell=True)
print("Environment ready!")
'''

res = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine'], input=code, text=True, capture_output=True)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
