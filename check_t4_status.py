import subprocess

script = '''
import os, subprocess
print("Checking status...")
print("lc0 exists:", os.path.exists("/root/lc0/build/release/lc0"))
if os.path.exists("/root/lc0/build/release/lc0"):
    res = subprocess.run(["/root/lc0/build/release/lc0", "--help"], capture_output=True, text=True)
    print("lc0 help head:")
    print(res.stdout[:300])
else:
    if os.path.exists("/root/lc0_build.log"):
        with open("/root/lc0_build.log") as f:
            lines = f.readlines()
        print("Last 10 lines of build log:")
        print("".join(lines[-10:]))
'''

res = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine'], input=script, text=True, capture_output=True)
print("STDOUT:")
print(res.stdout)
print("STDERR:")
print(res.stderr)
