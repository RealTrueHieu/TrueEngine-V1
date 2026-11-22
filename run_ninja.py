import subprocess

code = '''
import subprocess
p = subprocess.Popen("ninja -C /root/lc0/build/release", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
for i in range(30):
    line = p.stdout.readline()
    if not line: break
    print(line.strip())
'''
res = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine', '--timeout', '60'], input=code, text=True, capture_output=True)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
