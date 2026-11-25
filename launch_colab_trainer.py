import subprocess
import sys
import os

print("[Launcher] Starting TrueEngine V1 massive training on Tesla T4 GPU...")
log_file = open("/content/train.log", "w", encoding="utf-8")
p = subprocess.Popen(
    [sys.executable, "-u", "/content/colab_massive_trainer.py"],
    stdout=log_file,
    stderr=subprocess.STDOUT,
    cwd="/content"
)
print(f"[Launcher] Training process started with PID: {p.pid}")
with open("/content/train_pid.txt", "w") as f:
    f.write(str(p.pid))
print("[Launcher] Monitor training progress with /content/train.log")
