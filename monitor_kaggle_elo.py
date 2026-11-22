import requests
import json
import time
import os
import subprocess
import sys

CONFIG_PATH = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\engine_config.json"
PGN_LOCAL_PATH = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\data\stockfish19_vs_trueengine_600.pgn"
os.makedirs(os.path.dirname(PGN_LOCAL_PATH), exist_ok=True)

def get_tunnel_url():
    # 1. Check ntfy broadcast (poll mode)
    try:
        r = requests.get("https://ntfy.sh/trueengine_t4_hieu/json?poll=1", timeout=4)
        if r.status_code == 200:
            urls = []
            for line in r.text.strip().split("\n"):
                if line.strip():
                    try:
                        d = json.loads(line)
                        msg = d.get("message", "")
                        if msg.startswith("https://"):
                            urls.append(msg)
                    except Exception:
                        pass
            if urls:
                candidate = urls[-1]
                try:
                    h = requests.get(f"{candidate}/health", timeout=3)
                    if h.status_code == 200:
                        return candidate
                except Exception:
                    pass
    except Exception:
        pass

    # 2. Check engine_config.json
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cand = cfg.get("cloud_backend_url")
            if cand:
                h = requests.get(f"{cand}/health", timeout=3)
                if h.status_code == 200:
                    return cand
        except Exception:
            pass

    return None

def get_local_gpu():
    try:
        res = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True)
        parts = res.stdout.strip().split(",")
        return f"{parts[0].strip()}% util | {parts[1].strip()} MB VRAM"
    except Exception:
        return "N/A"

def monitor():
    print("==================================================================", flush=True)
    print(" 🏛️ TRUEENGINE V1 CLOUD: 600-MATCH ELO BENCHMARK MONITOR", flush=True)
    print(" Baseline Anchor: Stockfish 19 (3645 CCRL Elo)", flush=True)
    print(" Supercomputing Engine: 2x Tesla T4 GPUs (Lc0 BT4 Supernet on Kaggle)", flush=True)
    print(" Local GPU Status: STRICT ZERO USAGE (Cloud Native)", flush=True)
    print("==================================================================\n", flush=True)

    tunnel_url = None
    print("Connecting to Kaggle cluster...", flush=True)

    while True:
        if not tunnel_url:
            tunnel_url = get_tunnel_url()
            if tunnel_url:
                print(f"✅ Connected to Kaggle Cluster: {tunnel_url}\n", flush=True)
                # Update local config
                if os.path.exists(CONFIG_PATH):
                    try:
                        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                            c = json.load(f)
                        c["cloud_backend_url"] = tunnel_url
                        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                            json.dump(c, f, indent=2)
                    except Exception:
                        pass
            else:
                print("⏳ Waiting for Kaggle cluster to boot Lc0 & launch Cloudflare tunnel... (checking every 10s)", flush=True)
                time.sleep(10)
                continue

        try:
            r = requests.get(f"{tunnel_url}/elo_live", timeout=6)
            if r.status_code == 200:
                st = r.json()
                completed = st.get("games_completed", 0)
                target = st.get("games_target", 600)
                w = st.get("trueengine_wins", 0)
                d = st.get("draws", 0)
                l = st.get("stockfish_wins", 0)
                pct = st.get("score_pct", 0.0)
                elo = st.get("trueengine_elo", 3645.0)
                margin = st.get("margin", 0.0)
                status = st.get("status", "running")
                gpu_str = get_local_gpu()

                print(f"\r[Match {completed:03d}/{target}] Score: +{w} ={d} -{l} ({pct}%) | Live Elo: {elo} ± {margin} CCRL | Local GPU: {gpu_str} | Cluster: {status}", end="", flush=True)

                if status == "finished" and completed >= target:
                    print("\n\n🏆 ALL 600 MATCHES COMPLETED!", flush=True)
                    print(f"Final Standing: +{w} Wins | ={d} Draws | -{l} Losses ({pct}%)")
                    print(f"🔥 OFFICIAL TRUEENGINE V1 ELO: {elo} ± {margin} CCRL ELO")
                    
                    # Download PGN
                    p_res = requests.get(f"{tunnel_url}/download_pgn", timeout=15)
                    if p_res.status_code == 200:
                        with open(PGN_LOCAL_PATH, "w", encoding="utf-8") as pf:
                            pf.write(p_res.text)
                        print(f"📁 Full 600-Match PGN saved to {PGN_LOCAL_PATH}")
                    break
            else:
                tunnel_url = None
        except Exception:
            tunnel_url = None

        time.sleep(12)

if __name__ == "__main__":
    monitor()
