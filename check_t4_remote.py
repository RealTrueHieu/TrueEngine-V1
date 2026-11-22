import subprocess

code = '''
import subprocess
out = subprocess.check_output('nvidia-smi', shell=True).decode()
print(out)
'''

res = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine'], input=code, text=True, capture_output=True)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
