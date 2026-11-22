import urllib.request
import json
import os
import sys
import time

BRIDGE_URL = "https://start-throwing-blacks-accommodate.trycloudflare.com"
PROJECT_DIR = r"C:\Users\RealTrueHieu\CustomHumanChessEngine"
LOCAL_MEMORY = os.path.join(PROJECT_DIR, "books", "experience_memory.json")

def api_get(endpoint):
    url = f"{BRIDGE_URL}{endpoint}"
    req = urllib.request.Request(url, headers={"User-Agent": "TrueEngine-Bridge-Client"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8"))

def api_post(endpoint, data):
    url = f"{BRIDGE_URL}{endpoint}"
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={
        "User-Agent": "TrueEngine-Bridge-Client",
        "Content-Type": "application/json"
    })
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8"))

def ping():
    t0 = time.time()
    res = api_get("/health")
    ms = (time.time() - t0) * 1000
    print(f"[Bridge Ping] Latency: {ms:.1f}ms | Response: {res}")
    return res

def get_metrics():
    res = api_get("/metrics")
    print(json.dumps(res, indent=2))
    return res

def pull_distilled():
    print("[Bridge Sync] Pulling distilled knowledge from Cloud over secure tunnel...")
    t0 = time.time()
    distilled = api_get("/distilled")
    if not distilled or not isinstance(distilled, dict):
        print("[Bridge Sync] No new distilled data available on cloud yet.")
        return

    if os.path.exists(LOCAL_MEMORY):
        with open(LOCAL_MEMORY, "r", encoding="utf-8") as f:
            local_mem = json.load(f)
    else:
        local_mem = {}

    merged = 0
    for epd, moves in distilled.items():
        if epd not in local_mem:
            local_mem[epd] = {}
        for move, stats in moves.items():
            if move not in local_mem[epd]:
                local_mem[epd][move] = {
                    "visits": stats.get("visits", 1),
                    "wins": stats.get("wins", 0),
                    "draws": 0,
                    "losses": stats.get("losses", 0),
                    "multiplier": stats.get("multiplier", 1.0),
                    "blunder": stats.get("multiplier", 1.0) < 0.1,
                    "last_updated": int(time.time())
                }
                merged += 1

    temp_mem = LOCAL_MEMORY + ".tmp"
    with open(temp_mem, "w", encoding="utf-8") as f:
        json.dump(local_mem, f, indent=2)
    os.replace(temp_mem, LOCAL_MEMORY)

    ms = (time.time() - t0) * 1000
    print(f"[Bridge Sync] Downloaded {len(distilled)} cloud positions in {ms:.0f}ms! Total Local Brain: {len(local_mem)} positions (+{merged} new).")

def push_blunder(fen, move, refutation=""):
    payload = {
        "fen": fen,
        "blunder_move": move,
        "refutation": refutation,
        "timestamp": int(time.time())
    }
    res = api_post("/push_blunder", payload)
    print(f"[Bridge Push] Injected blunder into Cloud training queue: {res}")

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "ping"
    if action == "ping":
        ping()
    elif action == "metrics":
        get_metrics()
    elif action == "sync":
        pull_distilled()
    elif action == "push" and len(sys.argv) >= 4:
        push_blunder(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "")
    else:
        print("Usage: python cloud_bridge_client.py [ping | metrics | sync | push <fen> <move> <refutation>]")
