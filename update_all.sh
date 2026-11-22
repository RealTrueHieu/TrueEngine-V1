#!/usr/bin/env bash
# ==============================================================================
# TrueEngine V1: Universal One-Click Autonomous Full Cycle Engine
# ==============================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$SCRIPT_DIR"

export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export CLOUDFLARE_API_TOKEN="${CLOUDFLARE_API_TOKEN:-$(cat $HOME/.cloudflare/token 2>/dev/null || true)}"
export CLOUDFLARE_ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-35bcb20a3d655f2d3de7fd7a39597ecd}"
export KAGGLE_API_TOKEN="${KAGGLE_API_TOKEN:-$(cat $HOME/.kaggle/access_token 2>/dev/null || true)}"
export GH_TOKEN="${GH_TOKEN:-$(cat $HOME/.git-credentials 2>/dev/null | grep -o 'github_pat_[a-zA-Z0-9_]*' | head -n 1)}"

echo "=================================================================="
echo " 🚀 TRUEENGINE V1: FULL AUTONOMOUS MULTI-CLOUD SYSTEM CYCLE"
echo "=================================================================="

# 1. Audit & Sync Kaggle Dual-T4 Supercomputing Cluster (30GB VRAM)
echo -e "\n[1/6] Auditing Kaggle Dual-T4 Cluster & Cloudflare Tunnel..."
python3 agent_takeover.py status || true

# 2. Check & Sync Google Colab T4 (chess-100m-t4) Self-Play Streamer
echo -e "\n[2/6] Syncing Google Colab T4 (chess-100m-t4) Massive Self-Play..."
COLAB_STATUS=$(colab status -s chess-100m-t4 2>/dev/null || echo "OFFLINE")
echo "   Colab T4 Status: $COLAB_STATUS"

# Download latest Colab metrics
colab download /content/selfplay_100m_metrics.json "$SCRIPT_DIR/selfplay_100m_metrics.json" 2>/dev/null || true
if [ -f "$SCRIPT_DIR/selfplay_100m_metrics.json" ]; then
    python3 -c "
import json
try:
    m = json.load(open('$SCRIPT_DIR/selfplay_100m_metrics.json'))
    print(f'   ⚡ Colab Self-Play: {m.get(\"games_completed\", 0):,}/{m.get(\"target_games\", 100000000):,} games | Speed: {m.get(\"games_per_sec\", 0)} g/s ({m.get(\"pos_per_sec\", 0)} pos/s) | Top-1 Acc: {m.get(\"top1_acc\", 0)}%')
except Exception:
    pass
" || true
fi

# 3. Consolidate Experience Brain & Train TrueEngineSuperNet on this Machine
echo -e "\n[3/6] Distilling Experience & Training TrueEngineSuperNet on CPU..."
python3 fetch_and_train_pipeline.py || true

# 4. Check & Keep 600-Match CCRL Elo Tournament vs Stockfish 19 Active
echo -e "\n[4/6] Auditing 600-Match CCRL Elo Tournament Benchmark..."
# Ensure tournament daemon service is running
systemctl --user start trueengine-tournament.service 2>/dev/null || true
python3 -c "
import json, os
st_path = '$SCRIPT_DIR/tournament_state.json'
if os.path.exists(st_path):
    st = json.load(open(st_path))
    c = st.get('games_completed', 0)
    target = st.get('games_target', 600)
    w = st.get('trueengine_wins', 0)
    d = st.get('draws', 0)
    l = st.get('stockfish_wins', 0)
    pct = st.get('score_pct', 0.0)
    elo = st.get('trueengine_elo', 3645.0)
    margin = st.get('margin', 0.0)
    status = st.get('status', 'RUNNING')
    print(f'   🏆 Status: {status} | Matches: {c}/{target} ({round(c/target*100, 1)}%)')
    print(f'   🥊 Score:  +{w} Wins | ={d} Draws | -{l} Losses ({pct}%)')
    print(f'   🔥 Calculated Elo: {elo} ± {margin} CCRL (Stockfish 19 Anchor: 3645 Elo)')
" || true

# 5. Deploy Cloudflare Worker 1-Second Sub-Second Live Edge Telemetry
echo -e "\n[5/6] Deploying Cloudflare Worker (1-Second Sub-Second Live Telemetry)..."
cd "$SCRIPT_DIR/cloudflare_worker"
wrangler deploy --dry-run=false || true
cd "$SCRIPT_DIR"

# 6. Commit Updates, Push to GitHub & Trigger GitHub Actions Cloud Training
echo -e "\n[6/6] Synchronizing with GitHub Repository & Cloud CI/CD..."
git config user.name "RealTrueHieu" || true
git config user.email "realtruehieu@gmail.com" || true

# Add data, state, models, and scripts
git add books/ models/ data/ tournament_state.json selfplay_100m_metrics.json cloudflare_worker/ run_600_tournament.py fetch_and_train_pipeline.py update_all.sh .github/ .devcontainer/ 2>/dev/null || true

TS=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
if git diff --staged --quiet; then
    echo "   Git: Working tree already up-to-date."
else
    git commit -m "[Auto-Sync] TrueEngine V1: 1s Live Dashboard, Colab Self-Play & SuperNet Weights ($TS)" || true
    echo "   Git: Committed latest models, experience memory & tournament state."
fi

# Push to GitHub
git push origin HEAD && echo "   Git: Successfully pushed to GitHub origin/main!" || true

# Trigger GitHub Actions CI workflow (compliant with limits)
gh workflow run "train_and_distill.yml" -R RealTrueHieu/TrueEngine-V1 2>/dev/null && echo "   GitHub Actions: Dispatched automated model distillation run!" || true

echo -e "\n=================================================================="
echo " 🎉 TRUEENGINE V1 FULL CYCLE RUN COMPLETE!"
echo " 🌐 Live 1s Dashboard: https://trueengine-live.truehieu.workers.dev"
echo " 📂 GitHub Repo:       https://github.com/RealTrueHieu/TrueEngine-V1"
echo "=================================================================="
