import subprocess

code = '''
with open("/root/cloudflared.log", "r") as f:
    print(f.read())
'''
p = subprocess.run(['colab', 'exec', '-s', 'chess-t4-engine'], input=code, text=True, capture_output=True)
print(p.stdout)
if p.stderr:
    print("STDERR:", p.stderr)
