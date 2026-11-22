#!/usr/bin/env python3
"""
TrueEngine V1: Universal AI Agent Takeover & Autonomous Control Suite
Allows an incoming AI Agent or remote engineer on another machine to immediately
inspect, monitor, control, and benchmark TrueEngine V1.
"""

import sys
import os
import json
import time
import requests
import subprocess
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "engine_config.json")
PGN_PATH = os.path.join(SCRIPT_DIR, "data", "stockfish19_vs_trueengine_600.pgn")
NTFY_TOPIC = "https://ntfy.sh/trueengine_t4_hieu/json?poll=1"

def discover_tunnel():
    """Discovers active Kaggle Cloudflare tunnel URL."""
    # 1. From engine_config.json
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                c = json.load(f)
            url = c.get("cloud_backend_url")
            if url:
                try:
                    r = requests.get(f"{url}/health", timeout=3)
                    if r.status_code == 200:
                        return url
                except Exception:
                    pass
        except Exception:
            pass

    # 2. From ntfy webhook
    try:
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
            if urls:
                for cand in reversed(urls):
                    try:
                        h = requests.get(f"{cand}/health", timeout=3)
                        if h.status_code == 200:
                            return cand
                    except Exception:
                        pass
                return urls[-1]  # Return latest candidate even if booting
    except Exception:
        pass

    return None

def sync_config(url):
    """Syncs active tunnel URL to local engine_config.json."""
    if not os.path.exists(CONFIG_PATH):
        cfg = {}
    else:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    cfg["cloud_backend_url"] = url
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print(f"✅ Synced tunnel URL to engine_config.json: {url}")

def cmd_status(args):
    print("==================================================================")
    print(" 🤖 TRUEENGINE V1: AI AGENT CLUSTER STATUS & HEALTH AUDIT")
    print("==================================================================")
    
    url = discover_tunnel()
    if not url:
        print("❌ No active Kaggle tunnel discovered.")
        print("💡 Run 'python agent_takeover.py restart-cluster' to spin up a new Dual-T4 session.")
        return 1

    print(f"🌐 Active Cluster Tunnel: {url}")
    sync_config(url)

    # Health check
    try:
        h = requests.get(f"{url}/health", timeout=5).json()
        print(f"💚 Cluster Health: {h.get('status')} | Tier: {h.get('tier')}")
        print(f"⚡ Device: {h.get('device')}")
        print(f"   Lc0 Binary: {h.get('lc0')} | BT4 Supernet: {h.get('weights')} | Stockfish: {h.get('stockfish')}")
    except Exception as e:
        print(f"⚠️ Cluster health error (may still be booting port 8000): {e}")

    # Elo live check
    try:
        e = requests.get(f"{url}/elo_live", timeout=5).json()
        print("\n🏆 600-MATCH GRANDMASTER ELO TOURNAMENT STATUS:")
        print(f"   Status:           {e.get('status')}")
        print(f"   Matches:          {e.get('games_completed', 0)} / {e.get('games_target', 600)}")
        print(f"   Score:            +{e.get('trueengine_wins', 0)} Wins | ={e.get('draws', 0)} Draws | -{e.get('stockfish_wins', 0)} Losses ({e.get('score_pct', 0.0)}%)")
        print(f"   Stockfish Base:   {e.get('stockfish_base_elo', 3645.0)} CCRL Elo")
        print(f"   🔥 TrueEngine Elo: {e.get('trueengine_elo')} ± {e.get('margin')} CCRL Elo")
    except Exception as e:
        print(f"⚠️ Live Elo endpoint notice: {e}")

    return 0

def cmd_watch(args):
    print("📡 Watching live tournament stream... (Ctrl+C to stop)")
    url = discover_tunnel()
    if not url:
        print("❌ Cannot find active tunnel.")
        return 1

    while True:
        try:
            r = requests.get(f"{url}/elo_live", timeout=5)
            if r.status_code == 200:
                st = r.json()
                completed = st.get('games_completed', 0)
                target = st.get('games_target', 600)
                w = st.get('trueengine_wins', 0)
                d = st.get('draws', 0)
                l = st.get('stockfish_wins', 0)
                pct = st.get('score_pct', 0.0)
                elo = st.get('trueengine_elo', 3645.0)
                margin = st.get('margin', 0.0)
                status = st.get('status', 'running')
                print(f"\r[Match {completed:03d}/{target}] (+{w} ={d} -{l}) {pct}% | Live Elo: {elo} ± {margin} CCRL | Cluster: {status}   ", end="", flush=True)
                if status == "finished" and completed >= target:
                    print("\n\n🏁 600 Matches Complete!")
                    break
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped watching.")
            break
        except Exception:
            time.sleep(args.interval)
    return 0

def cmd_fetch_pgn(args):
    url = discover_tunnel()
    if not url:
        print("❌ Cannot find active tunnel.")
        return 1

    print(f"📥 Downloading complete tournament PGN from {url}/download_pgn...")
    try:
        r = requests.get(f"{url}/download_pgn", timeout=15)
        if r.status_code == 200:
            os.makedirs(os.path.dirname(PGN_PATH), exist_ok=True)
            with open(PGN_PATH, "w", encoding="utf-8") as f:
                f.write(r.text)
            print(f"✅ Saved PGN to {PGN_PATH} ({len(r.text.splitlines())} lines)")
            return 0
        else:
            print(f"❌ Failed to fetch PGN. HTTP status: {r.status_code}")
            return 1
    except Exception as e:
        print(f"❌ Error fetching PGN: {e}")
        return 1

def cmd_test_eval(args):
    url = discover_tunnel()
    if not url:
        print("❌ Cannot find active tunnel.")
        return 1

    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    print(f"⚡ Testing Cloud Inference on 2x Tesla T4 GPUs...")
    print(f"   FEN: {fen}")
    t0 = time.time()
    try:
        r = requests.post(f"{url}/evaluate", json={"fen": fen, "nodes": 3000}, timeout=10)
        spent = round(time.time() - t0, 3)
        if r.status_code == 200:
            data = r.json()
            print(f"✅ Best Move: {data.get('bestmove')} ({spent}s)")
            print(f"   NPS: {data.get('nps')} | Depth: {data.get('depth')} | Score: {data.get('score_cp')} cp")
            print(f"   Hardware Tier: {data.get('tier')}")
            return 0
        else:
            print(f"❌ Error: {r.status_code} - {r.text}")
            return 1
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return 1

def cmd_restart_cluster(args):
    kaggle_dir = os.path.join(SCRIPT_DIR, "kaggle_t4")
    if not os.path.exists(kaggle_dir):
        print(f"❌ Directory not found: {kaggle_dir}")
        return 1

    print("🚀 Pushing notebook to Kaggle to boot fresh Dual Tesla T4 cluster...")
    res = subprocess.run(["kaggle", "kernels", "push", "-p", kaggle_dir], capture_output=True, text=True)
    print(res.stdout)
    if res.returncode == 0:
        print("✅ Kaggle batch cluster successfully initiated!")
        print("⏳ Allow ~90 seconds for Lc0 and Cloudflared tunnel to launch.")
        return 0
    else:
        print("❌ Kaggle push failed:", res.stderr)
        return 1

def main():
    parser = argparse.ArgumentParser(description="TrueEngine V1: Universal AI Agent Takeover Suite")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    subparsers.add_parser("status", help="Audit cluster health and live 600-match Elo status")
    
    watch_p = subparsers.add_parser("watch", help="Stream live tournament updates")
    watch_p.add_argument("--interval", type=int, default=15, help="Refresh interval in seconds")

    subparsers.add_parser("fetch-pgn", help="Download complete 600-match PGN from Kaggle")
    subparsers.add_parser("test-eval", help="Test cloud move evaluation on Dual Tesla T4s")
    subparsers.add_parser("sync", help="Sync latest tunnel URL to engine_config.json")
    subparsers.add_parser("restart-cluster", help="Reboot/Push Kaggle Dual Tesla T4 cluster")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "status": cmd_status,
        "watch": cmd_watch,
        "fetch-pgn": cmd_fetch_pgn,
        "test-eval": cmd_test_eval,
        "sync": lambda a: cmd_status(a),
        "restart-cluster": cmd_restart_cluster
    }

    code = dispatch[args.command](args)
    sys.exit(code or 0)

if __name__ == "__main__":
    main()
