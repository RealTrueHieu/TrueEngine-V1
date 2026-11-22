import subprocess

SESSION = "chess-100m-t4"

setup_code = """
import subprocess
print("Installing python-chess and stockfish...")
subprocess.run(["pip", "install", "-q", "python-chess"], check=True)
subprocess.run(["apt-get", "update", "-qq"], check=True)
subprocess.run(["apt-get", "install", "-y", "-qq", "stockfish"], check=True)

import chess, chess.engine
print("python-chess version:", chess.__version__)
sf_proc = subprocess.run(["stockfish", "uci"], capture_output=True, text=True)
for line in sf_proc.stdout.splitlines()[:5]:
    print(line)
"""

cmd = ["colab", "exec", "-s", SESSION, "--timeout", "120"]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
out, _ = p.communicate(setup_code)
print(out)
