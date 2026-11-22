import subprocess

SESSION = "chess-100m-cpu"

setup_code = """
import subprocess
print("Installing python-chess...")
subprocess.run(["pip", "install", "-q", "python-chess"])
import chess
print("CHESS_OK:", chess.__version__)
"""

p = subprocess.Popen(["colab", "exec", "-s", SESSION, "--timeout", "30"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
out, _ = p.communicate(setup_code)
print(out)
