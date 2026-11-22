import subprocess

code = '''
import subprocess, time
subprocess.Popen("nohup ninja -C /root/lc0/build/release > /root/lc0_build.log 2>&1 &", shell=True)
time.sleep(2)
print("Started detached ninja. Log preview:")
print(subprocess.check_output("tail -n 10 /root/lc0_build.log || true", shell=True).decode())
'''

res = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine', '--timeout', '20'], input=code, text=True, capture_output=True)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
