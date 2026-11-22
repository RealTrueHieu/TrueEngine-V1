import subprocess

code = '''
import subprocess
print("Finding lc0 binary:")
print(subprocess.check_output("find /root -name 'lc0' -type f -executable 2>/dev/null || echo 'not found'", shell=True).decode())
print("Finding all lc0 files:")
print(subprocess.check_output("find /root/lc0/build -name 'lc0*' 2>/dev/null || echo 'none'", shell=True).decode())
'''
res = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine'], input=code, text=True, capture_output=True)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
