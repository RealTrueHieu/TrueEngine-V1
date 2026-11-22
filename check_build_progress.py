import subprocess

code = '''
import subprocess, os
print("Checking lc0 binary...")
out = subprocess.check_output("ls -la /root/lc0/build/release/lc0 2>/dev/null || echo 'NOT_YET'", shell=True).decode()
print("Binary check:", out.strip())

# Check running processes
ps = subprocess.check_output("ps aux | grep -E 'ninja|meson|build' | grep -v grep || echo 'NO_BUILD_RUNNING'", shell=True).decode()
print("Processes:\n", ps.strip())
'''

res = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine', '--timeout', '60'], input=code, text=True, capture_output=True)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
