import subprocess
import os
import time

SESSION = "chess-100m-cpu"
LOCAL_SCRIPT = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\t4_100m_selfplay_streamer.py"

with open(LOCAL_SCRIPT, "r", encoding="utf-8") as f:
    script_content = f.read()

print("Uploading streamer script to Colab CPU session...")
upload_code = f"""
import os
with open('/content/t4_100m_selfplay_streamer.py', 'w', encoding='utf-8') as f:
    f.write({repr(script_content)})
print('Uploaded. Size:', os.path.getsize('/content/t4_100m_selfplay_streamer.py'))
"""

p = subprocess.Popen(["colab", "exec", "-s", SESSION, "--timeout", "30"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
out, _ = p.communicate(upload_code)
print(out)

print("Launching streamer on CPU...")
launch_code = """
import subprocess, time
subprocess.run("pkill -f t4_100m_selfplay_streamer", shell=True)
time.sleep(1)
subprocess.Popen(
    ["python3", "-u", "/content/t4_100m_selfplay_streamer.py"],
    stdout=open("/content/streamer.log", "w"),
    stderr=subprocess.STDOUT,
    start_new_session=True
)
time.sleep(2)
res = subprocess.run("ps aux | grep t4_100m_selfplay_streamer", shell=True, capture_output=True, text=True)
print("Process status:")
print(res.stdout)
"""

p = subprocess.Popen(["colab", "exec", "-s", SESSION, "--timeout", "30"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
out2, _ = p.communicate(launch_code)
print(out2)
