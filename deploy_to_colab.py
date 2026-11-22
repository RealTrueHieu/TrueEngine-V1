import subprocess
import time
import os

SESSION = "chess-100m-t4"
LOCAL_SCRIPT = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\t4_100m_selfplay_streamer.py"

def run_colab(code, timeout=60):
    cmd = ["colab", "exec", "-s", SESSION, "--timeout", str(timeout)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out, _ = p.communicate(code)
    return out

if __name__ == "__main__":
    with open(LOCAL_SCRIPT, "r", encoding="utf-8") as f:
        script_content = f.read()

    print("Uploading streamer script to Colab session 'chess-100m-t4'...")
    # Transfer script to Colab file system
    upload_code = f"""
import os
with open('/content/t4_100m_selfplay_streamer.py', 'w', encoding='utf-8') as f:
    f.write({repr(script_content)})
print('Script uploaded successfully. Size:', os.path.getsize('/content/t4_100m_selfplay_streamer.py'), 'bytes')
"""
    res = run_colab(upload_code, timeout=60)
    print(res)

    print("Launching Massive 100M Streamer as background daemon...")
    launch_code = """
import subprocess, time, os

# Kill any existing streamer process if present
subprocess.run("pkill -f t4_100m_selfplay_streamer", shell=True)
time.sleep(1)

# Launch background daemon
proc = subprocess.Popen(
    ["python3", "-u", "/content/t4_100m_selfplay_streamer.py"],
    stdout=open("/content/streamer.log", "w"),
    stderr=subprocess.STDOUT,
    start_new_session=True
)
time.sleep(3)

# Verify process is running
res = subprocess.run("ps aux | grep t4_100m_selfplay_streamer", shell=True, capture_output=True, text=True)
print("Process Status:")
print(res.stdout)

# Check initial log
if os.path.exists("/content/streamer.log"):
    with open("/content/streamer.log", "r") as f:
        print("Initial log:\\n" + f.read())
"""
    launch_res = run_colab(launch_code, timeout=60)
    print(launch_res)
