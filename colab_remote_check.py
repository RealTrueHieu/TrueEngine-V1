import subprocess
import os
import sys

SESSION = "chess-100m-t4"

def run_colab(code, timeout=60):
    cmd = ["colab", "exec", "-s", SESSION, "--timeout", str(timeout)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out, _ = p.communicate(code)
    return out

if __name__ == "__main__":
    test_code = """
import os, psutil, shutil, torch
print("CPUs:", os.cpu_count())
total, used, free = shutil.disk_usage("/")
print("Disk Free:", free // (1024**3), "GB of", total // (1024**3), "GB")
print("RAM:", psutil.virtual_memory().total // (1024**3), "GB")
print("GPU:", torch.cuda.get_device_name(0), "| VRAM:", torch.cuda.get_device_properties(0).total_memory // (1024**2), "MB")
"""
    res = run_colab(test_code)
    print(res)
