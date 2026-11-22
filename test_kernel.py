import subprocess

code = '''
print("KERNEL_ALIVE_TEST")
'''
res = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine', '--timeout', '15'], input=code, text=True, capture_output=True)
print("STDOUT:", res.stdout)
if res.stderr:
    print("STDERR:", res.stderr)
