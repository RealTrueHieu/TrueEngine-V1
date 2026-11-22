import subprocess

code = '''
import subprocess, os

# Check python version and apt packages
print("Testing apt update & install...")
cmd = "apt-get update -qq && apt-get install -y -qq stockfish python3-pip curl wget > /dev/null"
subprocess.run(cmd, shell=True)
print("Stockfish & tools installed!")

# Check stockfish
sf_ver = subprocess.check_output("stockfish --version || which stockfish", shell=True).decode()
print("Stockfish:", sf_ver.strip())

# Check pip packages
subprocess.run("pip install -q fastapi uvicorn chess python-chess", shell=True)
print("FastAPI & chess installed!")
'''

res = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine'], input=code, text=True, capture_output=True)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
