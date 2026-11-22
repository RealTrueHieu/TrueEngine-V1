import subprocess
import time
import json
import os
import sys

ACTIVE_SESSION = "chess-100m-cpu"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(SCRIPT_DIR, "books")):
    PROJECT_DIR = SCRIPT_DIR
elif os.path.exists(r"C:\Users\RealTrueHieu\CustomHumanChessEngine"):
    PROJECT_DIR = r"C:\Users\RealTrueHieu\CustomHumanChessEngine"
else:
    PROJECT_DIR = SCRIPT_DIR
LOCAL_MEMORY = os.path.join(PROJECT_DIR, "books", "experience_memory.json")
LOCAL_MODELS_DIR = os.path.join(PROJECT_DIR, "models")
LOG_FILE = os.path.join(PROJECT_DIR, "auto_distill.log")
TEMP_DISTILLED = os.path.join(PROJECT_DIR, "books", "colab_downloaded_distilled.json")
TEMP_METRICS = os.path.join(PROJECT_DIR, "books", "colab_downloaded_metrics.json")
LOCAL_STREAMER_SCRIPT = os.path.join(PROJECT_DIR, "t4_100m_selfplay_streamer.py")

os.makedirs(os.path.dirname(LOCAL_MEMORY), exist_ok=True)
os.makedirs(LOCAL_MODELS_DIR, exist_ok=True)

consecutive_failures = 0

def log(msg):
    ts = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{ts} {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

import shutil

COLAB_BIN = shutil.which("colab") or os.path.expanduser("~/.local/bin/colab") or "colab"

def download_file(remote_path, local_path):
    global ACTIVE_SESSION
    cmd = [COLAB_BIN, "download", "-s", ACTIVE_SESSION, remote_path, local_path]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return res.returncode == 0 and os.path.exists(local_path)
    except Exception:
        return False

def check_session_responsive(session_name):
    cmd = [COLAB_BIN, "exec", "-s", session_name, "--timeout", "10"]
    try:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, _ = p.communicate("import os; print('SESSION_HEALTHY')")
        return "SESSION_HEALTHY" in out
    except Exception:
        return False

def failover_to_cpu():
    global ACTIVE_SESSION
    log("[Watchdog Failover] Detected T4 GPU quota exhaustion or disconnection! Initiating auto-failover to Colab CPU...")
    cpu_session = "chess-100m-cpu"
    
    # 1. Create or check CPU session
    log("[Watchdog Failover] Creating CPU session 'chess-100m-cpu'...")
    subprocess.run([COLAB_BIN, "new", "--session", cpu_session], capture_output=True, text=True)
    
    # 2. Setup dependencies on CPU session
    log("[Watchdog Failover] Installing python-chess & stockfish on CPU...")
    setup_code = """
import subprocess
subprocess.run(["pip", "install", "-q", "python-chess"], check=True)
subprocess.run(["apt-get", "update", "-qq"], check=True)
subprocess.run(["apt-get", "install", "-y", "-qq", "stockfish"], check=True)
"""
    try:
        p = subprocess.Popen([COLAB_BIN, "exec", "-s", cpu_session, "--timeout", "90"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        p.communicate(setup_code)
    except Exception as e:
        log(f"[Watchdog Failover Warning] Setup warning: {e}")

    # 3. Upload universal streamer script
    log("[Watchdog Failover] Uploading universal CPU streamer script...")
    with open(LOCAL_STREAMER_SCRIPT, "r", encoding="utf-8") as f:
        script_content = f.read()
    upload_code = f"""
with open('/content/t4_100m_selfplay_streamer.py', 'w', encoding='utf-8') as f:
    f.write({repr(script_content)})
"""
    try:
        p = subprocess.Popen([COLAB_BIN, "exec", "-s", cpu_session, "--timeout", "60"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        p.communicate(upload_code)
    except Exception as e:
        log(f"[Watchdog Failover Warning] Upload warning: {e}")

    # 4. Launch streamer on CPU runtime
    log("[Watchdog Failover] Launching multi-threaded CPU self-play streamer daemon...")
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
"""
    try:
        p = subprocess.Popen([COLAB_BIN, "exec", "-s", cpu_session, "--timeout", "30"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        p.communicate(launch_code)
    except Exception as e:
        log(f"[Watchdog Failover Warning] Launch warning: {e}")

    ACTIVE_SESSION = cpu_session
    log("[Watchdog Failover Complete] Successfully switched active session to 'chess-100m-cpu'! Self-play continuing on CPU.")

def merge_distilled_experience(distilled_data):
    """Performs continuous distillation: updates Q-values, amplifies wins, filters blunders."""
    if os.path.exists(LOCAL_MEMORY):
        try:
            with open(LOCAL_MEMORY, "r", encoding="utf-8") as f:
                local_mem = json.load(f)
        except Exception:
            local_mem = {}
    else:
        local_mem = {}

    added_positions = 0
    updated_moves = 0
    amplified_lines = 0
    blunders_caught = 0

    for epd, moves in distilled_data.items():
        if epd not in local_mem:
            local_mem[epd] = {}
            added_positions += 1

        for uci_move, stats in moves.items():
            visits = stats.get("visits", 1)
            wins = stats.get("wins", 0)
            losses = stats.get("losses", 0)
            remote_mult = stats.get("multiplier", 1.0)
            
            # Distillation calculation
            win_rate = wins / max(1, visits)
            is_blunder = (losses >= 3 and win_rate < 0.20) or remote_mult < 0.1

            if uci_move not in local_mem[epd]:
                mult = 0.001 if is_blunder else (min(3.5, 1.0 + win_rate * 2.0) if win_rate > 0.55 else 1.0)
                local_mem[epd][uci_move] = {
                    "visits": visits,
                    "wins": wins,
                    "draws": max(0, visits - wins - losses),
                    "losses": losses,
                    "q_val": round((wins - losses) / max(1, visits), 3),
                    "multiplier": round(mult, 3),
                    "blunder": is_blunder,
                    "last_updated": int(time.time())
                }
                updated_moves += 1
            else:
                entry = local_mem[epd][uci_move]
                entry["visits"] += visits
                entry["wins"] += wins
                entry["losses"] += losses
                total_vis = entry["visits"]
                total_wr = entry["wins"] / max(1, total_vis)
                entry["q_val"] = round((entry["wins"] - entry["losses"]) / max(1, total_vis), 3)

                if is_blunder or (entry["losses"] >= 3 and total_wr < 0.20):
                    entry["blunder"] = True
                    entry["multiplier"] = 0.001
                    blunders_caught += 1
                elif total_wr > 0.55:
                    entry["multiplier"] = min(3.5, round(entry.get("multiplier", 1.0) * 1.1, 3))
                    amplified_lines += 1

                entry["last_updated"] = int(time.time())
                updated_moves += 1

    # Atomic write to avoid file-lock conflicts with En Croissant
    temp_mem = LOCAL_MEMORY + ".tmp"
    with open(temp_mem, "w", encoding="utf-8") as f:
        json.dump(local_mem, f, indent=2)
    if os.path.exists(LOCAL_MEMORY):
        os.replace(temp_mem, LOCAL_MEMORY)
    else:
        os.rename(temp_mem, LOCAL_MEMORY)

    return len(local_mem), added_positions, updated_moves, amplified_lines, blunders_caught

def run_auto_distill_cycle():
    global consecutive_failures
    # 1. Download distilled experience
    download_ok = download_file("/content/colab_distilled_experience.json", TEMP_DISTILLED)
    if download_ok:
        consecutive_failures = 0
        try:
            with open(TEMP_DISTILLED, "r", encoding="utf-8") as f:
                distilled = json.load(f)
            if distilled:
                tot, added, updated, amp, blund = merge_distilled_experience(distilled)
                log(f"[Auto-Distill Sync] Merged {len(distilled)} positions from Colab ({ACTIVE_SESSION}) -> Total Brain: {tot:,} | New: {added:,} | Amplified: {amp:,} | Blunders Vetoed: {blund:,}")
        except Exception as e:
            log(f"[Auto-Distill Error] Failed to parse distilled JSON: {e}")
    else:
        consecutive_failures += 1

    # 2. Download metrics
    if download_file("/content/selfplay_100m_metrics.json", TEMP_METRICS):
        try:
            with open(TEMP_METRICS, "r", encoding="utf-8") as f:
                metrics = json.load(f)
            games = metrics.get("games_completed", 0)
            target = metrics.get("target_games", 100000000)
            gps = metrics.get("games_per_sec", 0)
            pps = metrics.get("pos_per_sec", 0)
            acc = metrics.get("top1_acc", 0)
            log(f"[Colab Metrics - {ACTIVE_SESSION}] Games: {games:,}/{target:,} ({(games/target)*100:.3f}%) | Speed: {gps} g/s ({pps} pos/s) | Top-1 Acc: {acc}%")
        except Exception:
            pass

    # 3. Check for Failover/Recovery requirement (if 3 consecutive download failures occur)
    if consecutive_failures >= 3:
        log(f"[Watchdog Notice] 3 consecutive poll failures on {ACTIVE_SESSION}. Verifying session health...")
        is_healthy = check_session_responsive(ACTIVE_SESSION)
        if not is_healthy:
            log(f"[Watchdog Notice] Session {ACTIVE_SESSION} unresponsive. Auto-recovering session and streamer...")
            failover_to_cpu()
            consecutive_failures = 0

def main():
    log("=== Autonomous Colab Auto-Distiller & Quota Failover Daemon Started ===")
    log(f"Active Polling Session: {ACTIVE_SESSION}")
    log(f"Target Memory File: {LOCAL_MEMORY}")
    log("Auto-Watchdog: Monitoring T4 GPU health; automatic failover to Colab CPU upon quota exhaustion.")

    while True:
        try:
            run_auto_distill_cycle()
        except Exception as e:
            log(f"[Daemon Exception] {e}")
        time.sleep(35)

if __name__ == "__main__":
    main()
