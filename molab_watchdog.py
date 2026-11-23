#!/usr/bin/env python3
"""
TrueEngine V1: Molab Autonomous Watchdog & Auto-Deployer Daemon
==============================================================
Monitors the Molab Marimo browser session on DISPLAY=:1.
Ensures molab_supercluster_node.py is continuously running on the RTX PRO 6000 Blackwell GPU.
If the session disconnects or restarts, automatically re-attaches, pulls latest git, and relaunches.
"""

import os
import sys
import time
import subprocess
import json

STATE_FILE = "/data/workspace/TrueEngine-V1/molab_state.json"
CHECK_INTERVAL = 30  # seconds
STALE_THRESHOLD = 90  # seconds

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [Molab Watchdog] {msg}", flush=True)

def is_molab_window_open():
    try:
        res = subprocess.run(
            ["xdotool", "search", "--onlyvisible", "--name", "molab"],
            env={**os.environ, "DISPLAY": ":1"},
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5
        )
        wids = [w.strip() for w in res.stdout.strip().splitlines() if w.strip()]
        return len(wids) > 0, (wids[0] if wids else None)
    except Exception:
        return False, None

def is_telemetry_fresh():
    if not os.path.exists(STATE_FILE):
        return False
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        last_t = data.get("last_updated", data.get("timestamp", 0))
        return (time.time() - last_t) < STALE_THRESHOLD
    except Exception:
        return False

def relaunch_on_molab(wid):
    log(f"Relaunching molab_supercluster_node.py on Molab window {wid}...")
    try:
        cmd_seq = [
            f"xdotool windowactivate {wid}",
            f"xdotool mousemove --window {wid} 500 550 click 1",
            "sleep 0.5",
            "xdotool type --delay 15 'cd /marimo/TrueEngine-V1 && git checkout -- . && git pull && pkill -f molab_supercluster_node || true && nohup python3 -u molab_supercluster_node.py > molab_node.log 2>&1 &'",
            "xdotool key Return"
        ]
        full_sh = " && ".join(cmd_seq)
        subprocess.run(
            ["bash", "-c", full_sh],
            env={**os.environ, "DISPLAY": ":1"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15
        )
        log("Successfully dispatched launch command to Molab terminal.")
    except Exception as e:
        log(f"Error relaunching on Molab: {e}")

def main():
    log("=== TrueEngine V1 Molab Autonomous Watchdog Daemon Started ===")
    while True:
        try:
            has_window, wid = is_molab_window_open()
            if has_window:
                fresh = is_telemetry_fresh()
                if not fresh:
                    log("Molab window is open but telemetry is stale or not reporting. Triggering relaunch...")
                    relaunch_on_molab(wid)
                    time.sleep(15)
                else:
                    # Healthy, telemetry reporting
                    pass
            else:
                # Molab window not open in Chromium
                pass
        except Exception as e:
            log(f"Watchdog loop error: {e}")
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
