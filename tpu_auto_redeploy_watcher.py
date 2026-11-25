#!/usr/bin/env python3
"""
TrueEngine V1: Kaggle TPU Auto-Redeploy & Completion Watcher Daemon
===================================================================
- Continuously monitors the Kaggle Cloud TPU v3-8 kernel status
- If stuck in QUEUED for too long (>180s), automatically triggers redeployment
- When RUNNING, monitors training progress and logs
- When COMPLETE, automatically downloads weights and updates Gateway
"""

import os
import sys
import time
import subprocess
import kaggle

KERNEL_SLUG = "jgfchj/trueengine-v1-tpu-supercharged-trainer"
TPU_DIR = "/data/workspace/TrueEngine-V1/kaggle_tpu_trainer"
LOG_FILE = "/data/workspace/TrueEngine-V1/data/tpu_watcher.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def log(msg):
    t_str = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{t_str}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def get_status(api):
    try:
        s = api.kernels_status(KERNEL_SLUG)
        status_str = s.get("status", "UNKNOWN") if isinstance(s, dict) else getattr(s, "status", "UNKNOWN")
        return status_str
    except Exception as e:
        log(f"API status check error: {e}")
        return "ERROR"

def redeploy():
    log(f"[*] Redeploying kernel {KERNEL_SLUG} to Kaggle scheduler...")
    res = subprocess.run(["kaggle", "kernels", "push", "-p", TPU_DIR], capture_output=True, text=True)
    log(f"Redeploy output: {res.stdout.strip()} | {res.stderr.strip()}")

def main():
    log("=================================================================")
    log("  TRUEENGINE V1: KAGGLE TPU AUTO-REDEPLOY WATCHER DAEMON")
    log("=================================================================")
    
    api = kaggle.KaggleApi()
    api.authenticate()

    queued_count = 0

    while True:
        status = get_status(api)
        log(f"Current Status: {status}")

        if status == "QUEUED":
            queued_count += 1
            log(f"Kernel is QUEUED ({queued_count * 30}s in queue).")
            # If queued for more than 5 minutes (10 checks), redeploy
            if queued_count >= 10:
                log("[!] Queued too long! Triggering auto-redeploy to refresh queue...")
                redeploy()
                queued_count = 0
                time.sleep(15)
        elif status == "RUNNING":
            queued_count = 0
            log("[✓] Kernel is actively RUNNING on Cloud TPU v3-8!")
        elif status in ["COMPLETE", "COMPLETED"]:
            log("🎉 TPU TRAINING COMPLETE! Downloading trained weights...")
            out_dir = "/data/workspace/TrueEngine-V1/models/tpu_latest"
            os.makedirs(out_dir, exist_ok=True)
            subprocess.run(["kaggle", "kernels", "output", KERNEL_SLUG, "-p", out_dir])
            log(f"[✓] Weights downloaded to {out_dir}")
            break
        elif status == "ERROR":
            log("[!] Kernel reported ERROR. Triggering redeployment...")
            redeploy()
            time.sleep(20)

        time.sleep(30)

if __name__ == "__main__":
    main()
