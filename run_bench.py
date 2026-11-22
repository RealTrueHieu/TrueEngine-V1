import subprocess

script = '''
import subprocess
res = subprocess.run(["/root/lc0/build/release/lc0", "benchmark", "--weights=/root/chess_bin/bt4.pb.gz", "--backend=cuda-fp16", "--minibatch-size=256", "--threads=2", "--num-positions=2", "--movetime=2000"], capture_output=True, text=True)
print("BENCHMARK CODE:", res.returncode)
print("STDOUT:")
print(res.stdout)
print("STDERR:")
print(res.stderr)
'''

res = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine', '--timeout', '60'], input=script, text=True, capture_output=True)
print("OUT:")
print(res.stdout)
print("ERR:")
print(res.stderr)
