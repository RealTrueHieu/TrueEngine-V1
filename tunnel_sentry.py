#!/usr/bin/env python3
"""
TrueEngine V1: Autonomous Cloudflare Tunnel Discovery & Hot-Swap Sentry
========================================================================
- Automatically listens to ntfy.sh/trueengine_t4_hieu webhook broadcasts.
- When Kaggle deploys and releases a new Cloudflare Tunnel URL:
  1. Validates /health on the newly announced URL.
  2. Automatically updates engine_config.json (hot-swap).
  3. Notifies tournament runner and sync server immediately.
"""

import os
import sys
import time
import json
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "engine_config.json")
NTFY_TOPIC = "https://ntfy.sh/trueengine_t4_hieu/json?poll=1"
LOG_FILE = os.path.join(SCRIPT_DIR, "tunnel_sentry.log")

def log(msg):
    ts = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{ts} {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def get_current_url():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("cloud_backend_url")
        except Exception:
            pass
    return None

def set_current_url(new_url):
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    cfg["cloud_backend_url"] = new_url
    cfg["last_updated"] = time.time()
    cfg["last_updated_iso"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    
    tmp_path = CONFIG_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp_path, CONFIG_PATH)
    log(f"🔄 [HOT-SWAP] Automatically updated engine_config.json -> {new_url}")

def check_health(url):
    try:
        r = requests.get(f"{url}/health", timeout=2.5)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "healthy":
                return True, data
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)

def run_sentry_loop():
    log("=" * 65)
    log("  🚀 TRUEENGINE V1: AUTONOMOUS TUNNEL SENTRY ACTIVE")
    log("=" * 65)

    current_active = get_current_url()
    log(f"Initial configured tunnel: {current_active or 'None'}")

    while True:
        try:
            # 1. First test if currently configured tunnel is healthy
            current_active = get_current_url()
            current_healthy = False
            if current_active:
                healthy, info = check_health(current_active)
                if healthy:
                    current_healthy = True

            # 2. Poll ntfy.sh for latest announcements from Kaggle
            r = requests.get(NTFY_TOPIC, timeout=5)
            if r.status_code == 200:
                urls = []
                for line in r.text.strip().split("\n"):
                    if line.strip():
                        try:
                            d = json.loads(line)
                            msg = d.get("message", "")
                            if msg.startswith("https://") and "trycloudflare.com" in msg:
                                urls.append(msg)
                        except Exception:
                            pass

                # Scan from newest to oldest
                for cand in reversed(urls):
                    healthy, info = check_health(cand)
                    if healthy:
                        if cand != current_active:
                            log(f"✨ Found NEW verified Kaggle Dual-T4 Tunnel: {cand}")
                            set_current_url(cand)
                            current_active = cand
                            current_healthy = True
                        break

            if not current_healthy:
                log("⏳ [WAITING] No healthy Kaggle tunnel responding yet. Retrying in 5s...")

        except Exception as e:
            log(f"⚠️ Sentry poll error: {e}")

        time.sleep(5)

if __name__ == "__main__":
    run_sentry_loop()
