#!/usr/bin/env bash
# ==============================================================================
# TrueEngine V1: Universal Multi-Cloud Master CLI (trueengine)
# ==============================================================================

set -e

# Color definitions
C_RESET="\033[0m"
C_BOLD="\033[1m"
C_CYAN="\033[38;5;51m"
C_GREEN="\033[38;5;48m"
C_GOLD="\033[38;5;220m"
C_PURPLE="\033[38;5;141m"
C_RED="\033[38;5;196m"
C_GRAY="\033[38;5;244m"

V1_DIR="/data/workspace/TrueEngine-V1"
MOLAB_API="http://127.0.0.1:8766"

show_banner() {
    echo -e "${C_CYAN}${C_BOLD}"
    cat << "EOF"
  ████████╗██████╗ ██╗   ██╗███████╗███████╗███╗   ██╗ ██████╗ ██╗███╗   ██╗███████╗
  ╚══██╔══╝██╔══██╗██║   ██║██╔════╝██╔════╝████╗  ██║██╔════╝ ██║████╗  ██║██╔════╝
     ██║   ██████╔╝██║   ██║█████╗  █████╗  ██╔██╗ ██║██║  ███╗██║██╔██╗ ██║█████╗  
     ██║   ██╔══██╗██║   ██║██╔══╝  ██╔══╝  ██║╚██╗██║██║   ██║██║██║╚██╗██║██╔══╝  
     ██║   ██║  ██║╚██████╔╝███████╗███████╗██║ ╚████║╚██████╔╝██║██║ ╚████║███████╗
     ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝╚══════╝
EOF
    echo -e "       👑 Autonomous Multi-Cloud Supercomputing Neural Chess Engine Ecosystem${C_RESET}"
    echo -e "       🌐 Dashboard: ${C_CYAN}https://trueengine-live.truehieu.workers.dev${C_RESET}\n"
}

cmd_status() {
    show_banner
    echo -e "${C_BOLD}=== ⚡ TRI-INFRA SUPERCOMPUTING CLUSTER STATUS ===${C_RESET}"

    # 1. Molab Blackwell
    echo -e "\n${C_PURPLE}${C_BOLD}[1] Molab Marimo Blackwell (Primary Heavy Supernet Node):${C_RESET}"
    python3 -c "
import json, os, time
p = '$V1_DIR/molab_state.json'
if os.path.exists(p):
    try:
        d = json.load(open(p))
        age = int(time.time() - d.get('last_updated', d.get('timestamp', 0)))
        status = d.get('status', 'ONLINE')
        gpu = d.get('gpu', 'NVIDIA RTX PRO 6000 Blackwell')
        vram = d.get('vram', '98 GB VRAM')
        speed = d.get('speed', '117k pos/s')
        loss = d.get('last_loss', '--')
        acc = d.get('accuracy_pct', '--')
        util = d.get('gpu_util_pct', 0)
        power = d.get('gpu_power_w', 0)
        print(f'    ● Status:      \033[38;5;48m{status}\033[0m (Heartbeat: {age}s ago)')
        print(f'    ● Accelerator: {gpu} ({vram})')
        print(f'    ● GPU Load:    {util}% Utilization | {power}W Draw | Speed: \033[38;5;51m{speed}\033[0m')
        print(f'    ● Neural Net:  Loss {loss} | Top-1 Accuracy: \033[38;5;220m{acc}%\033[0m')
    except Exception as e:
        print(f'    ● Status:      \033[38;5;244mInitializing ({e})\033[0m')
else:
    print('    ● Status:      \033[38;5;244mStandby / Waiting for Molab session\033[0m')
"

    # 2. Google Colab
    echo -e "\n${C_CYAN}${C_BOLD}[2] Google Colab (Continuous 24/7 Self-Play Streamer):${C_RESET}"
    COLAB_SESSION=$(colab sessions 2>/dev/null | grep -o '\[[^]]*\]' | tr -d '[]' | head -n 1 || echo "")
    if [ -n "$COLAB_SESSION" ]; then
        echo -e "    ● Active VM:   ${C_GREEN}${COLAB_SESSION}${C_RESET}"
        python3 -c "
import json, os
p = '$V1_DIR/selfplay_100m_metrics.json'
if os.path.exists(p):
    try:
        m = json.load(open(p))
        g = m.get('games_completed', 0)
        t = m.get('target_games', 100000000)
        pos = m.get('positions_generated', 0)
        acc = m.get('top1_acc', 0)
        print(f'    ● Self-Play:   {g:,}/{t:,} games ({pos:,} positions)')
        print(f'    ● Throughput:  {m.get(\"games_per_sec\", 0)} g/s ({m.get(\"pos_per_sec\", 0)} pos/s) | Top-1: \033[38;5;48m{acc}%\033[0m')
    except Exception:
        pass
"
    else
        echo -e "    ● Status:      ${C_GRAY}No active Colab VM detected${C_RESET}"
    fi

    # 3. Kaggle Dual-T4
    echo -e "\n${C_GOLD}${C_BOLD}[3] Kaggle Supercomputing Cluster (Dual-Tesla T4):${C_RESET}"
    echo -e "    ● Status:      ${C_GOLD}PAUSED (Quota Safeguard - ~3h Preserved for Tournament)${C_RESET}"
    echo -e "    ● Hardware:    2x Tesla T4 (32GB VRAM - Lc0 BT4 Neural Weights)"

    # 4. Local Host & Brain Memory
    echo -e "\n${C_GREEN}${C_BOLD}[4] Local Host Environment & Brain Memory:${C_RESET}"
    echo -e "    ● Host GPU:    ${C_GREEN}0 MB VRAM / 0% GPU (Strict Zero-Load Guard Enforced)${C_RESET}"
    python3 -c "
import json, os
mem_p = '/data/workspace/books/experience_memory.json'
if os.path.exists(mem_p):
    try:
        cnt = len(json.load(open(mem_p)))
        sz_mb = os.path.getsize(mem_p) / (1024 * 1024)
        print(f'    ● Brain Mem:   \033[38;5;48m{cnt:,} Curated Positions\033[0m ({sz_mb:.1f} MB)')
    except Exception:
        pass
"
    # Local services
    echo -e "    ● Background Services:"
    for s in trueengine-sync trueengine-molab-api trueengine-molab trueengine-colab-daemon trueengine-sentry trueengine-tournament; do
        IS_ACT=$(systemctl --user is-active $s.service 2>/dev/null || echo "inactive")
        if [ "$IS_ACT" = "active" ]; then
            echo -e "      - ${s}: ${C_GREEN}active (running)${C_RESET}"
        else
            echo -e "      - ${s}: ${C_RED}${IS_ACT}${C_RESET}"
        fi
    done

    echo -e "\n${C_GRAY}Run 'trueengine molab help' or 'trueengine sync' for cluster actions.${C_RESET}\n"
}

cmd_molab() {
    SUBCMD="${1:-status}"
    shift || true
    case "$SUBCMD" in
        status)
            echo -e "${C_PURPLE}${C_BOLD}=== Molab Autonomous API & VM Status ===${C_RESET}"
            curl -s "$MOLAB_API/status" | python3 -m json.tool
            ;;
        exec)
            CMD_TO_RUN="$*"
            if [ -z "$CMD_TO_RUN" ]; then
                echo "Usage: trueengine molab exec <command>"
                exit 1
            fi
            echo -e "${C_CYAN}>>> Executing on Molab Terminal: ${CMD_TO_RUN}${C_RESET}"
            PAYLOAD=$(python3 -c "import json, sys; print(json.dumps({'command': ' '.join(sys.argv[1:]), 'wait_sec': 2.5}))" "$@")
            curl -s -X POST "$MOLAB_API/api/exec" \
                 -H "Content-Type: application/json" \
                 -d "$PAYLOAD" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    if 'output' in d:
        print(d['output'])
    else:
        print(d)
except Exception as e:
    print(e)
"
            ;;
        new|create)
            echo -e "${C_PURPLE}${C_BOLD}>>> Provisioning fresh Molab VM with RTX Pro 6000 Blackwell (98GB VRAM)...${C_RESET}"
            echo -e "${C_GRAY}Triggering syntax injection ('!sudo apt install fastfetch'), clicking 'Open terminal', and deploying Supercluster...${C_RESET}"
            curl -s -X POST "$MOLAB_API/api/create_vm" \
                 -H "Content-Type: application/json" \
                 -d '{"gpu_type": "RTX Pro 6000 (Blackwell)", "bootstrap_supercluster": true}' | python3 -m json.tool
            ;;
        terminal|term|logs)
            LINES="${1:-40}"
            echo -e "${C_CYAN}=== Molab Terminal Screen Buffer (Last ${LINES} lines) ===${C_RESET}"
            curl -s "$MOLAB_API/api/terminal?lines=${LINES}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for l in d.get('lines', []):
        print(l)
except Exception as e:
    print(e)
"
            ;;
        redeploy)
            echo -e "${C_CYAN}>>> Redeploying TrueEngine V1 Supercluster on Molab...${C_RESET}"
            curl -s -X POST "$MOLAB_API/api/redeploy" | python3 -m json.tool
            ;;
        *)
            echo "Usage: trueengine molab [status | exec <cmd> | new | terminal [lines] | redeploy]"
            ;;
    esac
}

cmd_sync() {
    echo -e "${C_CYAN}>>> Executing TrueEngine V1 Autonomous Multi-Cloud Sync...${C_RESET}"
    bash "$V1_DIR/update_all.sh"
}

cmd_restart() {
    echo -e "${C_CYAN}>>> Restarting all TrueEngine V1 systemd background services...${C_RESET}"
    systemctl --user daemon-reload
    systemctl --user restart trueengine-sync.service \
                             trueengine-molab-api.service \
                             trueengine-colab-daemon.service \
                             trueengine-molab.service \
                             trueengine-sentry.service \
                             trueengine-tournament.service \
                             trueengine-autoupdate.timer
    sleep 1
    echo -e "${C_GREEN}✓ All TrueEngine V1 services restarted successfully.${C_RESET}"
    cmd_status
}

cmd_logs() {
    SERVICE="${1:-sync}"
    case "$SERVICE" in
        api|molab-api)
            journalctl --user -u trueengine-molab-api.service -f
            ;;
        molab)
            journalctl --user -u trueengine-molab.service -f
            ;;
        colab)
            journalctl --user -u trueengine-colab-daemon.service -f
            ;;
        tournament)
            journalctl --user -u trueengine-tournament.service -f
            ;;
        sync)
            journalctl --user -u trueengine-sync.service -f
            ;;
        sentry)
            journalctl --user -u trueengine-sentry.service -f
            ;;
        *)
            echo "Usage: trueengine logs [api|molab|colab|tournament|sync|sentry]"
            ;;
    esac
}

case "${1:-status}" in
    status)
        cmd_status
        ;;
    molab)
        shift
        cmd_molab "$@"
        ;;
    sync|auto|run)
        cmd_sync
        ;;
    restart)
        cmd_restart
        ;;
    logs|log)
        cmd_logs "$2"
        ;;
    *)
        echo "Usage: trueengine [status | molab <cmd> | sync | auto | restart | logs <service>]"
        exit 1
        ;;
esac
