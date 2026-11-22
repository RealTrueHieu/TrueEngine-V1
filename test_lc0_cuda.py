import subprocess

script = '''
import subprocess, os
os.chmod("/root/lc0/build/release/lc0", 0o755)
res = subprocess.run(["/root/lc0/build/release/lc0", "--help"], capture_output=True, text=True)
print("LC0_READY:", res.stdout.splitlines()[0] if res.stdout else "NO_STDOUT")

cmd = ["/root/lc0/build/release/lc0", "--weights=/root/chess_bin/bt4.pb.gz", "--backend=cuda"]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
p.stdin.write("uci\\nisready\\nposition startpos\\ngo nodes 200\\n")
p.stdin.flush()
output = []
for _ in range(35):
    line = p.stdout.readline()
    if not line: break
    output.append(line.strip())
    if "bestmove" in line: break

try:
    p.stdin.write("quit\\n")
    p.stdin.flush()
    p.terminate()
except Exception:
    pass

print("CUDA RUN RESULTS:")
for l in output:
    if any(k in l for k in ["info", "bestmove", "Initialized", "GPU", "CUDA", "Tesla"]):
        print("  ", l)
'''

res = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine'], input=script, text=True, capture_output=True)
print(res.stdout)
print(res.stderr)
