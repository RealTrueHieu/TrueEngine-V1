# 🤖 TRUEENGINE V1: AI AGENT SYSTEM HANDOVER & MISSION BRIEFING

> **Target Audience:** Incoming AI Agent / Autonomous Engineer on a remote server or new environment.  
> **Repository:** [https://github.com/RealTrueHieu/TrueEngine-V1](https://github.com/RealTrueHieu/TrueEngine-V1)  
> **Status:** Active Deployment | 600-Match CCRL Elo Benchmark vs Stockfish 19 | Zero-Local-GPU Enforced  
> **Date Generated:** 2026-11-22  

---

## 🎯 1. Executive Summary & Goals

**TrueEngine V1** is a Grandmaster-level hybrid chess engine designed for human-like positional mastery combined with supercomputing calculation depth.
- **Neural Core:** Leela Chess Zero (Lc0) running the **BT4 Grandmaster Supernet (382MB)** (`BT4-1024x15x32h-swa-6147500-policytune-332.pb.gz`).
- **Co-Pilot / Tactical Oracle:** Stockfish 19 Tactical Oracle for tactical blunder-proofing.
- **Strict Architecture Policy:** **ZERO LOCAL GPU LOAD**. All heavy neural inference runs on a remote **Kaggle Dual Tesla T4 Supercomputing Cluster (30GB VRAM, 640 Tensor Cores)** exposed via Cloudflare Tunnel. The local engine executable (`TrueEngine_V1_Cloud.exe`) communicates via HTTP/JSON. If the network hiccups, it fails over to local CPU Stockfish only—local GPU (GTX 1660 Ti) remains strictly at 0 MB VRAM and 0% load.

---

## 🏗️ 2. Core Infrastructure & Active Assets

### A. Kaggle Dual Tesla T4 Compute Cluster
- **Notebook Name:** `trueengine-v1-dual-t4-supercomputing-cluster`
- **Owner Account:** `truehieu`
- **Kaggle API Key:** Configure locally via `kaggle.json` or environment variables (provided in private prompt, not stored in repo).
- **Hardware:** 2x NVIDIA Tesla T4 GPUs (15GB + 15GB VRAM = 30GB VRAM).
- **Tunnel Discovery:** Every time the Kaggle cluster boots, it publishes its live Cloudflare Tunnel URL to the public webhook topic:
  `https://ntfy.sh/trueengine_t4_hieu/json?poll=1`

### B. Cloud API Endpoints
When the cluster is online, the active tunnel URL provides:
- `GET /health`: JSON cluster health and status.
- `POST /evaluate`: UCI evaluation endpoint (returns `bestmove`, `score_cp`, `nps`, `depth`).
- `GET /elo_live`: Live statistics of the 600-match benchmark against Stockfish 19.
- `GET /download_pgn`: Downloads the complete multi-game PGN of the ongoing match.

### C. Vanguard Gen-6 Arena Clash
- **Arena URL:** `https://lethoso.tech/`
- **Credentials:** Set locally via `VANGUARD_USER` and `VANGUARD_PASS` environment variables.
- **Match Record:** TrueEngine V1 defeated Vanguard Gen-6 Big (`gen6_full`) **2 - 0 (Clean Sweep)**:
  - Game 1: 1-0 (47 moves, Checkmate `Re8#`).
  - Game 2: 0-1 (93 moves, Checkmate `Rh2#`).
  - PGN File: `data/vanguard_gen6_clash.pgn`.

---

## ⚡ 3. Active Mission: 600-Match CCRL Elo Benchmark vs Stockfish 19

The Kaggle cluster runs an autonomous 600-game match between **TrueEngine V1 (Lc0 BT4 on Dual T4s)** and **Stockfish 19 (CCRL Anchor: 3645 Elo)**.
- **Time Control:** Ultra-fast bullet/blitz (`nodes=2500` vs `movetime=140ms`, ~0.15s/move).
- **Openings:** 14 diverse opening books (Sicilian, French, Caro-Kann, Ruy Lopez, King's Indian, etc.).
- **Mathematical Formula:** Empirical CCRL Logistic Model with 95% Confidence Interval:
  $$\Delta\text{Elo} = -400 \times \log_{10}\left(\frac{1 - P}{P}\right), \quad \text{Elo} = 3645 + \Delta\text{Elo}$$
  $$\text{Margin} = \pm 1.96 \times \sqrt{\frac{P(1 - P)}{N}} \times \frac{400}{\ln(10) \cdot P(1 - P)}$$

---

## 🛠️ 4. Quick-Start for the New AI Agent

Any agent on a new machine or server can take over full control using the included `agent_takeover.py` CLI:

### 1. Clone & Set Up
```bash
git clone https://github.com/RealTrueHieu/TrueEngine-V1.git
cd TrueEngine-V1
pip install requests chess python-chess
```

### 2. Check Live System Health & Active Tunnel
```bash
python agent_takeover.py status
```

### 3. Stream Live 600-Match Tournament Progress
```bash
python agent_takeover.py watch
```

### 4. Fetch the Complete PGN
```bash
python agent_takeover.py fetch-pgn
```

### 5. Test Move Evaluation (Ensure 0 Local GPU)
```bash
python agent_takeover.py test-eval
```

---

## 🚨 5. Troubleshooting & Operations Runbook

1. **Tunnel 502 Bad Gateway / Cluster Booting:**
   - Wait 60–90 seconds. Kaggle takes ~1.5 minutes to pull the BT4 weights and initialize CUDA before port 8000 opens.
2. **Tunnel Expired or Kaggle Session Stopped (after 9–12 hours):**
   - Push the notebook again using the Kaggle CLI:
     ```bash
     kaggle kernels push -p ./kaggle_t4
     ```
   - Watch `ntfy.sh/trueengine_t4_hieu/json?poll=1` for the new tunnel URL.
   - Run `python agent_takeover.py sync` to automatically update `engine_config.json`.
3. **Zero Local GPU Verification:**
   - Always verify local GPU load with `nvidia-smi`. `TrueEngine_V1_Cloud` must NEVER allocate more than 0 MB VRAM or cause >0% engine compute on the local graphics card.
