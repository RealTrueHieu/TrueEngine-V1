import subprocess
import json
import os
import sys

SESSION = "chess-100m-t4"
PROJECT_DIR = r"C:\Users\RealTrueHieu\CustomHumanChessEngine"
LOCAL_MEMORY = os.path.join(PROJECT_DIR, "books", "experience_memory.json")
LOCAL_MODELS_DIR = os.path.join(PROJECT_DIR, "models")
os.makedirs(LOCAL_MODELS_DIR, exist_ok=True)

def run_colab(code, timeout=60):
    cmd = ["colab", "exec", "-s", SESSION, "--timeout", str(timeout)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out, _ = p.communicate(code)
    return out

def get_status():
    code = """
import os, json
if os.path.exists('/content/selfplay_100m_status.log'):
    with open('/content/selfplay_100m_status.log', 'r') as f:
        print('STATUS:', f.read().strip())
if os.path.exists('/content/selfplay_100m_metrics.json'):
    with open('/content/selfplay_100m_metrics.json', 'r') as f:
        print('METRICS:', f.read().strip())
"""
    return run_colab(code)

def sync_distilled_data():
    print("[Colab Sync] Fetching distilled experience memory from Colab...")
    fetch_code = """
import os, json
if os.path.exists('/content/colab_distilled_experience.json'):
    with open('/content/colab_distilled_experience.json', 'r') as f:
        data = json.load(f)
    print(f'DISTILLED_COUNT:{len(data)}')
    # Dump compact sample
    with open('/content/colab_distilled_experience.json', 'r') as f:
        print('JSON_DATA_START')
        print(f.read())
        print('JSON_DATA_END')
else:
    print('DISTILLED_NOT_READY_YET')
"""
    out = run_colab(fetch_code, timeout=120)
    if "JSON_DATA_START" in out:
        raw_json = out.split("JSON_DATA_START")[1].split("JSON_DATA_END")[0].strip()
        distilled = json.loads(raw_json)
        print(f"[Colab Sync] Downloaded {len(distilled)} distilled positions!")
        
        # Merge into local experience memory
        if os.path.exists(LOCAL_MEMORY):
            with open(LOCAL_MEMORY, "r", encoding="utf-8") as f:
                local_mem = json.load(f)
        else:
            local_mem = {}

        merged_count = 0
        for epd, moves in distilled.items():
            if epd not in local_mem:
                local_mem[epd] = {}
            for move, stats in moves.items():
                if move not in local_mem[epd]:
                    local_mem[epd][move] = {
                        "visits": stats["visits"],
                        "wins": stats["wins"],
                        "draws": 0,
                        "losses": stats["losses"],
                        "multiplier": stats["multiplier"],
                        "blunder": stats["multiplier"] < 0.1
                    }
                    merged_count += 1
                else:
                    # Update multiplier
                    local_mem[epd][move]["visits"] += stats["visits"]
                    local_mem[epd][move]["wins"] += stats["wins"]
                    local_mem[epd][move]["multiplier"] = round((local_mem[epd][move]["multiplier"] + stats["multiplier"]) / 2.0, 3)

        with open(LOCAL_MEMORY, "w", encoding="utf-8") as f:
            json.dump(local_mem, f, indent=2)
        print(f"[Colab Sync] Successfully merged {merged_count} new lines into local brain! Total: {len(local_mem)} positions.")
    else:
        print("[Colab Sync] Distilled memory checkpoint not generated yet (saves every 5,000 games).")

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "status":
        print(get_status())
    elif action == "sync":
        sync_distilled_data()
