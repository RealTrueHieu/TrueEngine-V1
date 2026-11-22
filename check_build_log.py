import subprocess

code = '''
import subprocess, os
print("Processes:")
print(subprocess.check_output("ps aux | grep -v grep | grep -E 'ninja|c\\+\\+|nvcc' || echo 'NONE'", shell=True).decode())

lc0_exists = os.path.exists("/root/lc0/build/release/lc0")
print("LC0_EXISTS:", lc0_exists)
if lc0_exists:
    out = subprocess.check_output("ls -lh /root/lc0/build/release/lc0", shell=True).decode()
    print("Binary:", out.strip())
'''

res = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine', '--timeout', '20'], input=code, text=True, capture_output=True)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
