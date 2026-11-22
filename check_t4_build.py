import subprocess

code = '''
import os, subprocess
print("chess_bin:", os.listdir("/root/chess_bin") if os.path.exists("/root/chess_bin") else "none")
print("lc0 binary exists:", os.path.exists("/root/lc0/build/release/lc0"))
try:
    ps = subprocess.check_output("ps aux | grep -E 'ninja|meson|curl|python'", shell=True).decode()
    print("Processes:\n", ps)
except Exception as e:
    print("PS error:", e)
'''

p = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine'], input=code, text=True, capture_output=True)
print(p.stdout)
if p.stderr:
    print("STDERR:", p.stderr)
